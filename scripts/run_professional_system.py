#!/usr/bin/env python3
"""
Professional NFL Betting System - Main Entry Point

Implements full professional workflow based on industry standards:
1. Validate model meets professional requirements
2. Run morning routine to identify value
3. Execute bets with proper tracking
4. Post-game CLV calculation and reporting

Usage:
    python scripts/run_professional_system.py validate
    python scripts/run_professional_system.py morning
    python scripts/run_professional_system.py dashboard
    python scripts/run_professional_system.py setup

Sources:
- Professional bettor practices (Voulgaris, Walters, Spanky)
- Sports Insights, Bet-Analytix methodology
- Peer-reviewed research (Walsh & Joshi 2024)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_validate(args):
    """Run professional validation checks."""
    from src.validation.statistical_validator import ProfessionalValidator, validate_before_deployment

    print("\n" + "=" * 70)
    print("PROFESSIONAL VALIDATION")
    print("=" * 70)

    # Load historical betting data or backtest results
    data_path = Path(args.data) if args.data else Path("data/backtest_history.parquet")

    if data_path.exists():
        history_df = pd.read_parquet(data_path)
        logger.info(f"Loaded {len(history_df)} bets from {data_path}")
    else:
        # Generate sample data for demonstration
        logger.warning(f"No data at {data_path} - using sample data for demonstration")
        np.random.seed(42)
        n = 500

        history_df = pd.DataFrame({
            'bet_odds': np.random.uniform(1.8, 2.2, n),
            'closing_odds': np.random.uniform(1.85, 2.15, n),
            'result': np.random.binomial(1, 0.54, n),
            'pred_prob': np.random.uniform(0.48, 0.62, n),
            'season': np.random.choice([2022, 2023, 2024], n)
        })

        # Calculate CLV
        history_df['clv'] = (history_df['bet_odds'] / history_df['closing_odds']) - 1

    # Run validation
    passed = validate_before_deployment(history_df)

    if passed:
        print("\n✓ System validated. Ready for paper trading.")
        print("  Next: Run 'python scripts/run_professional_system.py setup' to configure accounts")
    else:
        print("\n✗ Validation failed. Do not deploy real money.")
        print("  Fix issues above before proceeding.")

    return 0 if passed else 1


def cmd_setup(args):
    """Set up accounts and initial configuration."""
    from src.operations.position_tracker import PositionTracker, Account, ExposureLimits

    print("\n" + "=" * 70)
    print("SYSTEM SETUP")
    print("=" * 70)

    # Initialize position tracker
    limits = ExposureLimits(
        max_per_game_pct=0.02,      # 2% max per game
        max_per_day_pct=0.10,       # 10% max per day
        max_single_bet_pct=0.01,    # 1% per bet (conservative start)
        daily_loss_limit_pct=0.05   # Stop after 5% daily loss
    )

    tracker = PositionTracker(
        db_path="data/positions.db",
        initial_bankroll=args.bankroll,
        limits=limits
    )

    print(f"\nInitialized position tracker with ${args.bankroll:,.2f} bankroll")
    print(f"\nExposure Limits:")
    print(f"  Max per game:    {limits.max_per_game_pct:.0%}")
    print(f"  Max per day:     {limits.max_per_day_pct:.0%}")
    print(f"  Max single bet:  {limits.max_single_bet_pct:.0%}")
    print(f"  Daily loss stop: {limits.daily_loss_limit_pct:.0%}")

    # Add sample accounts (user should update with real accounts)
    sample_accounts = [
        Account(book="Pinnacle", balance=0, deposited=0, withdrawn=0, status="pending",
                notes="Sharp-friendly book - apply for account"),
        Account(book="Bookmaker", balance=0, deposited=0, withdrawn=0, status="pending",
                notes="Sharp-friendly book - good limits"),
        Account(book="BetCRIS", balance=0, deposited=0, withdrawn=0, status="pending",
                notes="Market-making book"),
        Account(book="DraftKings", balance=0, deposited=0, withdrawn=0, status="pending",
                notes="Soft book - line shopping"),
        Account(book="FanDuel", balance=0, deposited=0, withdrawn=0, status="pending",
                notes="Soft book - line shopping"),
    ]

    print("\nSample accounts added (update with real balances):")
    for acc in sample_accounts:
        tracker.add_account(acc)
        print(f"  • {acc.book}: {acc.notes}")

    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Get odds API key: https://the-odds-api.com")
    print("  2. Set ODDS_API_KEY environment variable")
    print("  3. Update account balances in data/positions.db")
    print("  4. Run: python scripts/run_professional_system.py morning")

    return 0


def cmd_morning(args):
    """Run morning analysis routine."""
    from src.operations.daily_workflow import DailyWorkflow
    from src.operations.position_tracker import PositionTracker
    from src.operations.line_shopper import LineShopper

    print("\n" + "=" * 70)
    print(f"MORNING ROUTINE - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Load model
    model = None
    model_path = Path("models/nfl_model.json")
    if model_path.exists():
        try:
            from src.models import XGBoostNFLModel
            model = XGBoostNFLModel.load(str(model_path))
            logger.info("Loaded trained model")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")

    # Initialize components
    tracker = PositionTracker(db_path="data/positions.db")
    shopper = LineShopper()

    workflow = DailyWorkflow(
        model=model,
        position_tracker=tracker,
        line_shopper=shopper,
        min_edge=0.02,
        min_probability=0.52
    )

    # Load today's games
    games_path = Path(args.games) if args.games else Path("data/todays_games.csv")

    if games_path.exists():
        games_df = pd.read_csv(games_path)
    else:
        # Demo mode with sample games
        logger.warning("No games file found - using demo data")
        games_df = pd.DataFrame({
            'game_id': ['demo_1', 'demo_2', 'demo_3'],
            'home_team': ['KC', 'BUF', 'SF'],
            'away_team': ['LV', 'MIA', 'SEA'],
        })

    # Run morning routine
    plan = workflow.run_morning_routine(games_df)

    # Show current account status
    print("\n")
    tracker.print_daily_summary()

    return 0


def cmd_dashboard(args):
    """Show performance dashboard."""
    from src.operations.position_tracker import PositionTracker
    from src.operations.performance_dashboard import PerformanceDashboard

    tracker = PositionTracker(db_path="data/positions.db")
    dashboard = PerformanceDashboard(position_tracker=tracker)

    bets = tracker.get_bet_history()

    if not bets:
        print("\nNo betting history found.")
        print("Run some bets first or import historical data.")
        return 1

    dashboard.print_dashboard(bets)

    # Also show weekly report
    print("\n")
    report = dashboard.generate_weekly_report(bets)
    print(report)

    return 0


def cmd_accounts(args):
    """Show account status."""
    from src.operations.position_tracker import PositionTracker

    tracker = PositionTracker(db_path="data/positions.db")
    accounts = tracker.get_accounts()

    print("\n" + "=" * 70)
    print("SPORTSBOOK ACCOUNTS")
    print("=" * 70)

    if not accounts:
        print("\nNo accounts configured.")
        print("Run: python scripts/run_professional_system.py setup")
        return 1

    total_balance = 0
    print(f"\n{'Book':20} {'Balance':>12} {'Status':>12} {'Notes'}")
    print("-" * 70)

    for acc in accounts:
        print(f"{acc.book:20} ${acc.balance:>10,.2f} {acc.status:>12} {acc.notes[:30]}")
        total_balance += acc.balance

    print("-" * 70)
    print(f"{'TOTAL':20} ${total_balance:>10,.2f}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Professional NFL Betting System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  validate    Run professional validation checks (REQUIRED before betting)
  setup       Initialize accounts and configuration
  morning     Run morning analysis routine
  dashboard   Show performance dashboard
  accounts    Show sportsbook account status

Example workflow:
  1. python scripts/run_professional_system.py validate --data backtest_results.parquet
  2. python scripts/run_professional_system.py setup --bankroll 10000
  3. python scripts/run_professional_system.py morning
  4. python scripts/run_professional_system.py dashboard
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Run validation checks')
    validate_parser.add_argument('--data', type=str, help='Path to historical data')

    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Initialize system')
    setup_parser.add_argument('--bankroll', type=float, default=10000.0,
                              help='Initial bankroll (default: 10000)')

    # Morning command
    morning_parser = subparsers.add_parser('morning', help='Run morning routine')
    morning_parser.add_argument('--games', type=str, help='Path to today\'s games')

    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Show dashboard')

    # Accounts command
    accounts_parser = subparsers.add_parser('accounts', help='Show accounts')

    args = parser.parse_args()

    if args.command == 'validate':
        return cmd_validate(args)
    elif args.command == 'setup':
        return cmd_setup(args)
    elif args.command == 'morning':
        return cmd_morning(args)
    elif args.command == 'dashboard':
        return cmd_dashboard(args)
    elif args.command == 'accounts':
        return cmd_accounts(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
