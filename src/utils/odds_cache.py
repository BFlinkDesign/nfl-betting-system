"""
Multi-Layer Odds Caching System

Implements 3-tier caching:
1. Memory cache (hot) - 5 minute TTL
2. File cache (warm) - Dynamic TTL based on game time
3. SQLite database (cold) - Historical data forever

Optimizes API usage and provides instant responses.
"""

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.token_bucket import MultiAPITokenBucket, RateLimitStatus

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Track cache performance metrics."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_calls_saved: int = 0
    memory_hits: int = 0
    file_hits: int = 0
    db_hits: int = 0

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    def to_dict(self) -> Dict:
        return {**asdict(self), "hit_rate_pct": f"{self.hit_rate:.1f}%"}


class OddsCache:
    """
    Multi-layer caching system for NFL odds data.

    Cache Layers:
    - Layer 1 (Hot): In-memory dict - 5 min TTL
    - Layer 2 (Warm): JSON files - Dynamic TTL (2-60 min)
    - Layer 3 (Cold): SQLite DB - Forever (historical tracking)

    Dynamic TTL based on game proximity:
    - < 1 hour to kickoff: 2 minutes
    - 1-6 hours: 15 minutes
    - 6-24 hours: 30 minutes
    - > 24 hours: 60 minutes
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
        enable_memory: bool = True,
        enable_files: bool = True,
        enable_db: bool = True,
    ):
        """
        Initialize the caching system.

        Args:
            cache_dir: Directory for cache files
            db_path: Path to SQLite database
            enable_memory: Enable in-memory cache layer
            enable_files: Enable file cache layer
            enable_db: Enable database layer
        """
        self.cache_dir = cache_dir or Path("data/odds_cache")
        self.db_path = db_path or Path("data/odds_history.db")

        self.enable_memory = enable_memory
        self.enable_files = enable_files
        self.enable_db = enable_db

        # Layer 1: Memory cache
        self._memory: Dict[str, Dict] = {}
        self._memory_timestamps: Dict[str, datetime] = {}

        # Statistics
        self.stats = CacheStats()
        self.stats_file = self.cache_dir / "cache_stats.json"

        # Rate limit tracking (legacy)
        self.api_usage = {
            "daily_count": 0,
            "monthly_count": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
            "limit": 500,
            "remaining": 500,
        }

        # Token bucket for rate limiting
        self.token_bucket = MultiAPITokenBucket()
        self.token_bucket.register_default("odds_api")

        # Initialize
        self._setup()

    def _setup(self):
        """Create cache directory and database."""
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing stats
        if self.stats_file.exists():
            try:
                data = json.loads(self.stats_file.read_text())
                self.stats.total_requests = data.get("total_requests", 0)
                self.stats.cache_hits = data.get("cache_hits", 0)
                self.stats.cache_misses = data.get("cache_misses", 0)
                self.stats.api_calls_saved = data.get("api_calls_saved", 0)
                self.stats.memory_hits = data.get("memory_hits", 0)
                self.stats.file_hits = data.get("file_hits", 0)
                self.stats.db_hits = data.get("db_hits", 0)
            except Exception as e:
                logger.warning(f"Could not load cache stats: {e}")

        # Initialize database
        if self.enable_db:
            self._init_database()

    def _init_database(self):
        """Create SQLite database schema for historical odds."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main odds snapshots table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_timestamp DATETIME NOT NULL,
                game_id TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                commence_time DATETIME NOT NULL,
                bookmaker TEXT NOT NULL,
                spread_line REAL,
                spread_home_odds REAL,
                spread_away_odds REAL,
                home_ml REAL,
                away_ml REAL,
                total_line REAL,
                over_odds REAL,
                under_odds REAL,
                raw_data TEXT
            )
        """
        )

        # Indexes for fast queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_game_time 
            ON odds_snapshots(game_id, fetch_timestamp)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_commence 
            ON odds_snapshots(commence_time)
        """
        )

        # API usage tracking table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                endpoint TEXT NOT NULL,
                response_time_ms INTEGER,
                games_count INTEGER,
                calls_remaining INTEGER
            )
        """
        )

        conn.commit()
        conn.close()

        logger.info(f"Initialized odds database at {self.db_path}")

    def get(
        self, key: str = "nfl_odds", max_age_minutes: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Get cached odds data with automatic fallback through cache layers.

        Args:
            key: Cache key (default: "nfl_odds")
            max_age_minutes: Maximum acceptable cache age (None = use dynamic TTL)

        Returns:
            Cached data if found and fresh, None otherwise
        """
        self.stats.total_requests += 1

        # Layer 1: Check memory cache
        if self.enable_memory and key in self._memory:
            age_seconds = (
                datetime.now() - self._memory_timestamps[key]
            ).total_seconds()
            ttl_seconds = 300  # 5 minutes for memory

            if age_seconds < ttl_seconds:
                self.stats.cache_hits += 1
                self.stats.memory_hits += 1
                logger.debug(f"[CACHE HIT] Memory ({age_seconds:.0f}s old)")
                return self._memory[key]
            else:
                # Stale, remove from memory
                del self._memory[key]
                del self._memory_timestamps[key]

        # Layer 2: Check file cache
        if self.enable_files:
            cached_file = self._find_recent_cache_file(key, max_age_minutes)
            if cached_file:
                try:
                    data = json.loads(cached_file.read_text())

                    # Populate memory cache
                    if self.enable_memory:
                        self._memory[key] = data
                        self._memory_timestamps[key] = datetime.now()

                    age_minutes = (
                        datetime.now()
                        - datetime.fromtimestamp(cached_file.stat().st_mtime)
                    ).seconds // 60
                    self.stats.cache_hits += 1
                    self.stats.file_hits += 1
                    logger.info(f"[CACHE HIT] File ({age_minutes}m old)")
                    return data

                except Exception as e:
                    logger.warning(f"Error reading cache file: {e}")

        # Cache miss
        self.stats.cache_misses += 1
        logger.info("[CACHE MISS] Fresh data needed")
        return None

    def set(self, data: Dict, key: str = "nfl_odds"):
        """
        Store odds data in all cache layers.

        Args:
            data: Odds data to cache
            key: Cache key
        """
        timestamp = datetime.now()

        # Add metadata
        cache_entry = {
            "data": data,
            "cached_at": timestamp.isoformat(),
            "cached_at_unix": timestamp.timestamp(),
            "key": key,
        }

        # Layer 1: Memory cache
        if self.enable_memory:
            self._memory[key] = cache_entry
            self._memory_timestamps[key] = timestamp

        # Layer 2: File cache
        if self.enable_files:
            filename = f"{timestamp.strftime('%Y-%m-%d_%H-%M')}_{key}.json"
            filepath = self.cache_dir / filename

            try:
                filepath.write_text(json.dumps(cache_entry, indent=2))

                # Create/update symlink to latest (Windows may need admin rights)
                try:
                    latest_link = self.cache_dir / f"{key}_latest.json"
                    if latest_link.exists() or latest_link.is_symlink():
                        latest_link.unlink()
                    latest_link.symlink_to(filepath.name)
                except (OSError, NotImplementedError) as symlink_error:
                    # Symlinks may not work on Windows without admin - not critical
                    logger.debug(
                        f"Could not create symlink (not critical): {symlink_error}"
                    )

                logger.debug(f"[CACHE WRITE] File: {filename}")
            except Exception as e:
                logger.error(f"Error writing cache file: {e}")

        # Layer 3: Database (historical)
        if self.enable_db:
            self._store_to_database(data, timestamp)

        # Update stats
        self.stats.api_calls_saved = self.stats.cache_hits
        self._save_stats()

    def _store_to_database(self, data: Dict, timestamp: datetime):
        """Store odds snapshot in historical database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Extract games from API response
            games = data.get("data", {}).get("games", [])
            if not games and isinstance(data.get("data"), list):
                games = data.get("data", [])

            for game in games:
                game_id = game.get("id", "")
                home_team = game.get("home_team", "")
                away_team = game.get("away_team", "")
                commence_time = game.get("commence_time", "")

                # Process each bookmaker
                for bookmaker in game.get("bookmakers", []):
                    bookie_name = bookmaker.get("title", bookmaker.get("key", ""))

                    spread_line = None
                    spread_home_odds = None
                    spread_away_odds = None
                    home_ml = None
                    away_ml = None
                    total_line = None
                    over_odds = None
                    under_odds = None

                    # Extract markets
                    for market in bookmaker.get("markets", []):
                        if market["key"] == "spreads":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == home_team:
                                    spread_line = outcome.get("point")
                                    spread_home_odds = outcome.get("price")
                                else:
                                    spread_away_odds = outcome.get("price")

                        elif market["key"] == "h2h":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == home_team:
                                    home_ml = outcome.get("price")
                                else:
                                    away_ml = outcome.get("price")

                        elif market["key"] == "totals":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == "Over":
                                    total_line = outcome.get("point")
                                    over_odds = outcome.get("price")
                                else:
                                    under_odds = outcome.get("price")

                    # Insert snapshot
                    cursor.execute(
                        """
                        INSERT INTO odds_snapshots (
                            fetch_timestamp, game_id, home_team, away_team,
                            commence_time, bookmaker, spread_line,
                            spread_home_odds, spread_away_odds,
                            home_ml, away_ml, total_line, over_odds, under_odds,
                            raw_data
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            timestamp.isoformat(),
                            game_id,
                            home_team,
                            away_team,
                            commence_time,
                            bookie_name,
                            spread_line,
                            spread_home_odds,
                            spread_away_odds,
                            home_ml,
                            away_ml,
                            total_line,
                            over_odds,
                            under_odds,
                            json.dumps(bookmaker),
                        ),
                    )

            conn.commit()
            conn.close()
            logger.debug(f"[DB WRITE] Stored {len(games)} games to historical database")

        except Exception as e:
            logger.error(f"Error storing to database: {e}")

    def _find_recent_cache_file(
        self, key: str, max_age_minutes: Optional[int] = None
    ) -> Optional[Path]:
        """
        Find the most recent cache file within acceptable age.

        Args:
            key: Cache key
            max_age_minutes: Maximum acceptable age (None = dynamic TTL)

        Returns:
            Path to cache file if found, None otherwise
        """
        # Check for latest symlink first
        latest_link = self.cache_dir / f"{key}_latest.json"
        if latest_link.exists() and latest_link.is_symlink():
            target = latest_link.resolve()
            if target.exists():
                age_seconds = time.time() - target.stat().st_mtime

                # Determine acceptable age
                if max_age_minutes is None:
                    max_age_minutes = self._get_dynamic_ttl(target)

                if age_seconds < (max_age_minutes * 60):
                    return target

        # Fall back to scanning directory
        pattern = f"*_{key}.json"
        cache_files = sorted(
            self.cache_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
        )

        for filepath in cache_files:
            age_seconds = time.time() - filepath.stat().st_mtime

            if max_age_minutes is None:
                max_age_minutes = self._get_dynamic_ttl(filepath)

            if age_seconds < (max_age_minutes * 60):
                return filepath

        return None

    def _get_dynamic_ttl(self, cache_file: Path) -> int:
        """
        Calculate dynamic TTL based on game proximity.

        Returns TTL in minutes.
        """
        try:
            data = json.loads(cache_file.read_text())
            games = data.get("data", {}).get("games", [])
            if not games and isinstance(data.get("data"), list):
                games = data.get("data", [])

            if not games:
                return 30  # Default TTL

            # Find nearest game
            now = datetime.now()
            min_time_to_game = float("inf")

            for game in games:
                commence_str = game.get("commence_time", "")
                if commence_str:
                    try:
                        commence_time = datetime.fromisoformat(
                            commence_str.replace("Z", "+00:00")
                        )
                        commence_time = commence_time.replace(
                            tzinfo=None
                        )  # Remove timezone for comparison
                        time_to_game = (
                            commence_time - now
                        ).total_seconds() / 3600  # Hours
                        min_time_to_game = min(min_time_to_game, time_to_game)
                    except:
                        pass

            # Dynamic TTL based on proximity to kickoff
            if min_time_to_game < 1:
                return 2  # 2 minutes - odds moving fast
            elif min_time_to_game < 6:
                return 15  # 15 minutes - moderate movement
            elif min_time_to_game < 24:
                return 30  # 30 minutes - stable
            else:
                return 60  # 1 hour - very stable

        except Exception as e:
            logger.debug(f"Error calculating dynamic TTL: {e}")
            return 30  # Default

    def get_line_movement(self, game_id: str, lookback_hours: int = 24) -> List[Dict]:
        """
        Get line movement history for a game from database.

        Args:
            game_id: Game ID
            lookback_hours: Hours to look back

        Returns:
            List of historical odds snapshots
        """
        if not self.enable_db:
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff = datetime.now() - timedelta(hours=lookback_hours)

            cursor.execute(
                """
                SELECT 
                    fetch_timestamp,
                    bookmaker,
                    spread_line,
                    spread_home_odds,
                    home_ml,
                    away_ml,
                    total_line,
                    over_odds,
                    under_odds
                FROM odds_snapshots
                WHERE game_id = ?
                  AND fetch_timestamp > ?
                ORDER BY fetch_timestamp ASC
            """,
                (game_id, cutoff.isoformat()),
            )

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.stats.db_hits += 1
            return results

        except Exception as e:
            logger.error(f"Error fetching line movement: {e}")
            return []

    def update_api_usage(
        self, calls_remaining: int, response_time_ms: Optional[int] = None
    ):
        """
        Update API usage tracking.

        Args:
            calls_remaining: Remaining API calls from response header
            response_time_ms: API response time in milliseconds
        """
        self.api_usage["remaining"] = calls_remaining
        self.api_usage["monthly_count"] = 500 - calls_remaining

        # Store in database
        if self.enable_db:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO api_usage (
                        timestamp, endpoint, response_time_ms, calls_remaining
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        datetime.now().isoformat(),
                        "nfl_odds",
                        response_time_ms,
                        calls_remaining,
                    ),
                )

                conn.commit()
                conn.close()
            except Exception as e:
                logger.debug(f"Error logging API usage: {e}")

    def check(self, api_name: str = "odds_api", cost: int = 1) -> bool:
        """
        Check if API call can be made (non-consuming peek).

        Args:
            api_name: Name of the API
            cost: Token cost of the request

        Returns:
            True if call can be made, False otherwise
        """
        return self.token_bucket.check(api_name, cost)

    def can_call_api(self, api_name: str = "odds_api", cost: int = 1) -> bool:
        """
        Check if API can be called (wrapper for check).

        Args:
            api_name: Name of the API
            cost: Token cost of the request

        Returns:
            True if call can be made, False otherwise
        """
        return self.check(api_name, cost)

    def record_api_call(self, api_name: str = "odds_api", cost: int = 1) -> bool:
        """
        Record an API call (consume tokens).

        Args:
            api_name: Name of the API
            cost: Token cost of the request

        Returns:
            True if call recorded, False if rate limited
        """
        success = self.token_bucket.record_api_call(api_name, cost)

        if success:
            # Update legacy tracking
            self.api_usage["remaining"] = max(
                0, self.api_usage.get("remaining", 500) - cost
            )
            self.api_usage["monthly_count"] = (
                self.api_usage.get("monthly_count", 0) + cost
            )

        return success

    def get_rate_limit_stats(self) -> Dict:
        """
        Get rate limit statistics for all APIs.

        Returns:
            Dictionary with rate limit stats
        """
        bucket_stats = self.token_bucket.get_rate_limit_stats()

        # Merge with legacy stats
        return {
            "token_buckets": bucket_stats,
            "legacy": {
                "remaining": self.api_usage.get("remaining", 500),
                "monthly_count": self.api_usage.get("monthly_count", 0),
                "limit": self.api_usage.get("limit", 500),
            },
        }

    def should_fetch_fresh(self) -> bool:
        """
        Determine if we should fetch fresh data based on rate limits.

        Returns:
            True if safe to fetch, False if approaching limit
        """
        # Use token bucket if available
        if self.token_bucket:
            status = self.token_bucket.get_status("odds_api")
            if status == RateLimitStatus.EXHAUSTED:
                return False
            if status == RateLimitStatus.CRITICAL:
                logger.warning("Rate limit critical - using cache")
                return False

        # Fallback to legacy tracking
        remaining = self.api_usage.get("remaining", 500)

        if remaining < 10:
            logger.warning(f"Rate limit critical: {remaining} calls remaining")
            return False
        elif remaining < 50:
            logger.warning(f"Rate limit low: {remaining} calls remaining")
            # Still allow but warn
            return True

        return True

    def _save_stats(self):
        """Save cache statistics to file."""
        try:
            self.stats_file.write_text(json.dumps(self.stats.to_dict(), indent=2))
        except Exception as e:
            logger.debug(f"Error saving cache stats: {e}")

    def get_stats(self) -> Dict:
        """Get cache performance statistics."""
        return self.stats.to_dict()

    def clear_memory(self):
        """Clear memory cache only."""
        self._memory.clear()
        self._memory_timestamps.clear()
        logger.info("Memory cache cleared")

    def clear_files(self, older_than_hours: int = 24):
        """
        Clear old cache files.

        Args:
            older_than_hours: Remove files older than this many hours
        """
        cutoff = time.time() - (older_than_hours * 3600)
        removed = 0

        for filepath in self.cache_dir.glob("*.json"):
            if (
                filepath.name.endswith("_latest.json")
                or filepath.name == "cache_stats.json"
            ):
                continue

            if filepath.stat().st_mtime < cutoff:
                filepath.unlink()
                removed += 1

        logger.info(f"Removed {removed} old cache files (>{older_than_hours}h)")

    def clear_all(self):
        """Clear all caches (memory + files). Database preserved."""
        self.clear_memory()

        for filepath in self.cache_dir.glob("*.json"):
            if filepath.name != "cache_stats.json":
                filepath.unlink()

        logger.info("All caches cleared")

    def invalidate(self, key: str = "nfl_odds"):
        """
        Force invalidate a specific cache key.

        Args:
            key: Cache key to invalidate
        """
        # Remove from memory
        if key in self._memory:
            del self._memory[key]
            del self._memory_timestamps[key]

        # Remove latest file link
        latest_link = self.cache_dir / f"{key}_latest.json"
        if latest_link.exists():
            latest_link.unlink()

        logger.info(f"Cache invalidated: {key}")
