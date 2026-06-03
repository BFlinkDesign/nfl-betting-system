"""
Strategy Management Dashboard Components

BEGINNER-FRIENDLY UI for managing betting strategies.
Think of this as your strategy control panel!
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import List

import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from strategy_registry import Strategy, StrategyRegistry, StrategyStatus


def render_strategy_card(
    strategy: Strategy, registry: StrategyRegistry, key_prefix: str = ""
):
    """
    Render a single strategy card with actions.

    BEGINNER NOTE: Like a trading card for a betting strategy!
    Shows all the important info + action buttons.

    Args:
        strategy: Strategy to display
        registry: Registry instance (for updating)
        key_prefix: Unique prefix for Streamlit widget keys
    """
    # Status badge color
    status_colors = {
        "pending": "#ffa500",
        "accepted": "#00ff00",
        "rejected": "#ff0000",
        "archived": "#888888",
    }
    status_color = status_colors.get(strategy.status, "#888")

    # Win rate color (green if > 55%, red if < 50%)
    if strategy.win_rate > 55:
        wr_color = "#00ff00"
    elif strategy.win_rate < 50:
        wr_color = "#ff6666"
    else:
        wr_color = "#ffaa00"

    # ROI color
    if strategy.roi > 10:
        roi_color = "#00ff00"
    elif strategy.roi < 0:
        roi_color = "#ff6666"
    else:
        roi_color = "#ffaa00"

    # Create expandable card
    with st.expander(
        f"**{strategy.name}** ({strategy.status.upper()})", expanded=False
    ):
        # Header with key metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Win Rate",
                f"{strategy.win_rate:.1f}%",
                delta=(
                    None
                    if strategy.win_rate == 0
                    else f"{strategy.win_rate - 50:.1f}% vs 50%"
                ),
            )

        with col2:
            st.metric(
                "ROI",
                f"{strategy.roi:.1f}%",
                delta=None if strategy.roi == 0 else f"{strategy.roi:.1f}%",
            )

        with col3:
            st.metric("Sample Size", strategy.sample_size)

        with col4:
            st.metric("Edge", f"{strategy.edge:.1f}%")

        st.markdown("---")

        # Description
        st.markdown("**Description:**")
        st.write(strategy.description)

        # Pattern
        st.markdown("**Pattern:**")
        st.code(strategy.pattern, language="text")

        # Conditions (if any)
        if strategy.conditions:
            st.markdown("**Conditions:**")
            for key, value in strategy.conditions.items():
                st.write(f"- **{key}**: {value}")

        # Dates
        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"📅 Discovered: {strategy.date_discovered[:10]}")
        with col2:
            if strategy.date_reviewed:
                st.caption(f"✅ Reviewed: {strategy.date_reviewed[:10]}")

        # Notes
        if strategy.reviewer_notes:
            st.markdown("**Notes:**")
            st.info(strategy.reviewer_notes)

        # Version info
        if strategy.version > 1:
            st.caption(f"📌 Version {strategy.version}")
            if strategy.previous_version_id:
                st.caption(f"⬆️ Previous: {strategy.previous_version_id}")

        st.markdown("---")

        # Action buttons
        col1, col2, col3, col4 = st.columns(4)

        # Accept button (if pending or rejected)
        if strategy.status in ["pending", "rejected"]:
            with col1:
                if st.button(
                    "✅ Accept", key=f"{key_prefix}_accept_{strategy.strategy_id}"
                ):
                    notes = st.session_state.get(
                        f"{key_prefix}_notes_{strategy.strategy_id}", ""
                    )
                    success, message = registry.accept_strategy(
                        strategy.strategy_id, notes
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

        # Reject button (if pending or accepted)
        if strategy.status in ["pending", "accepted"]:
            with col2:
                if st.button(
                    "❌ Reject", key=f"{key_prefix}_reject_{strategy.strategy_id}"
                ):
                    notes = st.session_state.get(
                        f"{key_prefix}_notes_{strategy.strategy_id}", ""
                    )
                    success, message = registry.reject_strategy(
                        strategy.strategy_id, notes
                    )
                    if success:
                        st.warning(message)
                        st.rerun()
                    else:
                        st.error(message)

        # Archive button (if accepted)
        if strategy.status == "accepted":
            with col3:
                if st.button(
                    "📦 Archive", key=f"{key_prefix}_archive_{strategy.strategy_id}"
                ):
                    notes = st.session_state.get(
                        f"{key_prefix}_notes_{strategy.strategy_id}", ""
                    )
                    success, message = registry.archive_strategy(
                        strategy.strategy_id, notes
                    )
                    if success:
                        st.info(message)
                        st.rerun()
                    else:
                        st.error(message)

        # Delete button (dangerous!)
        with col4:
            if st.button(
                "🗑️ Delete", key=f"{key_prefix}_delete_{strategy.strategy_id}"
            ):
                # Confirm deletion
                st.session_state[f"confirm_delete_{strategy.strategy_id}"] = True

        # Confirmation for delete
        if st.session_state.get(f"confirm_delete_{strategy.strategy_id}", False):
            st.warning("⚠️ Are you sure? This cannot be undone!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "Yes, Delete",
                    key=f"{key_prefix}_confirm_delete_{strategy.strategy_id}",
                ):
                    success, message = registry.delete_strategy(strategy.strategy_id)
                    if success:
                        st.success(message)
                        st.session_state[f"confirm_delete_{strategy.strategy_id}"] = (
                            False
                        )
                        st.rerun()
                    else:
                        st.error(message)
            with col2:
                if st.button(
                    "Cancel", key=f"{key_prefix}_cancel_delete_{strategy.strategy_id}"
                ):
                    st.session_state[f"confirm_delete_{strategy.strategy_id}"] = False
                    st.rerun()

        # Notes input (for accept/reject/archive)
        st.text_area(
            "Add notes (optional):",
            key=f"{key_prefix}_notes_{strategy.strategy_id}",
            height=80,
            placeholder="Why are you accepting/rejecting this strategy?",
        )


def render_strategy_list(
    strategies: List[Strategy],
    registry: StrategyRegistry,
    title: str,
    key_prefix: str,
    empty_message: str = "No strategies found.",
):
    """
    Render a list of strategies.

    Args:
        strategies: List of strategies to display
        registry: Registry instance
        title: Section title
        key_prefix: Unique prefix for widget keys
        empty_message: Message to show if list is empty
    """
    st.markdown(f"### {title}")
    st.markdown(
        f"**{len(strategies)} strateg{'y' if len(strategies) == 1 else 'ies'}**"
    )

    if not strategies:
        st.info(empty_message)
        return

    # Sort by ROI (best first)
    strategies_sorted = sorted(strategies, key=lambda s: s.roi, reverse=True)

    for strategy in strategies_sorted:
        render_strategy_card(strategy, registry, key_prefix)


def render_add_strategy_form(registry: StrategyRegistry):
    """
    Render form to manually add a new strategy.

    BEGINNER NOTE: Like filling out a form to add a new recipe to your cookbook.
    """
    st.markdown("### ➕ Add New Strategy")

    with st.form("add_strategy_form"):
        # Basic info
        name = st.text_input("Strategy Name*", placeholder="e.g., Prime-time unders")
        description = st.text_area(
            "Description*", placeholder="What is this strategy?", height=100
        )
        pattern = st.text_input(
            "Pattern*", placeholder="e.g., game.primetime == True AND total_line > 45"
        )

        # Performance metrics
        col1, col2 = st.columns(2)
        with col1:
            win_rate = st.number_input(
                "Win Rate (%)*", min_value=0.0, max_value=100.0, value=55.0
            )
            roi = st.number_input(
                "ROI (%)*", min_value=-100.0, max_value=1000.0, value=10.0
            )
        with col2:
            sample_size = st.number_input("Sample Size*", min_value=1, value=50)
            edge = st.number_input(
                "Edge (%)", min_value=-100.0, max_value=100.0, value=5.0
            )

        # Optional
        sharpe = st.number_input(
            "Sharpe Ratio (optional)", min_value=-10.0, max_value=10.0, value=0.0
        )

        # Conditions (JSON format)
        conditions_text = st.text_area(
            "Conditions (JSON format, optional)",
            placeholder='{"primetime": true, "total_line": ">45"}',
            height=100,
        )

        submitted = st.form_submit_button("Add Strategy")

        if submitted:
            # Validate required fields
            if not name or not description or not pattern:
                st.error("Name, description, and pattern are required!")
                return

            # Parse conditions
            conditions = {}
            if conditions_text:
                try:
                    import json

                    conditions = json.loads(conditions_text)
                except:
                    st.error("Invalid JSON format for conditions!")
                    return

            # Generate ID
            strategy_id = name.lower().replace(" ", "_").replace("-", "_") + "_v1"

            # Create strategy
            strategy = Strategy(
                strategy_id=strategy_id,
                name=name,
                description=description,
                pattern=pattern,
                win_rate=win_rate,
                roi=roi,
                sample_size=sample_size,
                edge=edge,
                sharpe_ratio=sharpe if sharpe != 0 else None,
                conditions=conditions,
            )

            # Add to registry
            success, message = registry.add_strategy(strategy)

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)


def render_strategy_stats(registry: StrategyRegistry):
    """
    Render summary statistics.

    BEGINNER NOTE: Dashboard at a glance!
    Shows how many strategies you have in each status.
    """
    stats = registry.get_stats()

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total", stats["total"])

    with col2:
        st.metric("⏳ Pending", stats["pending"])

    with col3:
        st.metric("✅ Accepted", stats["accepted"])

    with col4:
        st.metric("❌ Rejected", stats["rejected"])

    with col5:
        st.metric("📦 Archived", stats["archived"])


def render_duplicate_checker(registry: StrategyRegistry):
    """
    Render duplicate detection tool.

    BEGINNER NOTE: Test if a strategy already exists before adding it.
    """
    st.markdown("### 🔍 Check for Duplicates")

    pattern = st.text_input(
        "Enter strategy pattern to check:",
        placeholder="e.g., Prime-time unders after long travel",
    )

    if pattern:
        similar = registry.find_similar_strategy(pattern, threshold=0.85)

        if similar:
            st.warning(
                f"⚠️ Similar strategy found: **{similar.name}** ({similar.strategy_id})"
            )
            st.write(f"**Similarity:** {similar.similarity_score(pattern) * 100:.1f}%")
            st.write(f"**Status:** {similar.status}")
            st.write(f"**Pattern:** `{similar.pattern}`")
        else:
            st.success("✅ No duplicates found! This is a new strategy.")


def render_version_update_form(registry: StrategyRegistry):
    """
    Render form to update a strategy with improved stats.

    BEGINNER NOTE: "Hey! This strategy got better - let me update it!"
    """
    st.markdown("### 🔄 Update Strategy Version")

    accepted_strategies = registry.get_accepted_strategies()

    if not accepted_strategies:
        st.info("No accepted strategies to update.")
        return

    # Select strategy to update
    strategy_names = {s.name: s.strategy_id for s in accepted_strategies}
    selected_name = st.selectbox(
        "Select strategy to update:", list(strategy_names.keys())
    )

    if selected_name:
        strategy_id = strategy_names[selected_name]
        strategy = registry.strategies[strategy_id]

        st.write(
            f"**Current stats:** Win Rate: {strategy.win_rate}%, ROI: {strategy.roi}%, Sample: {strategy.sample_size}"
        )

        with st.form("update_version_form"):
            st.markdown("**New performance metrics:**")

            col1, col2 = st.columns(2)
            with col1:
                new_win_rate = st.number_input(
                    "New Win Rate (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=strategy.win_rate,
                )
                new_roi = st.number_input(
                    "New ROI (%)",
                    min_value=-100.0,
                    max_value=1000.0,
                    value=strategy.roi,
                )
            with col2:
                new_sample_size = st.number_input(
                    "New Sample Size", min_value=1, value=strategy.sample_size
                )
                new_edge = st.number_input(
                    "New Edge (%)",
                    min_value=-100.0,
                    max_value=100.0,
                    value=strategy.edge,
                )

            submitted = st.form_submit_button("Create New Version")

            if submitted:
                # Check if stats actually improved
                improvements = {}
                if new_win_rate > strategy.win_rate:
                    improvements["win_rate"] = new_win_rate - strategy.win_rate
                if new_roi > strategy.roi:
                    improvements["roi"] = new_roi - strategy.roi
                if new_edge > strategy.edge:
                    improvements["edge"] = new_edge - strategy.edge

                if not improvements:
                    st.warning(
                        "⚠️ Stats didn't improve! Consider rejecting or archiving instead."
                    )
                    return

                # Show improvements
                st.success("✅ Improvements detected:")
                for metric, improvement in improvements.items():
                    st.write(f"- **{metric}**: +{improvement:.1f}%")

                # Create new version
                new_metrics = {
                    "win_rate": new_win_rate,
                    "roi": new_roi,
                    "sample_size": new_sample_size,
                    "edge": new_edge,
                }

                success, message = registry.create_strategy_version(
                    strategy_id, new_metrics
                )

                if success:
                    st.success(message)
                    st.info(f"Old version archived: {strategy_id}")
                    st.rerun()
                else:
                    st.error(message)
