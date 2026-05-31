"""
🧪 THE LAB - Full Backtesting & Training System
================================================
Visual, real-time interface for model training, backtesting, and strategy research.
Integrates with the full NFL betting system architecture.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import system components
try:
    from src.backtesting.data_loader import BacktestDataLoader
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.prediction_generator import PredictionGenerator
    from src.swarms.model_loader import ModelLoader

    BACKEND_AVAILABLE = True
except ImportError as e:
    BACKEND_AVAILABLE = False
    IMPORT_ERROR = str(e)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="THE LAB | GAMELOCK AI",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# CUSTOM CSS - CYBERPUNK LAB THEME
# -----------------------------------------------------------------------------
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
    
    :root {
        --lab-green: #22c55e;
        --lab-blue: #3b82f6;
        --lab-purple: #8b5cf6;
        --lab-orange: #f59e0b;
        --lab-red: #ef4444;
        --lab-dark: #0a0f1a;
        --lab-card: #111827;
    }
    
    html, body, .stApp {
        background: linear-gradient(135deg, #0a0f1a 0%, #0f172a 50%, #1a1a2e 100%);
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }
    
    #MainMenu, footer, header {visibility: hidden;}
    .block-container { padding: 1rem 2rem; max-width: 100%; }
    
    /* Animated grid background */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: 
            linear-gradient(rgba(34, 197, 94, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(34, 197, 94, 0.03) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
        z-index: 0;
    }
    
    /* Lab sections */
    .lab-section {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
        backdrop-filter: blur(10px);
    }
    
    .lab-section-header {
        font-family: 'Orbitron', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: #22c55e;
        letter-spacing: 2px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Model cards */
    .model-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        transition: all 0.3s ease;
    }
    
    .model-card:hover {
        border-color: #22c55e;
        box-shadow: 0 0 20px rgba(34, 197, 94, 0.2);
        transform: translateY(-2px);
    }
    
    .model-card.active {
        border-color: #22c55e;
        border-width: 2px;
        box-shadow: 0 0 30px rgba(34, 197, 94, 0.3);
    }
    
    /* Progress animations */
    @keyframes pulse-green {
        0%, 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
        50% { box-shadow: 0 0 0 10px rgba(34, 197, 94, 0); }
    }
    
    .running {
        animation: pulse-green 2s infinite;
    }
    
    /* Console output */
    .console-output {
        background: #0a0f1a;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 16px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #22c55e;
        max-height: 400px;
        overflow-y: auto;
    }
    
    .console-line {
        margin: 4px 0;
        display: flex;
        gap: 10px;
    }
    
    .console-timestamp {
        color: #6b7280;
        min-width: 80px;
    }
    
    .console-info { color: #3b82f6; }
    .console-success { color: #22c55e; }
    .console-warning { color: #f59e0b; }
    .console-error { color: #ef4444; }
    
    /* Metrics grid */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 16px;
        margin: 16px 0;
    }
    
    .metric-box {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    
    .metric-label {
        font-family: 'Orbitron', sans-serif;
        font-size: 0.65rem;
        color: #64748b;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    
    .metric-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 1.5rem;
        font-weight: 800;
        color: #fff;
        margin-top: 4px;
    }
    
    .metric-value.positive { color: #22c55e; }
    .metric-value.negative { color: #ef4444; }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(180deg, #1f2937 0%, #111827 100%);
        padding: 8px;
        border-radius: 12px;
        gap: 4px;
        border: 1px solid #374151;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: #9ca3af;
        font-weight: 600;
        padding: 12px 20px;
        font-family: 'Orbitron', sans-serif;
        font-size: 0.75rem;
        letter-spacing: 1px;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
        color: white !important;
        box-shadow: 0 0 20px rgba(34, 197, 94, 0.4);
    }
    
    /* Button overrides */
    .stButton > button {
        font-family: 'Orbitron', sans-serif;
        letter-spacing: 1px;
        font-weight: 600;
        border-radius: 8px;
    }
    
    /* Select box */
    .stSelectbox > div > div {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid #374151;
        border-radius: 8px;
    }
    
    /* Number input */
    .stNumberInput > div > div > input {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid #374151;
        border-radius: 8px;
        color: #e2e8f0;
    }
    
    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-ready { background: #22c55e; box-shadow: 0 0 10px #22c55e; }
    .status-running { background: #3b82f6; animation: pulse-green 1s infinite; }
    .status-error { background: #ef4444; }
    .status-pending { background: #6b7280; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if "backtest_results" not in st.session_state:
    st.session_state.backtest_results = None
if "backtest_history" not in st.session_state:
    st.session_state.backtest_history = []
if "console_logs" not in st.session_state:
    st.session_state.console_logs = []
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "selected_models" not in st.session_state:
    st.session_state.selected_models = []
if "training_progress" not in st.session_state:
    st.session_state.training_progress = 0


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def add_console_log(message: str, level: str = "info"):
    """Add a log entry to the console."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.console_logs.append(
        {"timestamp": timestamp, "message": message, "level": level}
    )
    # Keep last 100 logs
    st.session_state.console_logs = st.session_state.console_logs[-100:]


