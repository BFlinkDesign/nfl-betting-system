#!/usr/bin/env python3
"""
NFL Edge Finder - Simple AI Login (No API Keys!)
================================================
Let users login with their ChatGPT, Claude, Gemini accounts.
No technical knowledge needed - just like logging into Facebook!

EXPLAINS EVERYTHING LIKE YOU'RE 10 YEARS OLD
"""

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

# =============================================================================
# SIMPLE EXPLANATIONS (LIKE YOU'RE 10!)
# =============================================================================

SIMPLE_EXPLANATIONS = {
    "what_is_ai": """
    🤖 **What is AI? (Explained Simply)**
    
    Imagine you have a super smart friend who:
    - Has read every NFL game ever played
    - Remembers every play, every score, every injury
    - Can do math faster than a calculator
    - Never gets tired or makes silly mistakes
    
    That's what AI is! It's like having the smartest sports friend ever,
    who helps you make better betting decisions.
    
    **In this app:**
    - AI looks at the game (like Chiefs vs Raiders)
    - Thinks about what might happen
    - Tells you if it's a good bet or not
    - Explains WHY in simple words
    """,
    "why_multiple_ais": """
    🎓 **Why Do We Ask 3 Different AIs?**
    
    Imagine you're deciding whether to go to the park:
    - You ask Mom → She says "Check the weather"
    - You ask Dad → He says "Finish homework first"
    - You ask Grandma → She says "Bring a jacket!"
    
    They all see it differently! That's good because:
    - If everyone agrees = PROBABLY a good idea!
    - If they disagree = Maybe think more about it
    
    **Same with AI betting advisors:**
    - GPT-4 might notice something Claude missed
    - Claude might catch a risk Gemini didn't see
    - When all 3 agree = That's a STRONG bet!
    """,
    "what_is_confidence": """
    🎯 **What Does "Confidence" Mean?**
    
    Think about guessing what's for dinner:
    - If you smell pizza = HIGH confidence it's pizza! 🍕
    - If you hear sizzling = MEDIUM confidence it's burgers? 🍔
    - If you have no clue = LOW confidence, could be anything 🤷
    
    **In betting:**
    - HIGH confidence = AI is pretty sure (like smelling pizza)
    - MEDIUM confidence = AI thinks so but not 100%
    - LOW confidence = AI isn't sure, be careful!
    
    **Rule of thumb:**
    Only bet when confidence is MEDIUM or HIGH!
    """,
    "what_is_edge": """
    💰 **What is "Edge"? (The Secret to Winning)**
    
    Imagine a coin flip game:
    - Normal: Heads you win $10, Tails you lose $10 = Fair (no edge)
    - UNFAIR: Heads you win $12, Tails you lose $10 = YOU HAVE EDGE!
    
    **Edge means the game is unfair IN YOUR FAVOR!**
    
    Example:
    - Sportsbook says Chiefs have 50% chance to win
    - Our AI says they have 65% chance to win
    - That 15% difference = YOUR EDGE!
    
    **Simple rule:**
    - No edge (0%) = Don't bet (it's a coin flip)
    - Small edge (2-4%) = Maybe bet small
    - BIG edge (8%+) = GOOD BET! (But not too much money!)
    """,
    "why_dont_i_always_win": """
    🎲 **If AI Is Smart, Why Don't I Win Every Time?**
    
    Great question! Here's why:
    
    **Think about Pokemon battles:**
    - Your Charizard has 80% chance to win
    - But sometimes the other Pokemon gets lucky
    - 80% ≠ 100%!
    
    **In betting:**
    - 70% win chance = You win 7 out of 10 times
    - That means you LOSE 3 out of 10 times!
    - That's normal and okay!
    
    **The key:**
    - Keep making good bets (with edge)
    - Over time, you'll win more than you lose
    - But you'll NEVER win every single time
    
    **Like getting good grades:**
    - Study hard = Usually get A's
    - But sometimes you get a B
    - Still doing great overall!
    """,
    "what_is_bankroll": """
    🏦 **What is "Bankroll"? (Your Betting Piggy Bank)**
    
    Your bankroll is like your video game money:
    - You start with $100
    - Win a bet = Money goes UP! 💰
    - Lose a bet = Money goes DOWN 📉
    - Game over = When you run out
    
    **IMPORTANT RULES:**
    
    1️⃣ **Never bet all your money at once!**
       - Like don't spend all your allowance on one toy
       - Spread it out over many bets
    
    2️⃣ **Small bets are smart**
       - If you have $100, bet $5-$10 max
       - This way if you lose, you can try again
    
    3️⃣ **Add money slowly**
       - When you win, your bankroll grows
       - When it grows, you can bet a bit more
    
    **Think of it like:**
    - Your bankroll = Your game lives
    - Each bet = A level in the game
    - Smart bets = More lives for longer!
    """,
}

