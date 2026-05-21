"""Test each API key directly."""

import tomllib
from pathlib import Path

import httpx

# Load secrets
secrets_path = Path("dashboard/.streamlit/secrets.toml")
with open(secrets_path, "rb") as f:
    secrets = tomllib.load(f)

print("Testing each API key...")
print("=" * 50)

# Test Anthropic
print("\n1. ANTHROPIC (Claude):")
try:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": secrets["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-3-haiku-20240307",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Say hi in 5 words"}],
        },
        timeout=30,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("   [OK] Claude working!")
        print(f"   Response: {data['content'][0]['text']}")
    else:
        print(f"   Error: {resp.text[:300]}")
except Exception as e:
    print(f"   Error: {e}")

# Test Google
print("\n2. GOOGLE (Gemini):")
try:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={secrets['GOOGLE_API_KEY']}"
    resp = httpx.post(
        url,
        json={"contents": [{"parts": [{"text": "Say hi in 5 words"}]}]},
        timeout=30,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("   [OK] Gemini working!")
        print(f"   Response: {data['candidates'][0]['content']['parts'][0]['text']}")
    else:
        print(f"   Error: {resp.text[:300]}")
except Exception as e:
    print(f"   Error: {e}")

# Test X.AI (Grok)
print("\n3. X.AI (Grok):")
try:
    resp = httpx.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {secrets['XAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": "grok-3",
            "messages": [{"role": "user", "content": "Say hi in 5 words"}],
            "max_tokens": 100,
        },
        timeout=30,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("   [OK] Grok working!")
        print(f"   Response: {data['choices'][0]['message']['content']}")
    else:
        print(f"   Error: {resp.text[:300]}")
except Exception as e:
    print(f"   Error: {e}")

# Test OpenAI (for reference)
print("\n4. OPENAI (GPT-4):")
try:
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {secrets['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4-turbo-preview",
            "messages": [{"role": "user", "content": "Say hi in 5 words"}],
            "max_tokens": 100,
        },
        timeout=30,
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("   [OK] GPT-4 working!")
        print(f"   Response: {data['choices'][0]['message']['content']}")
    else:
        print(f"   Error: {resp.text[:300]}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 50)