def render_console():
    """Render the console output."""
    st.markdown('<div class="console-output">', unsafe_allow_html=True)
    for log in st.session_state.console_logs[-20:]:
        level_class = f"console-{log['level']}"
        st.markdown(
            f"""
            <div class="console-line">
                <span class="console-timestamp">[{log['timestamp']}]</span>
                <span class="{level_class}">{log['message']}</span>
            </div>
        """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def get_available_models() -> List[str]:
    """Get list of available trained models."""
    if not BACKEND_AVAILABLE:
        return [
            "xgboost_evolved_75pct",
            "lightgbm_improved",
            "ensemble_model",
            "calibrated_model",
        ]

    try:
        loader = ModelLoader()
        return loader.list_available_models()
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return []


def get_model_metadata(model_name: str) -> Dict:
    """Get metadata for a model."""
    if not BACKEND_AVAILABLE:
        return {"exists": True, "size_mb": 2.5, "model_type": "XGBoost"}

    try:
        loader = ModelLoader()
        return loader.get_model_metadata(model_name)
    except:
        return {"exists": False}


def get_available_seasons() -> List[int]:
    """Get available seasons for backtesting."""
    if not BACKEND_AVAILABLE:
        return list(range(2016, 2025))

    try:
        loader = BacktestDataLoader()
        return loader.get_available_seasons()
    except:
        return list(range(2016, 2025))


def run_backtest_sync(
    model_name: str,
    start_year: int,
    end_year: int,
    bankroll: float,
    kelly_fraction: float,
) -> Dict:
    """Run backtest synchronously using real data."""
    if not BACKEND_AVAILABLE:
        # Backend not available - return error with helpful message
        return {
            "error": "Backend modules not available. Please ensure all dependencies are installed.",
            "help": "Run: pip install -e . from the project root",
            "metrics": None,
        }

    try:
        # Load data
        data_loader = BacktestDataLoader()
        schedules_df, pbp_df = data_loader.get_backtest_data(
            {"start_year": start_year, "end_year": end_year, "focus": "full"}
        )

        # Generate predictions
        pred_generator = PredictionGenerator()
        predictions_df = pred_generator.generate_predictions(
            schedules_df, {"model_name": model_name}, pbp_df
        )

        # Run backtest
        engine = BacktestEngine(
            initial_bankroll=bankroll, config={"kelly_fraction": kelly_fraction}
        )
        metrics, history_df = engine.run_backtest(predictions_df)

        return {
            "metrics": metrics,
            "model_name": model_name,
            "start_year": start_year,
            "end_year": end_year,
            "history": history_df.to_dict("records") if len(history_df) > 0 else [],
        }

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {"error": str(e)}


# -----------------------------------------------------------------------------
# HEADER
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-bottom: 30px;">
        <div style="display: flex; align-items: center; gap: 20px;">
            <div style="
                font-family: 'Orbitron', sans-serif;
                font-size: 2.2rem;
                font-weight: 900;
                letter-spacing: 3px;
                background: linear-gradient(135deg, #22c55e 0%, #3b82f6 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            ">THE LAB</div>
            <span style="
                background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
                color: white;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 0.7rem;
                font-weight: 700;
                font-family: Orbitron;
                letter-spacing: 1px;
            ">RESEARCH CENTER</span>
            <span style="
                background: rgba(139, 92, 246, 0.2);
                color: #a78bfa;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 0.7rem;
                font-weight: 600;
                font-family: Orbitron;
                letter-spacing: 1px;
                border: 1px solid rgba(139, 92, 246, 0.3);
            ">{'CONNECTED' if BACKEND_AVAILABLE else 'DEMO MODE'}</span>
        </div>
        <div style="color: #64748b; font-size: 0.9rem; margin-top: 10px;">
            Walk-forward backtesting • Model training • Strategy research • Real predictions
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# MAIN TABS
# -----------------------------------------------------------------------------
tab_backtest, tab_models, tab_train, tab_compare = st.tabs(
    ["BACKTEST ENGINE", "MODEL ARSENAL", "TRAINING CENTER", "STRATEGY COMPARE"]
)

# =============================================================================
# TAB 1: BACKTEST ENGINE
# =============================================================================
with tab_backtest:
    col_config, col_results = st.columns([1, 2])

    with col_config:
        st.markdown(
            '<div class="lab-section-header">⚙️ CONFIGURATION</div>',
            unsafe_allow_html=True,
        )

        # Model selection
        available_models = get_available_models()
        selected_model = st.selectbox(
            "Select Model", available_models, help="Choose a trained model to backtest"
        )

        # Date range
        seasons = get_available_seasons()
        col_start, col_end = st.columns(2)
        with col_start:
            start_year = st.selectbox("Start Year", seasons, index=0)
        with col_end:
            end_year = st.selectbox("End Year", seasons[::-1], index=0)

        # Bankroll settings
        st.markdown("---")
        st.markdown(
            '<div class="lab-section-header">💰 BANKROLL</div>', unsafe_allow_html=True
        )

        initial_bankroll = st.number_input(
            "Initial Bankroll ($)",
            min_value=100,
            max_value=1000000,
            value=10000,
            step=1000,
        )
        kelly_fraction = st.slider(
            "Kelly Fraction",
            min_value=0.05,
            max_value=1.0,
            value=0.25,
            step=0.05,
            help="Fraction of Kelly criterion to use for bet sizing",
        )

        # Run button
        st.markdown("---")
        if st.button(
            "🚀 RUN BACKTEST",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_running,
        ):
            st.session_state.is_running = True
            st.session_state.console_logs = []

            add_console_log(f"Starting backtest for {selected_model}", "info")
            add_console_log(f"Period: {start_year} - {end_year}", "info")
            add_console_log(
                f"Bankroll: ${initial_bankroll:,.0f} | Kelly: {kelly_fraction}", "info"
            )

            with st.spinner("Running backtest..."):
                add_console_log("Loading historical data...", "info")
                result = run_backtest_sync(
                    selected_model,
                    start_year,
                    end_year,
                    initial_bankroll,
                    kelly_fraction,
                )

                if "error" in result:
                    add_console_log(f"ERROR: {result['error']}", "error")
                    st.session_state.backtest_results = None
                else:
                    add_console_log(
                        f"Processed {result['metrics'].get('total_bets', 0)} bets",
                        "success",
                    )
                    add_console_log(
                        f"Win Rate: {result['metrics'].get('win_rate', 0):.1f}%",
                        "success",
                    )
                    add_console_log(
                        f"ROI: {result['metrics'].get('roi', 0):.2f}%", "success"
                    )
                    add_console_log("Backtest complete!", "success")

                    st.session_state.backtest_results = result
                    st.session_state.backtest_history.append(result)

            st.session_state.is_running = False
            st.rerun()

        # Console
        st.markdown("---")
        st.markdown(
            '<div class="lab-section-header">📟 CONSOLE</div>', unsafe_allow_html=True
        )
        render_console()

    with col_results:
        st.markdown(
            '<div class="lab-section-header">📊 RESULTS</div>', unsafe_allow_html=True
        )

        if st.session_state.backtest_results:
            metrics = st.session_state.backtest_results["metrics"]

            # KPI Row
            k1, k2, k3, k4, k5 = st.columns(5)

            roi_color = "positive" if metrics.get("roi", 0) > 0 else "negative"
            k1.markdown(
                f"""
                <div class="metric-box">
                    <div class="metric-label">ROI</div>
                    <div class="metric-value {roi_color}">{metrics.get('roi', 0):.2f}%</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            win_rate = metrics.get("win_rate", 0)
            wr_color = "positive" if win_rate > 52 else "negative"
            k2.markdown(
                f"""
                <div class="metric-box">
                    <div class="metric-label">WIN RATE</div>
                    <div class="metric-value {wr_color}">{win_rate:.1f}%</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            k3.markdown(
                f"""
                <div class="metric-box">
                    <div class="metric-label">TOTAL BETS</div>
                    <div class="metric-value">{metrics.get('total_bets', 0)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            profit = metrics.get("total_profit", 0)
            profit_color = "positive" if profit > 0 else "negative"
            k4.markdown(
                f"""
                <div class="metric-box">
                    <div class="metric-label">PROFIT</div>
                    <div class="metric-value {profit_color}">${profit:,.0f}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            sharpe = metrics.get("sharpe_ratio", 0)
            sharpe_color = "positive" if sharpe > 1 else ""
            k5.markdown(
                f"""
                <div class="metric-box">
                    <div class="metric-label">SHARPE</div>
                    <div class="metric-value {sharpe_color}">{sharpe:.2f}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

            st.markdown("---")

            # Charts
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                # Equity curve
                if st.session_state.backtest_results.get("history"):
                    history = pd.DataFrame(st.session_state.backtest_results["history"])
                    fig_equity = go.Figure()
                    fig_equity.add_trace(
                        go.Scatter(
                            x=list(range(len(history))),
                            y=history["bankroll"],
                            mode="lines",
                            fill="tozeroy",
                            line=dict(color="#22c55e", width=2),
                            fillcolor="rgba(34, 197, 94, 0.1)",
                        )
                    )
                    fig_equity.update_layout(
                        title="Equity Curve",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#94a3b8",
                        margin=dict(l=0, r=0, t=40, b=0),
                        height=250,
                        xaxis=dict(gridcolor="rgba(55,65,81,0.3)"),
                        yaxis=dict(gridcolor="rgba(55,65,81,0.3)"),
                    )
                    st.plotly_chart(fig_equity, use_container_width=True)
                else:
                    # No history data available - show message
                    st.info("📊 Run a backtest to generate equity curve data.")

            with col_chart2:
                # Win/Loss distribution
                wins = metrics.get("wins", 50)
                losses = metrics.get("losses", 40)

                fig_wl = go.Figure(
                    data=[
                        go.Bar(
                            x=["Wins", "Losses"],
                            y=[wins, losses],
                            marker_color=["#22c55e", "#ef4444"],
                            text=[wins, losses],
                            textposition="auto",
                        )
                    ]
                )
                fig_wl.update_layout(
                    title="Win/Loss Distribution",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#94a3b8",
                    margin=dict(l=0, r=0, t=40, b=0),
                    height=250,
                    xaxis=dict(gridcolor="rgba(55,65,81,0.3)"),
                    yaxis=dict(gridcolor="rgba(55,65,81,0.3)"),
                )
                st.plotly_chart(fig_wl, use_container_width=True)

            # Additional metrics
            st.markdown("---")
            st.markdown(
                '<div class="lab-section-header">📈 ADVANCED METRICS</div>',
                unsafe_allow_html=True,
            )

            adv1, adv2, adv3, adv4 = st.columns(4)
            adv1.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0):.1f}%")
            adv2.metric("Avg CLV", f"{metrics.get('avg_clv', 0):.2f}%")
            adv3.metric("Positive CLV %", f"{metrics.get('positive_clv_pct', 0):.1f}%")
            adv4.metric(
                "Record", f"{metrics.get('wins', 0)}-{metrics.get('losses', 0)}"
            )

        else:
            st.markdown(
                """
                <div style="
                    text-align: center;
                    padding: 60px;
                    color: #64748b;
                ">
                    <div style="font-size: 3rem; margin-bottom: 20px;">🧪</div>
                    <div style="font-family: Orbitron; font-size: 1.1rem; margin-bottom: 10px;">NO BACKTEST RUNNING</div>
                    <div style="font-size: 0.9rem;">Configure settings and click RUN BACKTEST to start</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

# =============================================================================
# TAB 2: MODEL ARSENAL
# =============================================================================
with tab_models:
    st.markdown(
        '<div class="lab-section-header">🎯 TRAINED MODELS</div>',
        unsafe_allow_html=True,
    )

    models = get_available_models()

    if not models:
        st.warning("No trained models found in the models/ directory")
    else:
        cols = st.columns(3)
        for i, model_name in enumerate(models):
            with cols[i % 3]:
                meta = get_model_metadata(model_name)

                # Determine model type by name
                if "xgboost" in model_name.lower():
                    model_type = "XGBoost"
                    icon = "🌲"
                    color = "#22c55e"
                elif "lightgbm" in model_name.lower():
                    model_type = "LightGBM"
                    icon = "⚡"
                    color = "#3b82f6"
                elif "ensemble" in model_name.lower():
                    model_type = "Ensemble"
                    icon = "🔗"
                    color = "#8b5cf6"
                elif "calibrated" in model_name.lower():
                    model_type = "Calibrated"
                    icon = "🎯"
                    color = "#f59e0b"
                else:
                    model_type = "Custom"
                    icon = "🧠"
                    color = "#64748b"

                size_mb = meta.get("size_mb", 0)

                st.markdown(
                    f"""
                    <div class="model-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                            <span style="font-size: 1.5rem;">{icon}</span>
                            <span style="
                                background: {color}22;
                                color: {color};
                                padding: 4px 10px;
                                border-radius: 6px;
                                font-size: 0.7rem;
                                font-weight: 600;
                                font-family: Orbitron;
                            ">{model_type}</span>
                        </div>
                        <div style="font-family: Orbitron; font-weight: 700; color: #fff; font-size: 0.9rem; margin-bottom: 8px;">
                            {model_name}
                        </div>
                        <div style="color: #64748b; font-size: 0.8rem;">
                            Size: {size_mb:.1f} MB
                        </div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )

# =============================================================================
# TAB 3: TRAINING CENTER
# =============================================================================
with tab_train:
    st.markdown(
        '<div class="lab-section-header">🏋️ MODEL TRAINING</div>',
        unsafe_allow_html=True,
    )

    col_train_config, col_train_status = st.columns([1, 1])

    with col_train_config:
        st.markdown("#### Training Configuration")

        train_model_type = st.selectbox(
            "Model Type",
            ["XGBoost", "LightGBM", "Ensemble"],
            help="Select the type of model to train",
        )

        train_seasons = st.multiselect(
            "Training Seasons",
            get_available_seasons(),
            default=get_available_seasons()[-5:],
            help="Select seasons to use for training",
        )

        val_split = st.slider(
            "Validation Split",
            min_value=0.1,
            max_value=0.3,
            value=0.2,
            step=0.05,
            help="Fraction of data to use for validation",
        )

        # Hyperparameters
        st.markdown("---")
        st.markdown("#### Hyperparameters")

        if train_model_type == "XGBoost":
            n_estimators = st.number_input(
                "n_estimators", min_value=50, max_value=1000, value=200
            )
            max_depth = st.number_input("max_depth", min_value=2, max_value=15, value=6)
            learning_rate = st.number_input(
                "learning_rate", min_value=0.01, max_value=0.5, value=0.1, step=0.01
            )
        elif train_model_type == "LightGBM":
            n_estimators = st.number_input(
                "n_estimators", min_value=50, max_value=1000, value=200
            )
            num_leaves = st.number_input(
                "num_leaves", min_value=10, max_value=100, value=31
            )
            learning_rate = st.number_input(
                "learning_rate", min_value=0.01, max_value=0.5, value=0.1, step=0.01
            )
        else:
            st.info(
                "Ensemble combines multiple models - no additional hyperparameters needed"
            )

        st.markdown("---")

        if st.button("🚀 START TRAINING", type="primary", use_container_width=True):
            st.info(
                "⚠️ Training integration requires full backend setup. Use the scripts/train_*.py scripts for now."
            )
            st.code(f"""
# To train a new model, run from project root:
python scripts/train_xgboost.py --seasons {','.join(map(str, train_seasons))}

# Or use the Makefile:
make train-xgboost
            """)

    with col_train_status:
        st.markdown("#### Training Status")

        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
                border: 1px solid #374151;
                border-radius: 12px;
                padding: 40px;
                text-align: center;
            ">
                <div style="font-size: 3rem; margin-bottom: 20px;">🔬</div>
                <div style="font-family: Orbitron; font-size: 1rem; color: #94a3b8; margin-bottom: 20px;">
                    TRAINING READY
                </div>
                <div style="color: #64748b; font-size: 0.85rem;">
                    Configure parameters and click START TRAINING
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("#### Trained Models")

        # Get real model info from models directory
        training_history = []
        models_dir = Path(__file__).parent.parent.parent / "models"
        if models_dir.exists():
            for model_file in models_dir.glob("*.pkl"):
                import os
                from datetime import datetime

                mtime = os.path.getmtime(model_file)
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                training_history.append(
                    {
                        "model": model_file.stem,
                        "date": date_str,
                        "accuracy": "N/A",  # Would need to read from metrics file
                        "status": "success",
                    }
                )

        if not training_history:
            st.info("No trained models found. Run training to create models.")

        for run in training_history:
            status_color = "#22c55e" if run["status"] == "success" else "#ef4444"
            st.markdown(
                f"""
                <div style="
                    background: rgba(30, 41, 59, 0.5);
                    border-radius: 8px;
                    padding: 12px;
                    margin: 8px 0;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <div>
                        <div style="font-weight: 600; color: #fff;">{run['model']}</div>
                        <div style="font-size: 0.75rem; color: #64748b;">{run['date']}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: #22c55e; font-weight: 600;">{run['accuracy']}</div>
                        <div style="
                            width: 8px;
                            height: 8px;
                            background: {status_color};
                            border-radius: 50%;
                            display: inline-block;
                            box-shadow: 0 0 10px {status_color};
                        "></div>
                    </div>
                </div>
            """,
                unsafe_allow_html=True,
            )

# =============================================================================
# TAB 4: STRATEGY COMPARE
# =============================================================================
with tab_compare:
    st.markdown(
        '<div class="lab-section-header">⚔️ MODEL COMPARISON</div>',
        unsafe_allow_html=True,
    )

    # Model selection for comparison
    models_to_compare = st.multiselect(
        "Select Models to Compare",
        get_available_models(),
        default=get_available_models()[:3],
        help="Select 2+ models to compare performance",
    )

    if len(models_to_compare) >= 2:
        col_cmp1, col_cmp2 = st.columns([2, 1])

        with col_cmp1:
            # Comparison chart
            if st.session_state.backtest_history:
                # Use actual backtest results
                comparison_data = []
                for result in st.session_state.backtest_history:
                    if result.get("model_name") in models_to_compare:
                        comparison_data.append(
                            {
                                "Model": result["model_name"],
                                "ROI": result["metrics"].get("roi", 0),
                                "Win Rate": result["metrics"].get("win_rate", 0),
                                "Sharpe": result["metrics"].get("sharpe_ratio", 0),
                            }
                        )

                if comparison_data:
                    df_compare = pd.DataFrame(comparison_data)

                    fig_compare = go.Figure()
                    for model in df_compare["Model"].unique():
                        model_data = df_compare[df_compare["Model"] == model]
                        fig_compare.add_trace(
                            go.Bar(
                                name=model,
                                x=["ROI %", "Win Rate %", "Sharpe × 10"],
                                y=[
                                    model_data["ROI"].values[0],
                                    model_data["Win Rate"].values[0],
                                    model_data["Sharpe"].values[0] * 10,
                                ],
                            )
                        )

                    fig_compare.update_layout(
                        title="Model Comparison",
                        barmode="group",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font_color="#94a3b8",
                        margin=dict(l=0, r=0, t=40, b=0),
                        height=350,
                        xaxis=dict(gridcolor="rgba(55,65,81,0.3)"),
                        yaxis=dict(gridcolor="rgba(55,65,81,0.3)"),
                    )
                    st.plotly_chart(fig_compare, use_container_width=True)
            else:
                st.info("Run backtests on multiple models to see comparison")

        with col_cmp2:
            st.markdown("#### Quick Actions")

            if st.button("📊 Run Comparison Backtest", use_container_width=True):
                st.info("Running backtest on all selected models...")
                # Would trigger backtests for all selected models

            if st.button("📥 Export Results", use_container_width=True):
                if st.session_state.backtest_history:
                    results_json = json.dumps(
                        st.session_state.backtest_history, indent=2, default=str
                    )
                    st.download_button(
                        "Download JSON",
                        results_json,
                        file_name="backtest_results.json",
                        mime="application/json",
                    )
    else:
        st.info("Select at least 2 models to compare")

# -----------------------------------------------------------------------------
# FOOTER
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #64748b; font-size: 0.8rem; padding: 20px;">
        <span style="font-family: Orbitron;">GAMELOCK AI</span> • THE LAB • 
        Walk-forward backtesting powered by real ML models
    </div>
""",
    unsafe_allow_html=True,
)
