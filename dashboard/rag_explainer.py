#!/usr/bin/env python3
"""
NFL Edge Finder - RAG + SHAP Explainer
======================================
RAG = Retrieval Augmented Generation (Smart context-aware answers)
SHAP = Why did AI make this prediction? (Explained simply)

EVERYTHING EXPLAINED LIKE YOU'RE 10 YEARS OLD
"""

from typing import Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =============================================================================
# SHAP EXPLAINABILITY (WHY DID AI PICK THIS BET?)
# =============================================================================


def explain_prediction_simple(
    bet_info: Dict, feature_importance: Dict[str, float]
) -> Dict:
    """
    Explain WHY the AI recommended this bet.
    Uses SHAP-style feature importance but explains it simply.
    """

    # Get top 5 reasons (most important features)
    sorted_features = sorted(
        feature_importance.items(), key=lambda x: abs(x[1]), reverse=True
    )[:5]

    reasons = []

    for feature_name, importance in sorted_features:
        # Translate technical features to simple language
        simple_reason = _translate_feature_to_simple(feature_name, importance, bet_info)
        reasons.append(simple_reason)

    return {
        "main_reasons": reasons,
        "summary": _create_simple_summary(reasons),
        "confidence_explanation": _explain_confidence_simply(bet_info),
    }


def _translate_feature_to_simple(
    feature_name: str, importance: float, bet_info: Dict
) -> Dict:
    """Translate technical feature names to 10-year-old language"""

    # Mapping of technical terms to simple explanations
    translations = {
        "elo_diff": {
            "positive": "🏆 **Team Strength Difference**\n\nThe recommended team is WAY stronger! Like a 5th grader playing a 2nd grader in basketball. This is a BIG reason to bet on them.",
            "negative": "⚠️ **Team Strength Difference**\n\nThe team we're betting on is actually weaker! This is working AGAINST us. Be careful - this could be risky.",
        },
        "rest_days": {
            "positive": "😴 **Rest Advantage**\n\nOur team had more rest (like sleeping 10 hours vs 6 hours). Fresh players = better performance! This helps our bet.",
            "negative": "😪 **Rest Disadvantage**\n\nOur team is more tired (less rest). Like staying up late playing video games before a test. Not ideal!",
        },
        "injury_impact": {
            "positive": "🏥 **Injury Situation**\n\nTheir star players are OUT! Like playing basketball when the other team's best player is sick. Huge advantage for us!",
            "negative": "🤕 **Injury Situation**\n\nOUR star players are hurt! Like trying to win a game when your best friend can't play. This hurts our chances.",
        },
        "home_advantage": {
            "positive": "🏠 **Home Field Advantage**\n\nPlaying at home with fans cheering! Like playing video games on YOUR TV with YOUR controller. Big help!",
            "negative": "✈️ **Away Game**\n\nPlaying away from home. Like visiting a friend's house - their rules, their home court advantage. Harder to win!",
        },
        "weather": {
            "positive": "🌤️ **Weather Conditions**\n\nWeather favors our team's style! Like if it's rainy and we have good running backs. Perfect!",
            "negative": "🌧️ **Bad Weather**\n\nWeather hurts our team. Like trying to play football in a snowstorm when you're used to sunny California. Not fun!",
        },
        "recent_form": {
            "positive": "📈 **Hot Streak**\n\nTeam is playing awesome lately! Like when you're on a winning streak in Fortnite. Momentum is real!",
            "negative": "📉 **Cold Streak**\n\nTeam has been losing lately. Like when everything goes wrong and you can't win any games. Confidence is low.",
        },
        "division_game": {
            "positive": "🎯 **Division Rival**\n\nThey REALLY want to beat this team (big rivalry)! Like playing against your school's biggest rival. Extra motivation!",
            "negative": "😬 **Division Rival (Warning)**\n\nRivalry games are unpredictable! Even bad teams play their hearts out. Could go either way!",
        },
        "point_spread": {
            "positive": "📊 **Spread is Favorable**\n\nThe point spread (handicap) is good for us! Like getting a head start in a race. Makes winning easier!",
            "negative": "📊 **Spread is Tough**\n\nHave to win by a LOT of points. Like not just winning the race, but winning by 10 meters. Much harder!",
        },
    }

    # Get the explanation
    key = "positive" if importance > 0 else "negative"
    explanation = translations.get(feature_name, {}).get(
        key,
        f"**{feature_name}**: {'Helps our bet' if importance > 0 else 'Hurts our bet'}",
    )

    return {
        "feature": feature_name,
        "importance": abs(importance),
        "direction": "positive" if importance > 0 else "negative",
        "explanation": explanation,
        "emoji": "✅" if importance > 0 else "⚠️",
    }


