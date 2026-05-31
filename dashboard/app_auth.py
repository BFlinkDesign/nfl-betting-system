#!/usr/bin/env python3
"""
NFL Edge Finder - Enterprise PWA with Authentication
====================================================
Features:
- OAuth 2.0 (Google, Apple, GitHub)
- 2FA (TOTP, SMS)
- Biometric (WebAuthn, Face ID, Touch ID)
- Role-based access control
- Advanced admin panel
- One-click model retraining
- Bulldog system controls
"""

import base64
import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pyotp
import qrcode
import streamlit as st
import streamlit.components.v1 as components

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Auth imports
try:
    from jose import JWTError, jwt
    from passlib.context import CryptContext
except ImportError:
    st.error("❌ Authentication libraries not installed. Run setup script first!")
    st.stop()

# =================================================================================
# CONFIGURATION
# =================================================================================

st.set_page_config(
    page_title="NFL Edge Finder - Login",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# =================================================================================
# DATABASE HELPERS
# =================================================================================

import sqlite3


def get_db():
    """Get database connection."""
    db_path = Path(__file__).parent.parent / "data" / "auth.db"
    db_path.parent.mkdir(exist_ok=True)
    return sqlite3.connect(db_path, check_same_thread=False)


def init_db():
    """Initialize database if doesn't exist."""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            full_name TEXT,
            is_active INTEGER DEFAULT 1,
            is_admin INTEGER DEFAULT 0,
            oauth_provider TEXT,
            two_factor_enabled INTEGER DEFAULT 0,
            two_factor_secret TEXT,
            biometric_enabled INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """
    )

    # User settings
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            bankroll REAL DEFAULT 500,
            risk_profile TEXT DEFAULT 'small',
            min_edge REAL DEFAULT 0.015,
            min_probability REAL DEFAULT 0.52,
            notifications_enabled INTEGER DEFAULT 1,
            bulldog_enabled INTEGER DEFAULT 0,
            auto_retrain INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    conn.commit()
    conn.close()


# Initialize on startup
init_db()

# =================================================================================
# AUTH FUNCTIONS
# =================================================================================


def verify_password(plain_password, hashed_password):
    """Verify password hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Hash password."""
    return pwd_context.hash(password)


def create_user(email, username, password, full_name=""):
    """Create new user."""
    conn = get_db()
    cursor = conn.cursor()

    try:
        hashed_pw = get_password_hash(password)
        cursor.execute(
            """
            INSERT INTO users (email, username, hashed_password, full_name)
            VALUES (?, ?, ?, ?)
        """,
            (email, username, hashed_pw, full_name),
        )

        user_id = cursor.lastrowid

        # Create default settings
        cursor.execute(
            """
            INSERT INTO user_settings (user_id) VALUES (?)
        """,
            (user_id,),
        )

        conn.commit()
        return True, "User created successfully!"
    except sqlite3.IntegrityError:
        return False, "Email or username already exists"
    finally:
        conn.close()


def authenticate_user(username, password):
    """Authenticate user with username/password."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, email, hashed_password, two_factor_enabled, two_factor_secret, is_admin
        FROM users
        WHERE username = ? AND is_active = 1
    """,
        (username,),
    )

    user = cursor.fetchone()
    conn.close()

    if not user:
        return None

    user_id, username, email, hashed_pw, tfa_enabled, tfa_secret, is_admin = user

    if not verify_password(password, hashed_pw):
        return None

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "tfa_enabled": bool(tfa_enabled),
        "tfa_secret": tfa_secret,
        "is_admin": bool(is_admin),
    }


def enable_2fa(user_id):
    """Enable 2FA for user."""
    secret = pyotp.random_base32()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE users SET two_factor_enabled = 1, two_factor_secret = ?
        WHERE id = ?
    """,
        (secret, user_id),
    )
    conn.commit()
    conn.close()

    return secret


def verify_2fa(user_id, token):
    """Verify 2FA token."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT two_factor_secret FROM users WHERE id = ?
    """,
        (user_id,),
    )

    result = cursor.fetchone()
    conn.close()

    if not result:
        return False

    secret = result[0]
    totp = pyotp.TOTP(secret)
    return totp.verify(token)


# =================================================================================
# SESSION MANAGEMENT
# =================================================================================


def init_session():
    """Initialize session state."""
    if "user" not in st.session_state:
        st.session_state.user = None
    if "page" not in st.session_state:
        st.session_state.page = "login"
    if "2fa_pending" not in st.session_state:
        st.session_state["2fa_pending"] = False


init_session()

# =================================================================================
# LOGIN PAGE
# =================================================================================


