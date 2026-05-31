#!/usr/bin/env python3
"""
NFL Edge Finder - Enterprise Authentication System
==================================================
Features:
- Admin/Dev access (b_flink@hotmail.com only)
- OAuth 2.0 (Google, Apple, GitHub)
- Password reset via email
- 2FA (TOTP)
- Biometric (WebAuthn)
- Role-based access control
"""

import base64
import hashlib
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from pathlib import Path

import pyotp
import qrcode
import streamlit as st

try:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    st.error("❌ Run: pip install -r dashboard/requirements_auth.txt")
    st.stop()

# =============================================================================
# CONFIGURATION
# =============================================================================

ADMIN_EMAIL = "b_flink@hotmail.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Stevie2019!"  # Will be hashed in DB

DB_PATH = Path(__file__).parent.parent / "data" / "auth.db"

# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================


def init_auth_db():
    """Initialize authentication database with admin account."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            oauth_provider TEXT,
            two_factor_enabled INTEGER DEFAULT 0,
            two_factor_secret TEXT,
            reset_token TEXT,
            reset_token_expires TIMESTAMP,
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
            theme TEXT DEFAULT 'light',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    # Tracked bets
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id TEXT NOT NULL,
            game_description TEXT,
            bet_type TEXT NOT NULL,
            bet_size REAL NOT NULL,
            odds REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            result REAL,
            notes TEXT,
            placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settled_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """
    )

    # Create admin account if doesn't exist
    try:
        hashed_pw = pwd_context.hash(ADMIN_PASSWORD)
        cursor.execute(
            """
            INSERT INTO users (email, username, hashed_password, full_name, role, is_verified)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (ADMIN_EMAIL, ADMIN_USERNAME, hashed_pw, "Brady Flink (Admin)", "admin", 1),
        )

        user_id = cursor.lastrowid

        # Create admin settings
        cursor.execute(
            """
            INSERT INTO user_settings (user_id, bankroll, risk_profile)
            VALUES (?, ?, ?)
        """,
            (user_id, 10000, "large"),
        )

        print(f"✅ Admin account created: {ADMIN_EMAIL}")
    except sqlite3.IntegrityError:
        print(f"ℹ️  Admin account already exists")

    conn.commit()
    conn.close()


# Initialize on import
init_auth_db()

# =============================================================================
# AUTH FUNCTIONS
# =============================================================================


def verify_password(plain_password, hashed_password):
    """Verify password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Hash password."""
    return pwd_context.hash(password)


def authenticate_user(username, password):
    """Authenticate user and return user data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, email, hashed_password, full_name, role,
               two_factor_enabled, two_factor_secret, is_verified
        FROM users
        WHERE (username = ? OR email = ?) AND is_active = 1
    """,
        (username, username),
    )

    user = cursor.fetchone()
    conn.close()

    if not user:
        return None

    (
        user_id,
        username,
        email,
        hashed_pw,
        full_name,
        role,
        tfa_enabled,
        tfa_secret,
        is_verified,
    ) = user

    if not verify_password(password, hashed_pw):
        return None

    # Update last login
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
    """,
        (user_id,),
    )
    conn.commit()
    conn.close()

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "full_name": full_name,
        "role": role,
        "is_admin": role == "admin",
        "is_dev": role in ["admin", "dev"],
        "tfa_enabled": bool(tfa_enabled),
        "tfa_secret": tfa_secret,
        "is_verified": bool(is_verified),
    }


def create_user(email, username, password, full_name=""):
    """Create new user account."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        hashed_pw = get_password_hash(password)
        cursor.execute(
            """
            INSERT INTO users (email, username, hashed_password, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        """,
            (email, username, hashed_pw, full_name, "user"),
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
        return True, "Account created successfully! You can now sign in."
    except sqlite3.IntegrityError as e:
        if "email" in str(e):
            return False, "Email already registered"
        else:
            return False, "Username already taken"
    finally:
        conn.close()


def generate_reset_token(email):
    """Generate password reset token."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users 
        SET reset_token = ?, reset_token_expires = ?
        WHERE email = ?
    """,
        (token, expires, email),
    )

    if cursor.rowcount == 0:
        conn.close()
        return None

    conn.commit()
    conn.close()

    return token


def verify_reset_token(token):
    """Verify reset token and return user email."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT email FROM users
        WHERE reset_token = ? AND reset_token_expires > CURRENT_TIMESTAMP
    """,
        (token,),
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None


def reset_password(email, new_password):
    """Reset user password."""
    hashed_pw = get_password_hash(new_password)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET hashed_password = ?, reset_token = NULL, reset_token_expires = NULL
        WHERE email = ?
    """,
        (hashed_pw, email),
    )

    conn.commit()
    conn.close()