def _create_simple_summary(reasons: List[Dict]) -> str:
    """Create a simple summary of why this bet is good/bad"""

    positive_count = sum(1 for r in reasons if r["direction"] == "positive")
    negative_count = len(reasons) - positive_count

    if positive_count >= 4:
        return """
        🎯 **STRONG BET!**
        
        Almost everything is going our way! Like when all the stars align.
        This is the kind of bet we LOVE to see!
        """
    elif positive_count == 3:
        return """
        ✅ **GOOD BET**
        
        More things helping than hurting. Like having more friends on your team.
        Solid opportunity!
        """
    elif positive_count == 2:
        return """
        🤔 **OKAY BET**
        
        Some good, some bad. Like a coin flip with a slight edge.
        Proceed with caution!
        """
    else:
        return """
        ⚠️ **RISKY BET**
        
        More things working against us than for us.
        Maybe skip this one and wait for a better opportunity!
        """


def _explain_confidence_simply(bet_info: Dict) -> str:
    """Explain what the confidence score means"""

    confidence = bet_info.get("win_prob", 50)

    if confidence >= 70:
        return """
        **Confidence: VERY HIGH (70%+)**
        
        Think of it like:
        - 7 out of 10 times, we win this bet
        - Like your favorite Pokemon having type advantage
        - Pretty darn confident!
        
        But remember: Even 70% means we lose 3 out of 10 times. That's normal!
        """
    elif confidence >= 60:
        return """
        **Confidence: HIGH (60-70%)**
        
        Think of it like:
        - 6 out of 10 times, we win
        - Like a good student's chance of getting an A
        - Strong bet, but not guaranteed
        
        Remember: 60% ≠ 100%! Losses will happen.
        """
    elif confidence >= 55:
        return """
        **Confidence: MEDIUM (55-60%)**
        
        Think of it like:
        - Slightly better than a coin flip
        - Like guessing heads/tails but with a weighted coin
        - Small edge, be careful with bet size
        
        These can be good if the odds are right!
        """
    else:
        return """
        **Confidence: LOW (Under 55%)**
        
        Think of it like:
        - Basically a coin flip
        - Like guessing random trivia questions
        - Not enough edge to bet confidently
        
        **Recommendation:** Skip this and find a better bet!
        """


# =============================================================================
# VISUALIZE WHY (MAKE IT PRETTY AND SIMPLE)
# =============================================================================


def show_why_this_bet(bet_info: Dict, feature_importance: Dict[str, float]):
    """Show visual explanation of why AI picked this bet"""

    st.markdown("### 🎓 Why Did AI Pick This Bet?")
    st.caption("Let's break it down super simply!")

    # Get explanation
    explanation = explain_prediction_simple(bet_info, feature_importance)

    # Show summary first
    st.info(explanation["summary"])

    st.divider()

    # Show confidence explanation
    with st.expander("🎯 What Does the Confidence Score Mean?", expanded=False):
        st.markdown(explanation["confidence_explanation"])

    st.divider()

    # Show top reasons
    st.markdown("### 📊 Top 5 Reasons (Most Important First)")

    for idx, reason in enumerate(explanation["main_reasons"], 1):
        with st.container():
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**{idx}. {reason['emoji']} Reason #{idx}**")
                st.markdown(reason["explanation"])

            with col2:
                # Show importance as a bar
                importance_pct = int(reason["importance"] * 100)
                st.metric("Impact", f"{importance_pct}%")

            st.divider()

    # Visual chart
    st.markdown("### 📈 Visual Breakdown")

    # Create bar chart of feature importance
    chart_data = pd.DataFrame(
        [
            {
                "Reason": f"Reason {idx+1}",
                "Impact": abs(r["importance"]) * 100,
                "Type": "Helps" if r["direction"] == "positive" else "Hurts",
            }
            for idx, r in enumerate(explanation["main_reasons"])
        ]
    )

    fig = px.bar(
        chart_data,
        x="Reason",
        y="Impact",
        color="Type",
        title="What's Helping vs Hurting This Bet?",
        color_discrete_map={"Helps": "#00CC66", "Hurts": "#FF6B6B"},
        labels={"Impact": "How Much It Matters (%)"},
    )

    fig.update_layout(showlegend=True, height=400, font=dict(size=14))

    st.plotly_chart(fig, width="stretch")

    # Simple explanation of the chart
    st.caption(
        """
    **How to read this chart:**
    - 🟢 Green bars = Things helping our bet (good!)
    - 🔴 Red bars = Things hurting our bet (careful!)
    - Taller bars = More important
    - Want mostly green and tall? That's a great bet!
    """
    )


# =============================================================================
# RAG SYSTEM (SMART CONTEXT-AWARE ANSWERS)
# =============================================================================


