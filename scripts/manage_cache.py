"""
Cache Management Utility

Manage the odds caching system - view stats, clear caches, export data.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import argparse
import json
from datetime import datetime

from src.utils.odds_cache import OddsCache


def show_stats(cache: OddsCache):
    """Display cache statistics."""
    stats = cache.get_stats()

    print("=" * 80)
    print("ODDS CACHE STATISTICS")
    print("=" * 80)
    print()
    print(f"Total Requests:       {stats['total_requests']}")
    print(f"Cache Hits:           {stats['cache_hits']} ({stats['hit_rate_pct']})")
    print(f"Cache Misses:         {stats['cache_misses']}")
    print(f"API Calls Saved:      {stats['api_calls_saved']}")
    print()
    print("Hit Breakdown:")
    print(f"  Memory Cache:       {stats['memory_hits']}")
    print(f"  File Cache:         {stats['file_hits']}")
    print(f"  Database:           {stats['db_hits']}")
    print()
    print("Rate Limit Status:")
    print(f"  API Calls Remaining: {cache.api_usage['remaining']}/500")
    print(f"  Monthly Usage:       {cache.api_usage['monthly_count']}")
    print()

    # Show cache files
    cache_files = sorted(
        cache.cache_dir.glob("*_nfl_odds.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if cache_files:
        print(f"Recent Cache Files ({len(cache_files)} total):")
        for f in cache_files[:5]:
            age = datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)
            age_str = (
                f"{age.seconds // 60}m ago" if age.days == 0 else f"{age.days}d ago"
            )
            size_kb = f.stat().st_size / 1024
            print(f"  {f.name} ({size_kb:.1f} KB, {age_str})")

    print("=" * 80)


def clear_memory(cache: OddsCache):
    """Clear memory cache only."""
    cache.clear_memory()
    print("[OK] Memory cache cleared")


def clear_files(cache: OddsCache, hours: int = 24):
    """Clear old cache files."""
    cache.clear_files(older_than_hours=hours)
    print(f"[OK] Cleared cache files older than {hours} hours")


def clear_all(cache: OddsCache):
    """Clear all caches (memory + files)."""
    confirm = input("Clear ALL caches? Database will be preserved. (yes/no): ")
    if confirm.lower() in ["yes", "y"]:
        cache.clear_all()
        print("[OK] All caches cleared (database preserved)")
    else:
        print("[CANCELLED]")


def show_line_movement(cache: OddsCache, game_id: str, hours: int = 24):
    """Show line movement for a specific game."""
    movements = cache.get_line_movement(game_id, lookback_hours=hours)

    if not movements:
        print(f"No line movement data found for game {game_id}")
        return

    print("=" * 80)
    print(f"LINE MOVEMENT - Game {game_id}")
    print(f"Last {hours} hours")
    print("=" * 80)
    print()

    # Group by bookmaker
    by_book = {}
    for movement in movements:
        book = movement["bookmaker"]
        if book not in by_book:
            by_book[book] = []
        by_book[book].append(movement)

    for book, moves in by_book.items():
        print(f"\n{book}:")
        print(f"{'Time':<20} {'Spread':<10} {'Home ML':<10} {'Total':<10}")
        print("-" * 50)

        for move in moves:
            timestamp = datetime.fromisoformat(move["fetch_timestamp"]).strftime(
                "%m/%d %H:%M"
            )
            spread = f"{move['spread_line']:+.1f}" if move["spread_line"] else "N/A"
            home_ml = f"{move['home_ml']:+.0f}" if move["home_ml"] else "N/A"
            total = f"{move['total_line']:.1f}" if move["total_line"] else "N/A"

            print(f"{timestamp:<20} {spread:<10} {home_ml:<10} {total:<10}")

    print("=" * 80)


def export_history(cache: OddsCache, output_file: str = "odds_history_export.json"):
    """Export historical odds data."""
    import sqlite3

    if not cache.db_path.exists():
        print("[ERROR] No database found")
        return

    conn = sqlite3.connect(cache.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM odds_snapshots")
    count = cursor.fetchone()["count"]

    print(f"Exporting {count} odds snapshots...")

    cursor.execute(
        """
        SELECT * FROM odds_snapshots 
        ORDER BY fetch_timestamp DESC 
        LIMIT 10000
    """
    )

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    output_path = Path(output_file)
    output_path.write_text(json.dumps(rows, indent=2))

    print(f"[OK] Exported {len(rows)} records to {output_file}")


def validate_cache(cache: OddsCache):
    """Validate cache integrity."""
    print("Validating cache system...")
    print()

    issues = []

    # Check directory
    if not cache.cache_dir.exists():
        issues.append("Cache directory does not exist")
    else:
        print(f"[OK] Cache directory: {cache.cache_dir}")

    # Check database
    if cache.enable_db:
        if not cache.db_path.exists():
            issues.append("Database file does not exist")
        else:
            print(f"[OK] Database: {cache.db_path}")

            # Check tables
            import sqlite3

            conn = sqlite3.connect(cache.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM odds_snapshots")
            snapshot_count = cursor.fetchone()[0]
            print(f"[OK] Database contains {snapshot_count} odds snapshots")

            cursor.execute("SELECT COUNT(*) FROM api_usage")
            usage_count = cursor.fetchone()[0]
            print(f"[OK] Database contains {usage_count} API usage records")

            conn.close()

    # Check memory cache
    if cache.enable_memory:
        mem_count = len(cache._memory)
        print(f"[OK] Memory cache contains {mem_count} entries")

    # Check file cache
    cache_files = list(cache.cache_dir.glob("*.json"))
    print(f"[OK] File cache contains {len(cache_files)} files")

    print()

    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  [!] {issue}")
    else:
        print("[OK] Cache system is healthy")


def main():
    parser = argparse.ArgumentParser(description="Manage NFL odds cache")
    parser.add_argument(
        "command",
        choices=[
            "stats",
            "clear-memory",
            "clear-files",
            "clear-all",
            "line-movement",
            "export",
            "validate",
        ],
        help="Command to execute",
    )

    parser.add_argument("--game-id", help="Game ID for line movement")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    parser.add_argument(
        "--output", default="odds_history_export.json", help="Output file for export"
    )

    args = parser.parse_args()

    # Initialize cache
    cache = OddsCache()

    # Execute command
    if args.command == "stats":
        show_stats(cache)

    elif args.command == "clear-memory":
        clear_memory(cache)

    elif args.command == "clear-files":
        clear_files(cache, hours=args.hours)

    elif args.command == "clear-all":
        clear_all(cache)

    elif args.command == "line-movement":
        if not args.game_id:
            print("[ERROR] --game-id required for line-movement command")
            return
        show_line_movement(cache, args.game_id, hours=args.hours)

    elif args.command == "export":
        export_history(cache, output_file=args.output)

    elif args.command == "validate":
        validate_cache(cache)


if __name__ == "__main__":
    main()
