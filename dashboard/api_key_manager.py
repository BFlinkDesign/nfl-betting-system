"""API Key Manager for Dashboard - Easy configuration interface."""

import os
import re
from pathlib import Path
from typing import Dict, Optional

import streamlit as st
from dotenv import load_dotenv, set_key


class APIKeyManager:
    """Manage API keys through dashboard interface."""

    def __init__(self):
        """Initialize API key manager."""
        self.env_file = Path(__file__).parent.parent / "config" / "api_keys.env"
        self.env_template = (
            Path(__file__).parent.parent / "config" / "api_keys.env.template"
        )

        # Ensure env file exists
        if not self.env_file.exists() and self.env_template.exists():
            # Copy template to create new env file
            self.env_file.write_text(self.env_template.read_text())

        # Load current keys
        load_dotenv(self.env_file)

    def get_key(self, key_name: str) -> Optional[str]:
        """
        Get API key value.

        Args:
            key_name: Name of the API key

        Returns:
            Key value or None
        """
        return os.getenv(key_name)

    def set_key(self, key_name: str, key_value: str) -> bool:
        """
        Set API key value.

        Args:
            key_name: Name of the API key
            key_value: New value for the key

        Returns:
            True if successful
        """
        try:
            set_key(str(self.env_file), key_name, key_value)
            # Reload environment
            load_dotenv(self.env_file, override=True)
            return True
        except Exception as e:
            st.error(f"Failed to save key: {e}")
            return False

    def validate_key_format(self, key_name: str, key_value: str) -> tuple[bool, str]:
        """
        Validate API key format.

        Args:
            key_name: Name of the API key
            key_value: Value to validate

        Returns:
            Tuple of (is_valid, message)
        """
        if not key_value or key_value.strip() == "":
            return False, "Key cannot be empty"

        # Validate specific key formats
        if key_name == "OPENAI_API_KEY":
            if not key_value.startswith("sk-"):
                return False, "OpenAI keys should start with 'sk-'"
            if len(key_value) < 20:
                return False, "Key seems too short"

        elif key_name == "ANTHROPIC_API_KEY":
            if not key_value.startswith("sk-ant-"):
                return False, "Anthropic keys should start with 'sk-ant-'"

        elif key_name == "ODDS_API_KEY":
            if len(key_value) < 20:
                return False, "API key seems too short"

        return True, "Format looks good"

    def test_key(self, key_name: str) -> tuple[bool, str]:
        """
        Test if API key is working.

        Args:
            key_name: Name of the API key

        Returns:
            Tuple of (is_working, message)
        """
        key_value = self.get_key(key_name)

        if not key_value:
            return False, "No key configured"

        try:
            # Test OpenAI
            if key_name == "OPENAI_API_KEY":
                import openai

                openai.api_key = key_value
                # Try to list models (lightweight test)
                models = openai.Model.list()
                return True, f"✅ Connected! Found {len(models.data)} models"

            # Test Anthropic
            elif key_name == "ANTHROPIC_API_KEY":
                import anthropic

                client = anthropic.Anthropic(api_key=key_value)
                # Try a minimal request
                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "test"}],
                )
                return True, "✅ Connected! API key is valid"

            # Test Google Gemini
            elif key_name == "GOOGLE_API_KEY":
                import google.generativeai as genai

                genai.configure(api_key=key_value)
                # Try to list models
                models = genai.list_models()
                return True, "✅ Connected! API key is valid"

            # Test The Odds API
            elif key_name == "ODDS_API_KEY":
                import requests

                response = requests.get(
                    "https://api.the-odds-api.com/v4/sports",
                    params={"apiKey": key_value},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    return True, f"✅ Connected! Found {len(data)} sports"
                else:
                    return False, f"❌ API error: {response.status_code}"

            else:
                return False, "Test not implemented for this API"

        except ImportError:
            return False, "⚠️ Required library not installed"
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                return False, "❌ Invalid API key"
            elif "403" in error_msg or "Forbidden" in error_msg:
                return False, "❌ API key doesn't have permission"
            elif "quota" in error_msg.lower():
                return False, "⚠️ Quota exceeded"
            else:
                return False, f"❌ Error: {error_msg[:50]}"

    def get_all_keys_status(self) -> Dict[str, Dict]:
        """
        Get status of all configured API keys.

        Returns:
            Dictionary with key status information
        """
        keys = {
            "OPENAI_API_KEY": {
                "name": "OpenAI (GPT-4)",
                "required": False,
                "icon": "🟢",
                "cost": "~$0.03/analysis",
                "free_tier": False,
            },
            "ANTHROPIC_API_KEY": {
                "name": "Anthropic (Claude)",
                "required": False,
                "icon": "🟣",
                "cost": "~$0.015/analysis",
                "free_tier": False,
            },
            "GOOGLE_API_KEY": {
                "name": "Google (Gemini)",
                "required": False,
                "icon": "🔵",
                "cost": "FREE",
                "free_tier": True,
            },
            "ODDS_API_KEY": {
                "name": "The Odds API",
                "required": True,
                "icon": "📊",
                "cost": "FREE (500/mo) or $99/mo",
                "free_tier": True,
            },
            "XAI_API_KEY": {
                "name": "xAI (Grok)",
                "required": False,
                "icon": "⚡",
                "cost": "Varies",
                "free_tier": False,
            },
        }

        status = {}
        for key_name, info in keys.items():
            key_value = self.get_key(key_name)
            status[key_name] = {
                **info,
                "configured": bool(key_value),
                "masked_value": self._mask_key(key_value) if key_value else None,
            }

        return status

    def _mask_key(self, key: str) -> str:
        """
        Mask API key for display.

        Args:
            key: API key to mask

        Returns:
            Masked key (e.g., "sk-...xyz")
        """
        if not key:
            return "Not set"

        if len(key) <= 10:
            return "***"

        return f"{key[:7]}...{key[-4:]}"


# =============================================================================
# STREAMLIT UI COMPONENTS
# =============================================================================


def show_api_key_settings():
    """Display API key management interface."""
    st.markdown("### 🔑 API Key Configuration")
    st.caption("Configure your API keys for data sources and AI reasoning")

    manager = APIKeyManager()
    all_keys = manager.get_all_keys_status()

    # Show summary
    configured_count = sum(1 for k in all_keys.values() if k["configured"])
    total_count = len(all_keys)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Configured", f"{configured_count}/{total_count}")
    with col2:
        required_keys = [k for k in all_keys.values() if k["required"]]
        required_configured = sum(1 for k in required_keys if k["configured"])
        st.metric("Required", f"{required_configured}/{len(required_keys)}")
    with col3:
        ai_keys = [
            k
            for k in all_keys.values()
            if "OpenAI" in k["name"] or "Claude" in k["name"] or "Gemini" in k["name"]
        ]
        ai_configured = sum(1 for k in ai_keys if k["configured"])
        st.metric("AI Providers", f"{ai_configured}/{len(ai_keys)}")

    st.divider()

    # Tabs for different API categories
    data_tab, ai_tab, optional_tab = st.tabs(
        ["📊 Data APIs", "🤖 AI Reasoning", "⚡ Optional"]
    )

    # Data APIs tab
    with data_tab:
        st.markdown("#### Betting Odds & Data")

        # The Odds API
        show_api_key_input(
            manager,
            "ODDS_API_KEY",
            all_keys["ODDS_API_KEY"],
            help_text="""
            **The Odds API** provides live betting odds from 40+ sportsbooks.

            **Get your key:**
            1. Sign up at https://the-odds-api.com/
            2. Get 500 FREE requests/month
            3. Copy your API key

            **Cost:** FREE tier (500 requests/month) or $99/month unlimited
            """,
        )

        st.info(
            """
        **Free Data Sources (No Keys Needed):**
        - ✅ ESPN API (scores, schedules, team data)
        - ✅ NOAA Weather (stadium weather forecasts)
        - ✅ nflverse (historical play-by-play data)

        These are already configured and working!
        """
        )

    # AI Reasoning tab
    with ai_tab:
        st.markdown("#### AI Reasoning Swarm")
        st.caption("Configure multiple AIs for intelligent bet analysis (all optional)")

        # OpenAI
        show_api_key_input(
            manager,
            "OPENAI_API_KEY",
            all_keys["OPENAI_API_KEY"],
            help_text="""
            **OpenAI (GPT-4)** provides strategic betting analysis.

            **Get your key:**
            1. Go to https://platform.openai.com/api-keys
            2. Sign up / Log in
            3. Click "Create new secret key"
            4. Copy key (starts with sk-...)

            **Cost:** ~$0.03 per game analysis (~$8/season for 272 games)

            **Note:** This is different from ChatGPT Plus subscription!
            """,
        )

        # Anthropic
        show_api_key_input(
            manager,
            "ANTHROPIC_API_KEY",
            all_keys["ANTHROPIC_API_KEY"],
            help_text="""
            **Anthropic (Claude)** provides risk assessment and validation.

            **Get your key:**
            1. Go to https://console.anthropic.com/
            2. Sign up / Log in
            3. Go to API Keys section
            4. Create new key (starts with sk-ant-...)

            **Cost:** ~$0.015 per game analysis (~$5/season)
            """,
        )

        # Google Gemini
        show_api_key_input(
            manager,
            "GOOGLE_API_KEY",
            all_keys["GOOGLE_API_KEY"],
            help_text="""
            **Google (Gemini)** provides comprehensive bet review.

            **Get your key:**
            1. Go to https://makersuite.google.com/app/apikey
            2. Sign in with Google account
            3. Create API key
            4. Copy the key

            **Cost:** FREE tier (15 requests/minute)

            **Best for beginners:** Start with Gemini (it's free!)
            """,
        )

        st.success(
            """
        💡 **Recommendation:** Start with Google Gemini (FREE) for AI analysis.
        Add OpenAI + Anthropic later for full 3-AI consensus ($15/season total).
        """
        )

    # Optional APIs tab
    with optional_tab:
        st.markdown("#### Optional Integrations")

        # xAI Grok
        show_api_key_input(
            manager,
            "XAI_API_KEY",
            all_keys["XAI_API_KEY"],
            help_text="""
            **xAI (Grok)** - Elon's AI with edgy personality.

            **Get your key:**
            1. Sign up for xAI API access
            2. Get API key from dashboard

            **Cost:** Varies based on plan
            **Status:** Optional, not required for core functionality
            """,
        )

        st.info(
            """
        These APIs are completely optional. The system works great without them!
        """
        )

    st.divider()

    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧪 Test All Keys", width="stretch"):
            with st.spinner("Testing API connections..."):
                results = {}
                for key_name, key_info in all_keys.items():
                    if key_info["configured"]:
                        is_working, message = manager.test_key(key_name)
                        results[key_name] = (is_working, message)

                # Show results
                for key_name, (is_working, message) in results.items():
                    if is_working:
                        st.success(f"{all_keys[key_name]['name']}: {message}")
                    else:
                        st.error(f"{all_keys[key_name]['name']}: {message}")

    with col2:
        if st.button("📋 View Template", width="stretch"):
            with st.expander("api_keys.env.template", expanded=True):
                if manager.env_template.exists():
                    st.code(manager.env_template.read_text(), language="bash")
                else:
                    st.warning("Template file not found")

    with col3:
        if st.button("🔄 Reload Keys", width="stretch"):
            load_dotenv(manager.env_file, override=True)
            st.success("✅ Keys reloaded!")
            st.rerun()


def show_api_key_input(
    manager: APIKeyManager, key_name: str, key_info: Dict, help_text: str = None
):
    """
    Display API key input widget.

    Args:
        manager: APIKeyManager instance
        key_name: Name of the API key
        key_info: Key information dictionary
        help_text: Optional help text
    """
    with st.container():
        # Header
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**{key_info['icon']} {key_info['name']}**")
            if key_info["configured"]:
                st.caption(f"Current: {key_info['masked_value']}")
            else:
                st.caption("Not configured")

        with col2:
            if key_info["configured"]:
                st.success("✅ Set")
            else:
                if key_info["required"]:
                    st.error("⚠️ Required")
                else:
                    st.info("Optional")

        # Cost info
        st.caption(f"💰 Cost: {key_info['cost']}")

        # Help text
        if help_text:
            with st.expander(f"ℹ️ How to get {key_info['name']} API key"):
                st.markdown(help_text)

        # Input field
        new_value = st.text_input(
            f"Enter {key_info['name']} API Key",
            value="",
            type="password",
            key=f"input_{key_name}",
            placeholder=f"Paste your {key_info['name']} API key here...",
        )

        # Actions
        col1, col2, col3 = st.columns([2, 2, 2])

        with col1:
            if st.button("💾 Save", key=f"save_{key_name}", width="stretch"):
                if new_value:
                    # Validate format
                    is_valid, msg = manager.validate_key_format(key_name, new_value)

                    if is_valid:
                        # Save
                        if manager.set_key(key_name, new_value):
                            st.success(f"✅ {key_info['name']} key saved!")
                            st.rerun()
                        else:
                            st.error("Failed to save key")
                    else:
                        st.warning(f"⚠️ {msg}")
                else:
                    st.warning("Please enter a key")

        with col2:
            if key_info["configured"]:
                if st.button("🧪 Test", key=f"test_{key_name}", width="stretch"):
                    with st.spinner(f"Testing {key_info['name']}..."):
                        is_working, message = manager.test_key(key_name)

                        if is_working:
                            st.success(message)
                        else:
                            st.error(message)

        with col3:
            if key_info["configured"]:
                if st.button(
                    "🗑️ Remove",
                    key=f"remove_{key_name}",
                    width="stretch",
                ):
                    if manager.set_key(key_name, ""):
                        st.success(f"✅ {key_info['name']} key removed")
                        st.rerun()

        st.divider()


# =============================================================================
# EXPORT
# =============================================================================

__all__ = ["APIKeyManager", "show_api_key_settings", "show_api_key_input"]