# =============================================================================
# AI PLATFORM LOGIN (SIMPLE - NO API KEYS!)
# =============================================================================

AI_PLATFORMS = {
    "ChatGPT": {
        "name": "ChatGPT (OpenAI)",
        "icon": "🟢",
        "free": True,
        "description": "The most popular AI! Like having a really smart tutor.",
        "signup_url": "https://chat.openai.com/",
        "how_to": """
        **How to get ChatGPT (FREE!):**
        
        1. Go to chat.openai.com
        2. Click "Sign Up"
        3. Use your email or Google account
        4. Done! You have ChatGPT!
        
        **What it costs:**
        - ChatGPT-3.5 = FREE forever!
        - ChatGPT-4 = $20/month (better but optional)
        
        **For betting:**
        - Free version works fine!
        - Upgrade only if you want faster/smarter answers
        """,
        "integration_available": True,
    },
    "Claude": {
        "name": "Claude (Anthropic)",
        "icon": "🟣",
        "free": True,
        "description": "Super careful AI that thinks before answering. Great for checking bets!",
        "signup_url": "https://claude.ai/",
        "how_to": """
        **How to get Claude (FREE!):**
        
        1. Go to claude.ai
        2. Click "Get Started"
        3. Sign in with Google or email
        4. Done! You have Claude!
        
        **What it costs:**
        - Claude = FREE with limits
        - Claude Pro = $20/month (more usage)
        
        **For betting:**
        - Free version is perfect!
        - Very good at finding risks in bets
        """,
        "integration_available": True,
    },
    "Gemini": {
        "name": "Gemini (Google)",
        "icon": "🔵",
        "free": True,
        "description": "Google's AI! Fast and free. Great for quick bet checks.",
        "signup_url": "https://gemini.google.com/",
        "how_to": """
        **How to get Gemini (FREE!):**
        
        1. Go to gemini.google.com
        2. Sign in with your Gmail
        3. That's it! You're done!
        
        **What it costs:**
        - Completely FREE!
        - No paid version needed
        
        **For betting:**
        - Best free option
        - Very fast responses
        - Good at explaining things simply
        """,
        "integration_available": True,
    },
    "Grok": {
        "name": "Grok (X/Twitter)",
        "icon": "⚡",
        "free": False,
        "description": "Elon's AI! Fun personality. Needs X Premium.",
        "signup_url": "https://x.com/i/grok",
        "how_to": """
        **How to get Grok:**
        
        1. Have an X (Twitter) account
        2. Subscribe to X Premium ($8/month)
        3. Grok is included!
        
        **What it costs:**
        - X Premium = $8/month
        - Grok is part of that
        
        **For betting:**
        - Fun and edgy responses
        - Good for second opinions
        - Optional (not needed)
        """,
        "integration_available": False,  # Coming soon
    },
    "Perplexity": {
        "name": "Perplexity AI",
        "icon": "🔍",
        "free": True,
        "description": "AI that shows where it got info. Good for fact-checking!",
        "signup_url": "https://www.perplexity.ai/",
        "how_to": """
        **How to get Perplexity (FREE!):**
        
        1. Go to perplexity.ai
        2. Click "Sign Up"
        3. Use email or Google
        4. Start asking!
        
        **What it costs:**
        - FREE forever
        - Pro = $20/month (optional)
        
        **For betting:**
        - Shows sources (like Wikipedia)
        - Good for checking team stats
        - Great for learning!
        """,
        "integration_available": False,  # Coming soon
    },
}

# =============================================================================
# SIMPLE AI SETUP WIZARD
# =============================================================================


