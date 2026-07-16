"""Durable, fail-closed strategy registry.

The registry is an operator review ledger, not proof that a betting strategy is
profitable. Persistence is atomic, concurrent changes are detected, corrupt
files fail closed, and all mutations are validated before the on-disk state is
replaced.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "data" / "strategies" / "registry.json"
REGISTRY_FORMAT_VERSION = 1
LOCK_WAIT_SECONDS = 5.0
STALE_LOCK_SECONDS = 60.0


def utc_now_iso() -> str:
    """Return an unambiguous UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def normalize_pattern(text: str) -> str:
    """Normalize free-form text for fuzzy duplicate detection."""

    if not text:
        return ""
    normalized = text.lower()
    normalized = re.sub(r"\s*\(v\d+\)|\s*v\d+$", "", normalized)
    normalized = re.sub(r"[_\-:,()]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


class StrategyRegistryError(RuntimeError):
    """Base class for registry integrity and persistence failures."""


class RegistryCorruptionError(StrategyRegistryError):
    """Raised when an existing registry cannot be parsed or validated."""


class RegistryPersistenceError(StrategyRegistryError):
    """Raised when an atomic registry write cannot be completed."""


class RegistryConflictError(StrategyRegistryError):
    """Raised when another process changed the registry after it was loaded."""


class StrategyStatus(str, Enum):
    """Operator review state."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class EvidenceStatus(str, Enum):
    """Evidence maturity; independent from the operator review state."""

    UNVERIFIED = "unverified"
    RESEARCH_ONLY = "research_only"
    OUT_OF_SAMPLE_VALIDATED = "out_of_sample_validated"
    PAPER_TRADING = "paper_trading"
    LIVE_VALIDATED = "live_validated"


DEPLOYABLE_EVIDENCE_STATUSES = {
    EvidenceStatus.PAPER_TRADING.value,
    EvidenceStatus.LIVE_VALIDATED.value,
}


@dataclass
class Strategy:
    """One versioned strategy record."""

    strategy_id: str
    name: str
    description: str
    pattern: str
    win_rate: float
    roi: float
    sample_size: int
    edge: float
    sharpe_ratio: Optional[float] = None
    status: str = StrategyStatus.PENDING.value
    date_discovered: Optional[str] = None
    date_reviewed: Optional[str] = None
    reviewer_notes: str = ""
    conditions: Optional[Dict[str, Any]] = None
    version: int = 1
    previous_version_id: Optional[str] = None
    evidence_status: str = EvidenceStatus.UNVERIFIED.value
    evidence: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.date_discovered is None:
            self.date_discovered = utc_now_iso()
        if self.conditions is None:
            self.conditions = {}
        if self.evidence is None:
            self.evidence = {}
        self.validate()

    def validate(self) -> None:
        """Validate the complete record before it can enter the registry."""

        for field_name in ("strategy_id", "name", "description", "pattern"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")

        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", self.strategy_id):
            raise ValueError(
                "strategy_id must start with an alphanumeric character and contain "
                "only lowercase letters, digits, underscores, periods, or hyphens"
            )

        numeric_fields = {
            "win_rate": self.win_rate,
            "roi": self.roi,
            "edge": self.edge,
        }
        if self.sharpe_ratio is not None:
            numeric_fields["sharpe_ratio"] = self.sharpe_ratio
        for field_name, value in numeric_fields.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"{field_name} must be finite")

        if not 0 <= float(self.win_rate) <= 100:
            raise ValueError("win_rate must be between 0 and 100")
        if float(self.roi) < -100:
            raise ValueError("roi cannot be lower than -100%")
        if not -100 <= float(self.edge) <= 100:
            raise ValueError("edge must be between -100 and 100")

        if isinstance(self.sample_size, bool) or not isinstance(self.sample_size, int):
            raise ValueError("sample_size must be an integer")
        if self.sample_size < 0:
            raise ValueError("sample_size cannot be negative")

        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise ValueError("version must be an integer")
        if self.version < 1:
            raise ValueError("version must be at least 1")

        valid_statuses = {status.value for status in StrategyStatus}
        if self.status not in valid_statuses:
            raise ValueError(f"invalid strategy status: {self.status}")

        valid_evidence_statuses = {status.value for status in EvidenceStatus}
        if self.evidence_status not in valid_evidence_statuses:
            raise ValueError(f"invalid evidence status: {self.evidence_status}")

        if not isinstance(self.conditions, dict):
            raise ValueError("conditions must be a dictionary")
        if not isinstance(self.evidence, dict):
            raise ValueError("evidence must be a dictionary")
        if self.previous_version_id == self.strategy_id:
            raise ValueError("previous_version_id cannot reference the same strategy")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Strategy":
        if not isinstance(data, dict):
            raise ValueError("strategy payload must be an object")
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise ValueError(f"unknown strategy fields: {', '.join(unknown)}")
        return cls(**data)

    def similarity_score(self, other_pattern: str, other_name: str = None) -> float:
        pattern_score = SequenceMatcher(
            None, normalize_pattern(self.pattern), normalize_pattern(other_pattern)
        ).ratio()
        if other_name:
            name_score = SequenceMatcher(
                None, normalize_pattern(self.name), normalize_pattern(other_name)
            ).ratio()
            return max(pattern_score, name_score)
        return pattern_score

    def is_similar_to(
        self, other_pattern: str, other_name: str = None, threshold: float = 0.85
    ) -> bool:
        return self.similarity_score(other_pattern, other_name) >= threshold


class StrategyRegistry:
    """Validated registry with atomic writes and concurrency control."""

    MUTABLE_FIELDS = {
        "name",
        "description",
        "pattern",
        "win_rate",
        "roi",
        "sample_size",
        "edge",
        "sharpe_ratio",
        "status",
        "date_reviewed",
        "reviewer_notes",
        "conditions",
        "evidence_status",
        "evidence",
    }

    def __init__(self, registry_path: str | Path | None = None):
        self.registry_path = (
            DEFAULT_REGISTRY_PATH if registry_path is None else Path(registry_path)
        )
        self.strategies: Dict[str, Strategy] = {}
        self._fingerprint: Optional[str] = None
        self._load_registry()

    @staticmethod
    def _hash_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _current_file_fingerprint(self) -> Optional[str]:
        if not self.registry_path.exists():
            return None
        return self._hash_bytes(self.registry_path.read_bytes())

    def _deserialize(self, payload: Any) -> Dict[str, Strategy]:
        if not isinstance(payload, dict):
            raise RegistryCorruptionError("registry root must be a JSON object")

        if "_meta" in payload or "strategies" in payload:
            meta = payload.get("_meta")
            strategy_payload = payload.get("strategies")
            if not isinstance(meta, dict) or not isinstance(strategy_payload, dict):
                raise RegistryCorruptionError(
                    "versioned registry requires object-valued _meta and strategies"
                )
            version = meta.get("format_version")
            if version != REGISTRY_FORMAT_VERSION:
                raise RegistryCorruptionError(
                    f"unsupported registry format version: {version}"
                )
        else:
            strategy_payload = payload

        loaded: Dict[str, Strategy] = {}
        for strategy_id, strategy_data in strategy_payload.items():
            if not isinstance(strategy_id, str):
                raise RegistryCorruptionError("strategy keys must be strings")
            try:
                strategy = Strategy.from_dict(strategy_data)
            except (TypeError, ValueError) as exc:
                raise RegistryCorruptionError(
                    f"invalid strategy {strategy_id!r}: {exc}"
                ) from exc
            if strategy.strategy_id != strategy_id:
                raise RegistryCorruptionError(
                    f"strategy key {strategy_id!r} does not match embedded id "
                    f"{strategy.strategy_id!r}"
                )
            loaded[strategy_id] = strategy
        return loaded

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            self.strategies = {}
            self._fingerprint = None
            self._persist({})
            return

        raw = self.registry_path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryCorruptionError(
                f"registry is unreadable; refusing to replace it: {self.registry_path}"
            ) from exc

        self.strategies = self._deserialize(payload)
        self._fingerprint = self._hash_bytes(raw)
        logger.info(
            "Loaded %s strategies from %s", len(self.strategies), self.registry_path
        )

    def reload(self) -> None:
        """Reload the registry after resolving an external-change conflict."""

        self._load_registry()

    @contextmanager
    def _exclusive_lock(self):
        """Serialize writers with an atomic cross-platform lock file."""

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.registry_path.with_name(f".{self.registry_path.name}.lock")
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        acquired = False

        while not acquired:
            try:
                descriptor = os.open(
                    lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(f"pid={os.getpid()} acquired={utc_now_iso()}\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                acquired = True
            except FileExistsError as exc:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                    if age > STALE_LOCK_SECONDS:
                        lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise RegistryConflictError(
                        f"registry is locked by another writer: {lock_path}"
                    ) from exc
                time.sleep(0.05)
            except OSError as exc:
                raise RegistryPersistenceError(
                    f"could not acquire registry lock: {exc}"
                ) from exc

        try:
            yield
        finally:
            if acquired:
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("Could not remove registry lock %s", lock_path)

    def _serialize(self, strategies: Dict[str, Strategy]) -> Dict[str, Any]:
        return {
            "_meta": {
                "format_version": REGISTRY_FORMAT_VERSION,
                "updated_at": utc_now_iso(),
                "strategy_count": len(strategies),
            },
            "strategies": {
                strategy_id: strategy.to_dict()
                for strategy_id, strategy in sorted(strategies.items())
            },
        }

    def _persist(self, strategies: Dict[str, Strategy]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self._exclusive_lock():
            current_fingerprint = self._current_file_fingerprint()
            if current_fingerprint != self._fingerprint:
                raise RegistryConflictError(
                    "registry changed after it was loaded; reload before writing"
                )

            payload = json.dumps(
                self._serialize(strategies),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ).encode("utf-8")

            fd: Optional[int] = None
            temp_path: Optional[Path] = None
            try:
                fd, temp_name = tempfile.mkstemp(
                    prefix=f".{self.registry_path.name}.",
                    suffix=".tmp",
                    dir=self.registry_path.parent,
                )
                temp_path = Path(temp_name)
                with os.fdopen(fd, "wb") as handle:
                    fd = None
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.registry_path)
                temp_path = None
                self._fingerprint = self._hash_bytes(payload)
            except StrategyRegistryError:
                raise
            except OSError as exc:
                raise RegistryPersistenceError(
                    f"could not atomically persist registry: {exc}"
                ) from exc
            finally:
                if fd is not None:
                    os.close(fd)
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        logger.exception(
                            "Could not remove temporary registry file %s", temp_path
                        )

    def _commit(self, strategies: Dict[str, Strategy]) -> None:
        self._persist(strategies)
        self.strategies = strategies

    def _save_registry(self) -> None:
        """Compatibility wrapper; raises on failure instead of pretending success."""

        self._persist(self.strategies)

    def add_strategy(
        self, strategy: Strategy, skip_duplicate_check: bool = False
    ) -> tuple[bool, Optional[str]]:
        try:
            strategy.validate()
            if not skip_duplicate_check:
                duplicate = self.find_similar_strategy(strategy.pattern, strategy.name)
                if duplicate:
                    return (
                        False,
                        "Similar strategy already exists: "
                        f"{duplicate.strategy_id} ({duplicate.name})",
                    )
            if strategy.strategy_id in self.strategies:
                return False, f"Strategy ID {strategy.strategy_id} already exists"

            updated = deepcopy(self.strategies)
            updated[strategy.strategy_id] = deepcopy(strategy)
            self._commit(updated)
            return True, f"Strategy {strategy.strategy_id} added successfully"
        except (StrategyRegistryError, ValueError) as exc:
            logger.error("Could not add strategy %s: %s", strategy.strategy_id, exc)
            return False, str(exc)

    def update_strategy(self, strategy_id: str, **updates: Any) -> tuple[bool, str]:
        if strategy_id not in self.strategies:
            return False, f"Strategy {strategy_id} not found"

        unknown = sorted(set(updates) - self.MUTABLE_FIELDS)
        if unknown:
            return False, f"Unsupported update fields: {', '.join(unknown)}"

        try:
            candidate_data = self.strategies[strategy_id].to_dict()
            candidate_data.update(updates)
            candidate = Strategy.from_dict(candidate_data)
            updated = deepcopy(self.strategies)
            updated[strategy_id] = candidate
            self._commit(updated)
            return True, f"Strategy {strategy_id} updated successfully"
        except (StrategyRegistryError, ValueError) as exc:
            logger.error("Could not update strategy %s: %s", strategy_id, exc)
            return False, str(exc)

    def accept_strategy(self, strategy_id: str, notes: str = "") -> tuple[bool, str]:
        return self.update_strategy(
            strategy_id,
            status=StrategyStatus.ACCEPTED.value,
            date_reviewed=utc_now_iso(),
            reviewer_notes=notes,
        )

    def reject_strategy(self, strategy_id: str, notes: str = "") -> tuple[bool, str]:
        return self.update_strategy(
            strategy_id,
            status=StrategyStatus.REJECTED.value,
            date_reviewed=utc_now_iso(),
            reviewer_notes=notes,
        )

    def archive_strategy(self, strategy_id: str, notes: str = "") -> tuple[bool, str]:
        return self.update_strategy(
            strategy_id,
            status=StrategyStatus.ARCHIVED.value,
            date_reviewed=utc_now_iso(),
            reviewer_notes=notes,
        )

    def get_strategies_by_status(self, status: StrategyStatus) -> List[Strategy]:
        return [
            strategy
            for strategy in self.strategies.values()
            if strategy.status == status.value
        ]

    def get_pending_strategies(self) -> List[Strategy]:
        return self.get_strategies_by_status(StrategyStatus.PENDING)

    def get_accepted_strategies(self) -> List[Strategy]:
        return self.get_strategies_by_status(StrategyStatus.ACCEPTED)

    def get_rejected_strategies(self) -> List[Strategy]:
        return self.get_strategies_by_status(StrategyStatus.REJECTED)

    def get_deployable_strategies(self) -> List[Strategy]:
        """Return accepted strategies with paper/live evidence maturity."""

        return [
            strategy
            for strategy in self.get_accepted_strategies()
            if strategy.evidence_status in DEPLOYABLE_EVIDENCE_STATUSES
        ]

    def find_similar_strategy(
        self, pattern: str, name: str = None, threshold: float = 0.85
    ) -> Optional[Strategy]:
        best_match: Optional[Strategy] = None
        best_score = 0.0
        for strategy in self.strategies.values():
            score = strategy.similarity_score(pattern, name)
            if score >= threshold and score > best_score:
                best_match = strategy
                best_score = score
        return best_match

    def check_for_updates(
        self, pattern: str, new_metrics: Dict[str, Any]
    ) -> Optional[Dict]:
        similar = self.find_similar_strategy(pattern)
        if not similar:
            return None

        old_metrics = {
            "win_rate": similar.win_rate,
            "roi": similar.roi,
            "sample_size": similar.sample_size,
            "edge": similar.edge,
        }
        improvements: Dict[str, Dict[str, float]] = {}
        for key in ("win_rate", "roi", "edge"):
            if key not in new_metrics:
                continue
            old_value = float(old_metrics[key])
            new_value = float(new_metrics[key])
            if new_value > old_value:
                improvements[key] = {
                    "old": old_value,
                    "new": new_value,
                    "change": new_value - old_value,
                    "pct_change": (
                        ((new_value - old_value) / abs(old_value) * 100)
                        if old_value != 0
                        else 0.0
                    ),
                }
        if not improvements:
            return None
        return {
            "strategy_id": similar.strategy_id,
            "strategy_name": similar.name,
            "old_metrics": old_metrics,
            "new_metrics": new_metrics,
            "improvements": improvements,
        }

    def create_strategy_version(
        self, original_id: str, updated_metrics: Dict[str, Any]
    ) -> tuple[bool, str]:
        if original_id not in self.strategies:
            return False, f"Original strategy {original_id} not found"

        allowed_metrics = {"win_rate", "roi", "sample_size", "edge", "sharpe_ratio"}
        unknown = sorted(set(updated_metrics) - allowed_metrics)
        if unknown:
            return False, f"Unsupported metric fields: {', '.join(unknown)}"

        try:
            original = self.strategies[original_id]
            new_version = original.version + 1
            base_id = re.sub(r"_v\d+$", "", original.strategy_id)
            new_id = f"{base_id}_v{new_version}"
            if new_id in self.strategies:
                return False, f"Strategy ID {new_id} already exists"

            new_strategy = Strategy(
                strategy_id=new_id,
                name=f"{re.sub(r' \(v\d+\)$', '', original.name)} (v{new_version})",
                description=original.description,
                pattern=original.pattern,
                win_rate=updated_metrics.get("win_rate", original.win_rate),
                roi=updated_metrics.get("roi", original.roi),
                sample_size=updated_metrics.get("sample_size", original.sample_size),
                edge=updated_metrics.get("edge", original.edge),
                sharpe_ratio=updated_metrics.get("sharpe_ratio", original.sharpe_ratio),
                status=StrategyStatus.PENDING.value,
                conditions=deepcopy(original.conditions),
                version=new_version,
                previous_version_id=original_id,
                evidence_status=EvidenceStatus.UNVERIFIED.value,
                evidence={
                    "supersedes": original_id,
                    "reason": "metrics updated; independent revalidation required",
                },
            )

            archived_data = original.to_dict()
            archived_data.update(
                {
                    "status": StrategyStatus.ARCHIVED.value,
                    "date_reviewed": utc_now_iso(),
                    "reviewer_notes": f"Superseded by {new_id}",
                }
            )
            archived = Strategy.from_dict(archived_data)

            updated = deepcopy(self.strategies)
            updated[original_id] = archived
            updated[new_id] = new_strategy
            self._commit(updated)
            return True, f"Strategy {new_id} added successfully"
        except (StrategyRegistryError, ValueError) as exc:
            logger.error("Could not version strategy %s: %s", original_id, exc)
            return False, str(exc)

    def get_all_strategies(self) -> List[Strategy]:
        return list(self.strategies.values())

    def delete_strategy(self, strategy_id: str) -> tuple[bool, str]:
        if strategy_id not in self.strategies:
            return False, f"Strategy {strategy_id} not found"
        try:
            updated = deepcopy(self.strategies)
            del updated[strategy_id]
            self._commit(updated)
            return True, f"Strategy {strategy_id} deleted"
        except StrategyRegistryError as exc:
            logger.error("Could not delete strategy %s: %s", strategy_id, exc)
            return False, str(exc)

    def get_stats(self) -> Dict[str, int]:
        return {
            "total": len(self.strategies),
            "pending": len(self.get_pending_strategies()),
            "accepted": len(self.get_accepted_strategies()),
            "rejected": len(self.get_rejected_strategies()),
            "archived": len(self.get_strategies_by_status(StrategyStatus.ARCHIVED)),
            "deployable": len(self.get_deployable_strategies()),
        }
