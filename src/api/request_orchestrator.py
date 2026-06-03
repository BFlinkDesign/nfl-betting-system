"""
Request Orchestrator

Manages API requests with priority queuing, rate limiting, and intelligent batching.
Integrates with OddsCache for caching and rate limit protection.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Empty, PriorityQueue
from typing import Any, Callable, Dict, List, Optional

from src.utils.odds_cache import OddsCache

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Request priority levels."""

    CRITICAL = 1  # Game starting soon, user request
    HIGH = 2  # Scheduled refresh, important update
    NORMAL = 3  # Regular refresh, background task
    LOW = 4  # Prefetch, non-urgent


@dataclass
class PriorityRequest:
    """A prioritized API request."""

    endpoint: str
    params: Dict[str, Any]
    priority: Priority
    callback: Callable
    api_name: str = "odds_api"
    timeout: int = 30
    retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    request_id: str = field(default_factory=lambda: f"req_{int(time.time() * 1000)}")

    def __lt__(self, other):
        """Compare by priority (lower number = higher priority)."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # If same priority, earlier request first
        return self.created_at < other.created_at


class CircuitBreaker:
    """Circuit breaker pattern for API failure handling."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
        self.lock = threading.Lock()

    def record_success(self):
        """Record successful request."""
        with self.lock:
            self.failure_count = 0
            self.state = "closed"

    def record_failure(self):
        """Record failed request."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )

    def can_proceed(self) -> bool:
        """Check if request can proceed."""
        with self.lock:
            if self.state == "closed":
                return True

            if self.state == "open":
                # Check if timeout has passed
                if (
                    self.last_failure_time
                    and (time.time() - self.last_failure_time) > self.timeout
                ):
                    self.state = "half_open"
                    logger.info("Circuit breaker entering half-open state")
                    return True
                return False

            # half_open state
            return True


class RequestOrchestrator:
    """
    Orchestrates API requests with priority queuing and rate limiting.

    Features:
    - Priority queue for request ordering
    - Rate limit protection via token bucket
    - Circuit breaker for failure handling
    - Request deduplication
    - Automatic retries with exponential backoff
    """

    def __init__(self, cache: Optional[OddsCache] = None):
        """
        Initialize request orchestrator.

        Args:
            cache: OddsCache instance for caching and rate limiting
        """
        self.cache = cache or OddsCache()
        self.token_bucket = self.cache.token_bucket

        # Initialize API clients (lazy loading)
        self._espn_client = None
        self._noaa_client = None

        # Priority queue for requests
        self.queue: PriorityQueue = PriorityQueue()

        # Request tracking
        self.in_flight: Dict[str, PriorityRequest] = {}
        self.completed: Dict[str, Any] = {}
        self.failed: Dict[str, Exception] = {}

        # Deduplication
        self.pending_requests: Dict[str, List[Callable]] = (
            {}
        )  # endpoint+params -> callbacks

        # Circuit breakers per API
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Control
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        logger.info("RequestOrchestrator initialized")

    def _get_circuit_breaker(self, api_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for API."""
        if api_name not in self.circuit_breakers:
            self.circuit_breakers[api_name] = CircuitBreaker()
        return self.circuit_breakers[api_name]

    def _deduplicate_key(self, endpoint: str, params: Dict) -> str:
        """Generate deduplication key."""
        # Sort params for consistent key
        sorted_params = sorted(params.items())
        return f"{endpoint}:{str(sorted_params)}"

    def enqueue(self, request: PriorityRequest) -> str:
        """
        Add request to priority queue.

        Args:
            request: PriorityRequest to enqueue

        Returns:
            Request ID
        """
        dedup_key = self._deduplicate_key(request.endpoint, request.params)

        with self.lock:
            # Check for duplicate request
            if dedup_key in self.pending_requests:
                logger.debug(f"Deduplicating request {request.request_id}")
                self.pending_requests[dedup_key].append(request.callback)
                return request.request_id

            # New request
            self.pending_requests[dedup_key] = [request.callback]
            self.queue.put(request)

            logger.debug(
                f"Enqueued request {request.request_id} (priority={request.priority.name})"
            )

            return request.request_id

    def _fetch_from_api(self, request: PriorityRequest) -> Any:
        """
        Actually make API call.

        Args:
            request: Request to execute

        Returns:
            API response data
        """
        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(request.api_name)
        if not circuit_breaker.can_proceed():
            raise Exception(f"Circuit breaker open for {request.api_name}")

        # Check rate limits
        if not self.token_bucket.can_call_api(request.api_name):
            raise Exception(f"Rate limit exceeded for {request.api_name}")

        # Check cache first
        cache_key = f"{request.endpoint}_{str(request.params)}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for {request.request_id}")
            return cached_data.get("data")

        # Make API call - route to appropriate API client
        if "odds" in request.endpoint.lower() or request.api_name == "odds_api":
            # The Odds API
            try:
                import sys
                from pathlib import Path

                sys.path.append(str(Path(__file__).parent.parent.parent))
                from agents.api_integrations import TheOddsAPI

                api_client = TheOddsAPI(use_cache=True)

                # Extract method from endpoint
                if (
                    "nfl_odds" in request.endpoint
                    or "americanfootball_nfl/odds" in request.endpoint
                ):
                    regions = request.params.get("regions", "us")
                    markets = request.params.get("markets", "h2h,spreads,totals")
                    return api_client.get_nfl_odds(regions=regions, markets=markets)
                else:
                    raise NotImplementedError(
                        f"Odds API endpoint not implemented: {request.endpoint}"
                    )
            except ImportError:
                logger.error(
                    "Could not import TheOddsAPI - check agents/api_integrations.py"
                )
                raise

        elif "espn" in request.endpoint.lower() or request.api_name == "espn_api":
            # ESPN API (FREE - No Key Required)
            try:
                from src.api.espn_client import ESPNClient

                if not hasattr(self, "_espn_client"):
                    self._espn_client = ESPNClient(cache=self.cache)

                endpoint = request.params.get("endpoint", "scoreboard")

                if endpoint == "scoreboard":
                    return self._espn_client.get_scoreboard(
                        dates=request.params.get("dates")
                    )
                elif endpoint == "game_summary":
                    return self._espn_client.get_game_summary(
                        request.params.get("game_id", "")
                    )
                elif endpoint == "teams":
                    return {"teams": self._espn_client.get_teams()}
                elif endpoint == "team_schedule":
                    return self._espn_client.get_team_schedule(
                        request.params.get("team_abbr", ""),
                        request.params.get("season"),
                    )
                elif endpoint == "standings":
                    return self._espn_client.get_standings()
                elif endpoint == "news":
                    return {"articles": self._espn_client.get_news()}
                else:
                    raise NotImplementedError(
                        f"ESPN endpoint not implemented: {endpoint}"
                    )
            except Exception as e:
                logger.error(f"ESPN API error: {e}")
                raise

        elif "noaa" in request.endpoint.lower() or request.api_name == "noaa_api":
            # NOAA Weather API (FREE - No Key Required)
            try:
                from datetime import datetime

                from src.api.noaa_client import NOAAClient

                if not hasattr(self, "_noaa_client"):
                    self._noaa_client = NOAAClient(cache=self.cache)

                endpoint = request.params.get("endpoint", "forecast")

                if endpoint == "forecast":
                    return self._noaa_client.get_forecast_for_location(
                        request.params.get("latitude", 0),
                        request.params.get("longitude", 0),
                    )
                elif endpoint == "hourly_forecast":
                    return self._noaa_client.get_hourly_forecast(
                        request.params.get("latitude", 0),
                        request.params.get("longitude", 0),
                    )
                elif endpoint == "current":
                    return self._noaa_client.get_current_conditions(
                        request.params.get("latitude", 0),
                        request.params.get("longitude", 0),
                    )
                elif endpoint == "game_forecast":
                    # Parse game_time if string
                    game_time = request.params.get("game_time")
                    if isinstance(game_time, str):
                        game_time = datetime.fromisoformat(
                            game_time.replace("Z", "+00:00")
                        )

                    return self._noaa_client.get_game_day_forecast(
                        request.params.get("stadium_name", ""),
                        (
                            request.params.get("latitude", 0),
                            request.params.get("longitude", 0),
                        ),
                        game_time,
                    )
                else:
                    raise NotImplementedError(
                        f"NOAA endpoint not implemented: {endpoint}"
                    )
            except Exception as e:
                logger.error(f"NOAA API error: {e}")
                raise

        else:
            raise NotImplementedError(
                f"API endpoint not implemented: {request.endpoint}"
            )

    def _process_request(self, request: PriorityRequest):
        """Process a single request."""
        dedup_key = self._deduplicate_key(request.endpoint, request.params)

        try:
            # Fetch data
            data = self._fetch_from_api(request)

            # Record success
            circuit_breaker = self._get_circuit_breaker(request.api_name)
            circuit_breaker.record_success()

            # Consume tokens
            self.token_bucket.record_api_call(request.api_name)

            # Cache result
            cache_key = f"{request.endpoint}_{str(request.params)}"
            self.cache.set(data, cache_key)

            # Call all callbacks for this request (deduplication)
            callbacks = self.pending_requests.pop(dedup_key, [])
            for callback in callbacks:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            # Track completion
            with self.lock:
                self.completed[request.request_id] = data
                if request.request_id in self.in_flight:
                    del self.in_flight[request.request_id]

            logger.info(f"Completed request {request.request_id}")

        except Exception as e:
            # Record failure
            circuit_breaker = self._get_circuit_breaker(request.api_name)
            circuit_breaker.record_failure()

            # Retry logic
            if request.retries > 0:
                request.retries -= 1
                wait_time = 2 ** (3 - request.retries)  # Exponential backoff
                logger.warning(
                    f"Request {request.request_id} failed, retrying in {wait_time}s ({request.retries} left)"
                )
                time.sleep(wait_time)
                self.enqueue(request)
            else:
                # Failed permanently
                with self.lock:
                    self.failed[request.request_id] = e
                    if request.request_id in self.in_flight:
                        del self.in_flight[request.request_id]
                    self.pending_requests.pop(dedup_key, None)

                logger.error(f"Request {request.request_id} failed permanently: {e}")

    def _worker_loop(self):
        """Worker thread that processes requests."""
        logger.info("Request orchestrator worker started")

        while self.running:
            try:
                # Get next request (with timeout)
                try:
                    request = self.queue.get(timeout=1)
                except Empty:
                    continue

                # Track in-flight
                with self.lock:
                    self.in_flight[request.request_id] = request

                # Process request
                self._process_request(request)

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1)

        logger.info("Request orchestrator worker stopped")

    def start(self):
        """Start the orchestrator worker thread."""
        if self.running:
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Request orchestrator started")

    def stop(self, timeout: int = 30):
        """Stop the orchestrator."""
        if not self.running:
            return

        logger.info("Stopping request orchestrator...")
        self.running = False

        if self.worker_thread:
            self.worker_thread.join(timeout=timeout)

        logger.info("Request orchestrator stopped")

    def get_stats(self) -> Dict:
        """Get orchestrator statistics."""
        with self.lock:
            return {
                "queue_size": self.queue.qsize(),
                "in_flight": len(self.in_flight),
                "completed": len(self.completed),
                "failed": len(self.failed),
                "circuit_breakers": {
                    api: {"state": cb.state, "failures": cb.failure_count}
                    for api, cb in self.circuit_breakers.items()
                },
                "rate_limits": self.token_bucket.get_rate_limit_stats(),
            }