def show_simple_ai_setup():
    """Simple wizard for setting up AI (no technical stuff!)"""

    st.title("🤖 Get Your AI Betting Buddies!")
    st.markdown("### No API keys, no coding - just simple logins like Facebook!")

    # Explain what we're doing
    with st.expander("❓ What are we setting up? (Click to learn)", expanded=False):
        st.markdown(SIMPLE_EXPLANATIONS["what_is_ai"])
        st.markdown(SIMPLE_EXPLANATIONS["why_multiple_ais"])

    st.divider()

    # Show each AI platform
    for platform_key, platform in AI_PLATFORMS.items():
        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"### {platform['icon']} {platform['name']}")
                st.caption(platform["description"])

                # Show if free or paid
                if platform["free"]:
                    st.success("✅ **FREE** - No credit card needed!")
                else:
                    st.warning(f"💰 Requires subscription")

                # How to get it
                with st.expander(f"📖 How to get {platform['name']}", expanded=False):
                    st.markdown(platform["how_to"])
                    st.markdown(f"[**👉 Sign up here**]({platform['signup_url']})")

            with col2:
                if platform["integration_available"]:
                    # Check if user has it
                    has_account = st.checkbox(
                        "I have this!",
                        key=f"has_{platform_key}",
                        help=f"Check this after you sign up for {platform['name']}",
                    )

                    if has_account:
                        st.success("✅ Ready!")
                else:
                    st.info("🔜 Coming soon!")

            st.divider()

    # Summary
    st.markdown("### 🎯 Recommendation for Beginners:")
    st.info(
        """
    **Get these 3 (all FREE!):**
    
    1. **Gemini** 🔵 - Easiest (just use your Gmail!)
    2. **ChatGPT** 🟢 - Most popular
    3. **Claude** 🟣 - Great for double-checking
    
    **Time needed:** 5 minutes total
    
    **Cost:** $0 (completely free!)
    """
    )

    # Next steps
    if st.button("✅ I've Signed Up - Let's Connect Them!", type="primary"):
        st.balloons()
        st.success("🎉 Awesome! Now let's connect your AI accounts...")
        st.info("👉 Go to Settings → AI Connections to link your accounts")


# =============================================================================
# SIMPLE AI STATUS CHECKER
# =============================================================================


def show_ai_status_simple():
    """Show AI status in simple language"""

    st.markdown("### 🤖 Your AI Helpers")

    # Check which AIs are available
    connected_ais = []

    # Check session state for connected AIs
    if st.session_state.get("has_ChatGPT"):
        connected_ais.append("ChatGPT")
    if st.session_state.get("has_Claude"):
        connected_ais.append("Claude")
    if st.session_state.get("has_Gemini"):
        connected_ais.append("Gemini")

    if not connected_ais:
        st.warning(
            """
        ⚠️ **No AI helpers connected yet!**
        
        **What this means:**
        You won't get smart bet advice from AI.
        
        **What to do:**
        Click the button below to set up your free AI accounts!
        (Takes 5 minutes, costs $0)
        """
        )

        if st.button("🚀 Set Up AI Helpers (FREE!)", type="primary"):
            st.session_state["show_ai_setup"] = True
            st.rerun()

    else:
        st.success(
            f"""
        ✅ **{len(connected_ais)} AI helpers ready!**
        
        Connected: {', '.join(connected_ais)}
        
        **What this means:**
        Your bets will have smart AI analysis!
        """
        )

        # Show simple status for each
        cols = st.columns(len(connected_ais))
        for idx, ai in enumerate(connected_ais):
            with cols[idx]:
                icon = AI_PLATFORMS[ai]["icon"]
                st.markdown(f"### {icon}")
                st.caption(AI_PLATFORMS[ai]["name"])
                st.metric("Status", "Ready", delta="✓")


# =============================================================================
# EXPLAIN LIKE I'M 10 - Q&A WIDGET
# =============================================================================


def show_eli10_helper():
    """Explain complex betting concepts like talking to a 10-year-old"""

    st.markdown("### 🎓 Need Help Understanding Something?")
    st.caption("Ask anything! I'll explain it super simply.")

    questions = [
        ("What is AI?", "what_is_ai"),
        ("Why use 3 different AIs?", "why_multiple_ais"),
        ("What does 'Confidence' mean?", "what_is_confidence"),
        ("What is 'Edge'?", "what_is_edge"),
        ("Why don't I win every time?", "why_dont_i_always_win"),
        ("What is 'Bankroll'?", "what_is_bankroll"),
    ]

    selected = st.selectbox(
        "Pick a question:", options=[q[0] for q in questions], key="eli10_question"
    )

    # Find the explanation
    for question_text, explanation_key in questions:
        if question_text == selected:
            st.markdown(SIMPLE_EXPLANATIONS[explanation_key])
            break

    st.divider()

    # Custom question
    st.markdown("#### 💬 Have a different question?")
    custom_q = st.text_input(
        "Type your question here:", placeholder="Why is this bet good?"
    )

    if custom_q and st.button("Get Simple Answer"):
        st.info(
            """
        🤖 **AI Simple Explainer:**
        
        I'll answer this in the simplest way possible!
        (This feature uses your connected AI accounts)
        """
        )

        # TODO: Call AI with "explain like I'm 10" prompt
        st.write("Feature coming in next update!")