class SimpleRAG:
    """
    RAG = Retrieval Augmented Generation

    Simple explanation:
    Instead of AI making stuff up, it looks up REAL facts first,
    then answers your question using those facts.

    Like:
    - You ask: "Is Patrick Mahomes good?"
    - RAG looks up: His stats, awards, playoff record
    - Then answers: "Yes! He has 2 Super Bowls and 50+ TDs per season"

    Much better than guessing!
    """

    def __init__(self):
        # In production, this would connect to a vector database
        # For now, we'll use simple keyword matching
        self.knowledge_base = self._build_simple_knowledge_base()

    def _build_simple_knowledge_base(self) -> Dict:
        """Build a simple knowledge base of betting facts"""

        return {
            "bankroll_management": {
                "keywords": ["bankroll", "how much", "bet size", "money management"],
                "facts": [
                    "Never bet more than 2-5% of your total bankroll on one game",
                    "If you have $100, bet $2-$5 per game maximum",
                    "Losing streaks happen! Keep bet sizes small so you can survive them",
                    "As your bankroll grows, you can slowly increase bet sizes",
                ],
                "simple_answer": """
                **How Much Should I Bet?**
                
                Easy formula:
                - Total money ÷ 20 = Max bet per game
                - Example: $100 ÷ 20 = $5 max bet
                
                Why so small?
                - Protects you from losing everything
                - Let's you make many bets (more chances to win)
                - Keeps the fun going even when you lose some
                """,
            },
            "win_rate": {
                "keywords": ["win rate", "how often", "percentage", "accuracy"],
                "facts": [
                    "Professional sports bettors win 55-60% of their bets",
                    "Even winning 53% can be profitable with proper bankroll management",
                    "Nobody wins 100% of bets - that's impossible!",
                    "Focus on long-term winning, not individual bets",
                ],
                "simple_answer": """
                **What's a Good Win Rate?**
                
                Think of it like batting average in baseball:
                - 50% = Coin flip (break even)
                - 55% = Good! (like getting B's in school)
                - 60% = Great! (like getting A's)
                - 65%+ = Amazing! (like being top of class)
                
                Our AI targets 60-67% win rate.
                That means winning 6-7 out of every 10 bets!
                """,
            },
            "value_betting": {
                "keywords": ["value", "edge", "ev", "expected value"],
                "facts": [
                    "Value betting means the odds are in your favor",
                    "Like buying something on sale - you get more than you pay for",
                    "Even small edges (2-5%) add up over time",
                    "Always need edge to win long-term",
                ],
                "simple_answer": """
                **What is 'Value' in Betting?**
                
                Imagine a vending machine:
                - Normal: Pay $1, get $1 candy (fair)
                - VALUE: Pay $1, sometimes get $1.50 candy!
                
                That's value betting! When you bet $10:
                - Fair bet: Sometimes win $10, sometimes lose $10
                - Value bet: Sometimes win $12, sometimes lose $10
                
                Over time, that extra $2 adds up to big profit!
                """,
            },
        }

    def answer_question(self, question: str) -> str:
        """Answer a question using RAG (with real facts!)"""

        question_lower = question.lower()

        # Find matching topic
        for topic, info in self.knowledge_base.items():
            for keyword in info["keywords"]:
                if keyword in question_lower:
                    return self._format_rag_answer(info)

        # No match found
        return """
        🤔 **Hmm, I'm not sure about that specific question.**
        
        Try asking about:
        - Bankroll management (how much to bet)
        - Win rates (how often should I win?)
        - Value betting (what is edge/value?)
        
        Or rephrase your question and I'll try again!
        """

    def _format_rag_answer(self, info: Dict) -> str:
        """Format the answer nicely"""

        answer = info["simple_answer"] + "\n\n**Quick Facts:**\n"

        for fact in info["facts"]:
            answer += f"- {fact}\n"

        return answer


# Create global RAG instance
simple_rag = SimpleRAG()

# =============================================================================
# UI COMPONENTS
# =============================================================================


def show_rag_qa_widget():
    """Show Q&A widget powered by RAG"""

    st.markdown("### 💬 Ask Me Anything (Smart Answers!)")
    st.caption("I look up REAL facts before answering!")

    question = st.text_input(
        "Your question:",
        placeholder="How much should I bet on each game?",
        key="rag_question",
    )

    if question:
        with st.spinner("🔍 Looking up facts..."):
            answer = simple_rag.answer_question(question)

        st.markdown(answer)

    # Example questions
    with st.expander("📖 Example Questions", expanded=False):
        st.markdown(
            """
        **Try asking:**
        - "How much should I bet?"
        - "What's a good win rate?"
        - "What is value betting?"
        - "How do I manage my bankroll?"
        - "How often will I win?"
        """
        )


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    "explain_prediction_simple",
    "show_why_this_bet",
    "SimpleRAG",
    "simple_rag",
    "show_rag_qa_widget",
]