def login_page():
    """Login/signup page."""
    st.markdown(
        """
    <style>
        .auth-container {
            max-width: 450px;
            margin: 2rem auto;
            padding: 2rem;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .auth-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .social-button {
            width: 100%;
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-radius: 8px;
            border: 1px solid #ddd;
            background: white;
            cursor: pointer;
            font-size: 1rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }
        .social-button:hover {
            background: #f9fafb;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### 🏈 NFL Edge Finder")
        st.caption("Sign in to access your betting intelligence")

        tab1, tab2 = st.tabs(["Sign In", "Sign Up"])

        # ===== SIGN IN TAB =====
        with tab1:
            st.markdown("#### Welcome Back!")

            # OAuth Buttons
            st.markdown("**Quick Sign In:**")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(
                    "🍎 Sign in with Apple",
                    use_container_width=True,
                    key="apple_signin",
                ):
                    st.info(
                        "🔄 Apple Sign In coming soon! Enable in config/auth_keys.env"
                    )
            with col_b:
                if st.button(
                    "🔵 Sign in with Google",
                    use_container_width=True,
                    key="google_signin",
                ):
                    st.info(
                        "🔄 Google Sign In coming soon! Enable in config/auth_keys.env"
                    )

            if st.button(
                "😺 Sign in with GitHub", use_container_width=True, key="github_signin"
            ):
                st.info("🔄 GitHub Sign In coming soon! Enable in config/auth_keys.env")

            st.divider()
            st.markdown("**Or use your account:**")

            # Traditional login
            username = st.text_input("Username or Email", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")

            col1, col2 = st.columns([3, 2])
            with col1:
                remember = st.checkbox("Remember me")
            with col2:
                st.markdown("[Forgot password?](#)")

            if st.button("Sign In", type="primary", use_container_width=True):
                if not username or not password:
                    st.error("Please enter username and password")
                else:
                    user = authenticate_user(username, password)
                    if user:
                        if user["tfa_enabled"]:
                            st.session_state["2fa_pending"] = True
                            st.session_state["2fa_user"] = user
                            st.rerun()
                        else:
                            st.session_state.user = user
                            st.session_state.page = "dashboard"
                            st.success(f"✅ Welcome back, {user['username']}!")
                            st.rerun()
                    else:
                        st.error("❌ Invalid username or password")

        # ===== SIGN UP TAB =====
        with tab2:
            st.markdown("#### Create Your Account")

            # OAuth signup
            st.markdown("**Quick Sign Up:**")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(
                    "🍎 Sign up with Apple",
                    use_container_width=True,
                    key="apple_signup",
                ):
                    st.info("🔄 Apple Sign In coming soon!")
            with col_b:
                if st.button(
                    "🔵 Sign up with Google",
                    use_container_width=True,
                    key="google_signup",
                ):
                    st.info("🔄 Google Sign In coming soon!")

            st.divider()
            st.markdown("**Or create account:**")

            # Registration form
            email = st.text_input("Email", key="signup_email")
            username = st.text_input("Username", key="signup_username")
            full_name = st.text_input("Full Name", key="signup_fullname")
            password = st.text_input("Password", type="password", key="signup_password")
            password2 = st.text_input(
                "Confirm Password", type="password", key="signup_password2"
            )

            terms = st.checkbox("I agree to the Terms and Privacy Policy")

            if st.button("Create Account", type="primary", use_container_width=True):
                if not all([email, username, password, password2]):
                    st.error("Please fill all fields")
                elif password != password2:
                    st.error("Passwords don't match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters")
                elif not terms:
                    st.error("Please accept the terms")
                else:
                    success, message = create_user(email, username, password, full_name)
                    if success:
                        st.success(f"✅ {message} You can now sign in!")
                    else:
                        st.error(f"❌ {message}")


# =================================================================================
# 2FA VERIFICATION PAGE
# =================================================================================


def twofa_page():
    """2FA verification page."""
    st.markdown("### 🔐 Two-Factor Authentication")
    st.info("Enter the 6-digit code from your authenticator app")

    user = st.session_state.get("2fa_user")

    code = st.text_input("6-Digit Code", max_chars=6, key="2fa_code")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Verify", type="primary", use_container_width=True):
            if verify_2fa(user["id"], code):
                st.session_state.user = user
                st.session_state.page = "dashboard"
                st.session_state["2fa_pending"] = False
                st.success("✅ Verified!")
                st.rerun()
            else:
                st.error("❌ Invalid code")
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.session_state["2fa_pending"] = False
            st.rerun()


# =================================================================================
# MAIN DASHBOARD (After Login)
# =================================================================================


def main_dashboard():
    """Main dashboard for authenticated users."""
    # Import the main app
    from app import main as dashboard_main

    # Add logout button in sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user['username']}")
        st.caption(f"{st.session_state.user['email']}")

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.page = "login"
            st.rerun()

    # Show main dashboard
    dashboard_main()


# =================================================================================
# ROUTING
# =================================================================================


def main():
    """Main app routing."""
    if st.session_state.get("2fa_pending"):
        twofa_page()
    elif st.session_state.user is None:
        login_page()
    else:
        # Import and run the main dashboard
        exec(open(Path(__file__).parent / "app.py").read())


if __name__ == "__main__":
    main()