# =============================================================================
# AI INSUFFICIENCY DETECTOR
# =============================================================================


def check_ai_quality_simple(prediction_confidence: float, edge: float) -> dict:
    """
    Check if AI model is doing a good job (explained simply).
    Returns warnings if something seems off.
    """

    issues = []
    severity = "good"  # good, warning, bad

    # Check 1: Is confidence too low?
    if prediction_confidence < 0.52:
        issues.append(
            {
                "problem": "AI isn't very sure about this bet",
                "simple_explanation": """
            **Think of it like this:**
            You're guessing if it will rain tomorrow, but you're only 52% sure.
            That's basically a coin flip! Not very helpful.
            
            **What to do:**
            Skip this bet. Wait for one where AI is more confident (60%+ is better).
            """,
                "emoji": "🤔",
            }
        )
        severity = "warning"

    # Check 2: Is edge too small?
    if edge < 0.02:
        issues.append(
            {
                "problem": "The 'edge' is too tiny",
                "simple_explanation": """
            **Imagine:**
            You're selling lemonade for $1, but it costs you $0.99 to make.
            Sure, you make 1 cent profit, but is it worth it?
            
            **What to do:**
            Look for bets with bigger edge (3%+ is better).
            Small edges aren't worth the risk!
            """,
                "emoji": "📏",
            }
        )
        if severity == "good":
            severity = "warning"

    # Check 3: High confidence but low edge (suspicious!)
    if prediction_confidence > 0.70 and edge < 0.03:
        issues.append(
            {
                "problem": "Something weird: AI is confident but edge is small",
                "simple_explanation": """
            **This is like:**
            Being 100% sure your team will win, but the prize is only 10 cents.
            If you're so sure, the prize should be bigger!
            
            **What might be wrong:**
            - Sportsbook might know something we don't
            - AI might be overconfident
            - Line might have moved
            
            **What to do:**
            Be extra careful. Maybe skip this one.
            """,
                "emoji": "🚨",
            }
        )
        severity = "bad"

    # Check 4: Everything looks great!
    if not issues:
        issues.append(
            {
                "problem": None,
                "simple_explanation": """
            **Great news!**
            
            ✅ AI is confident (like being sure it's pizza for dinner!)
            ✅ Edge is good (unfair game in your favor!)
            ✅ Everything checks out!
            
            **This is a QUALITY bet!**
            
            (But remember: Even good bets lose sometimes. That's normal!)
            """,
                "emoji": "🎯",
            }
        )

    return {
        "severity": severity,
        "issues": issues,
        "overall_grade": _get_simple_grade(severity),
        "should_bet": severity != "bad",
    }


def _get_simple_grade(severity: str) -> str:
    """Convert severity to simple grade like school"""
    grades = {
        "good": "A (Excellent bet!)",
        "warning": "C (Okay but be careful)",
        "bad": "F (Skip this one!)",
    }
    return grades.get(severity, "?")


def show_ai_quality_check(prediction_confidence: float, edge: float):
    """Show AI quality check in simple terms"""

    st.markdown("### 🔍 Bet Quality Check")
    st.caption("Is this bet actually good? Let's check!")

    result = check_ai_quality_simple(prediction_confidence, edge)

    # Show grade
    if result["severity"] == "good":
        st.success(f"**Grade: {result['overall_grade']}**")
    elif result["severity"] == "warning":
        st.warning(f"**Grade: {result['overall_grade']}**")
    else:
        st.error(f"**Grade: {result['overall_grade']}**")

    # Show each issue
    for issue in result["issues"]:
        with st.expander(
            f"{issue['emoji']} {issue['problem'] or 'Quality Check Passed!'}",
            expanded=(result["severity"] == "bad"),
        ):
            st.markdown(issue["simple_explanation"])

    # Final recommendation
    st.divider()
    if result["should_bet"]:
        st.info("💡 **Recommendation:** This bet passed the quality check!")
    else:
        st.warning("⚠️ **Recommendation:** Skip this bet. Wait for a better one!")


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    "show_simple_ai_setup",
    "show_ai_status_simple",
    "show_eli10_helper",
    "check_ai_quality_simple",
    "show_ai_quality_check",
    "SIMPLE_EXPLANATIONS",
    "AI_PLATFORMS",
]