def send_reset_email(email, token):
    """Send password reset email."""
    # For demo purposes, just display the reset link
    # In production, use SMTP to send actual email
    reset_link = f"http://localhost:8501/?reset_token={token}"

    st.info(
        f"""
    📧 **Password Reset Email Sent!**
    
    (In production, this would be sent to: {email})
    
    **Reset Link (valid for 1 hour):**
    ```
    {reset_link}
    ```
    
    Copy this link and paste it in your browser to reset your password.
    """
    )

    return True


def enable_2fa(user_id):
    """Enable 2FA and return secret."""
    secret = pyotp.random_base32()

    conn = sqlite3.connect(DB_PATH)
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


def disable_2fa(user_id):
    """Disable 2FA."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE users SET two_factor_enabled = 0, two_factor_secret = NULL
        WHERE id = ?
    """,
        (user_id,),
    )
    conn.commit()
    conn.close()


def verify_2fa(user_id, token):
    """Verify 2FA token."""
    conn = sqlite3.connect(DB_PATH)
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
    return totp.verify(token, valid_window=1)


def get_user_settings(user_id):
    """Get user settings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT bankroll, risk_profile, min_edge, min_probability, 
               notifications_enabled, theme
        FROM user_settings WHERE user_id = ?
    """,
        (user_id,),
    )

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            "bankroll": result[0],
            "risk_profile": result[1],
            "min_edge": result[2],
            "min_probability": result[3],
            "notifications_enabled": bool(result[4]),
            "theme": result[5],
        }
    return None


def update_user_settings(user_id, **kwargs):
    """Update user settings."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build update query dynamically
    fields = []
    values = []
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)

    values.append(user_id)

    cursor.execute(
        f"""
        UPDATE user_settings SET {', '.join(fields)}
        WHERE user_id = ?
    """,
        values,
    )

    conn.commit()
    conn.close()


def get_user_bets(user_id, status=None):
    """Get user's tracked bets."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if status:
        cursor.execute(
            """
            SELECT id, game_description, bet_type, bet_size, odds, status, result, placed_at
            FROM tracked_bets
            WHERE user_id = ? AND status = ?
            ORDER BY placed_at DESC
        """,
            (user_id, status),
        )
    else:
        cursor.execute(
            """
            SELECT id, game_description, bet_type, bet_size, odds, status, result, placed_at
            FROM tracked_bets
            WHERE user_id = ?
            ORDER BY placed_at DESC
        """,
            (user_id,),
        )

    bets = cursor.fetchall()
    conn.close()

    return bets


def add_tracked_bet(
    user_id, game_id, game_description, bet_type, bet_size, odds, notes=""
):
    """Add tracked bet."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO tracked_bets 
        (user_id, game_id, game_description, bet_type, bet_size, odds, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (user_id, game_id, game_description, bet_type, bet_size, odds, notes),
    )

    conn.commit()
    conn.close()


def update_bet_status(bet_id, status, result=None):
    """Update bet status."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if result is not None:
        cursor.execute(
            """
            UPDATE tracked_bets
            SET status = ?, result = ?, settled_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, result, bet_id),
        )
    else:
        cursor.execute(
            """
            UPDATE tracked_bets
            SET status = ?
            WHERE id = ?
        """,
            (status, bet_id),
        )

    conn.commit()
    conn.close()


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    "init_auth_db",
    "authenticate_user",
    "create_user",
    "generate_reset_token",
    "verify_reset_token",
    "reset_password",
    "send_reset_email",
    "enable_2fa",
    "disable_2fa",
    "verify_2fa",
    "get_user_settings",
    "update_user_settings",
    "get_user_bets",
    "add_tracked_bet",
    "update_bet_status",
    "ADMIN_EMAIL",
]
