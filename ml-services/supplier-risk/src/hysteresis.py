"""
Hysteresis state machine for Supplier Risk tier transitions.

Provides an explicit, testable state machine that tracks independent per-supplier
accepted risk tiers, enforces configurable enter/exit boundary thresholds to
eliminate score chatter, requires minimum supporting evidence before accepting
tier transitions, and emits standard score-change events.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import math
from typing import Any, Deque, Dict, List, Optional, Tuple

from src.config import (
    DEFAULT_HYSTERESIS_ENTER_HIGH,
    DEFAULT_HYSTERESIS_ENTER_MEDIUM,
    DEFAULT_HYSTERESIS_EXIT_HIGH,
    DEFAULT_HYSTERESIS_EXIT_MEDIUM,
    DEFAULT_HYSTERESIS_MIN_EVIDENCE,
    DEFAULT_TIER_LOW_CEILING,
    DEFAULT_TIER_MEDIUM_CEILING,
    Settings,
)
from src.events import (
    EventPublisher,
    build_score_changed_event,
    format_supporting_articles,
    map_tier_to_event_tier,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Hysteresis Configuration
# ------------------------------------------------------------------


@dataclass(frozen=True)
class HysteresisConfig:
    """
    Configuration for risk tier hysteresis thresholds and evidence gating.

    Threshold Design & Exact Boundary Semantics:
    -------------------------------------------
    Nominal Tiers on 0-100 scale:
      - Low:    [0.0, 60.0)
      - Medium: [60.0, 72.0)
      - High:   [72.0, 100.0]

    Enter / Exit Hysteresis Thresholds:
      - enter_medium_threshold (default 62.0):
          Score required to move upward into Medium from Low (inclusive, >= 62.0).
          A score of 61.99 remains Low.
      - exit_medium_threshold (default 58.0):
          Score required to drop downward into Low from Medium (strictly below, < 58.0).
          A score of 58.00 remains Medium.
      - enter_high_threshold (default 74.0):
          Score required to move upward into High from Medium or Low (inclusive, >= 74.0).
          A score of 73.99 remains Medium.
      - exit_high_threshold (default 70.0):
          Score required to drop downward into Medium from High (strictly below, < 70.0).
          A score of 70.00 remains High.

    Deadbands:
      - Low-Medium Deadband: [58.0, 62.0)
          Within this zone, scores fluctuating near 60.0 retain the previous accepted tier.
      - Medium-High Deadband: [70.0, 74.0)
          Within this zone, scores fluctuating near 72.0 retain the previous accepted tier.
    """

    tier_low_ceiling: float = DEFAULT_TIER_LOW_CEILING
    tier_medium_ceiling: float = DEFAULT_TIER_MEDIUM_CEILING
    enter_medium_threshold: float = DEFAULT_HYSTERESIS_ENTER_MEDIUM
    exit_medium_threshold: float = DEFAULT_HYSTERESIS_EXIT_MEDIUM
    enter_high_threshold: float = DEFAULT_HYSTERESIS_ENTER_HIGH
    exit_high_threshold: float = DEFAULT_HYSTERESIS_EXIT_HIGH
    # Minimum number of articles that individually point toward the new tier.
    # 0 disables evidence gating (used for the "hysteresis only" comparison).
    min_evidence: int = DEFAULT_HYSTERESIS_MIN_EVIDENCE
    # The first accepted tier also needs min_evidence articles in the window.
    require_min_evidence_for_initial: bool = True
    # Number of top supporting articles carried in the event payload.
    top_articles: int = 3

    def __post_init__(self) -> None:
        """Validate threshold relationships and positive constraints."""
        if not (0.0 <= self.exit_medium_threshold <= self.tier_low_ceiling):
            raise ValueError(
                f"exit_medium_threshold ({self.exit_medium_threshold}) must satisfy "
                f"0.0 <= exit_medium_threshold <= tier_low_ceiling ({self.tier_low_ceiling})"
            )
        if not (self.tier_low_ceiling <= self.enter_medium_threshold):
            raise ValueError(
                f"enter_medium_threshold ({self.enter_medium_threshold}) must be >= "
                f"tier_low_ceiling ({self.tier_low_ceiling})"
            )
        if not (self.enter_medium_threshold < self.exit_high_threshold):
            raise ValueError(
                f"enter_medium_threshold ({self.enter_medium_threshold}) must be < "
                f"exit_high_threshold ({self.exit_high_threshold})"
            )
        if not (self.exit_high_threshold <= self.tier_medium_ceiling <= self.enter_high_threshold <= 100.0):
            raise ValueError(
                f"Thresholds must satisfy exit_high ({self.exit_high_threshold}) <= "
                f"tier_medium_ceiling ({self.tier_medium_ceiling}) <= "
                f"enter_high ({self.enter_high_threshold}) <= 100.0"
            )
        if self.min_evidence < 0:
            raise ValueError(f"min_evidence must be >= 0, got {self.min_evidence}")
        if self.top_articles < 1:
            raise ValueError(f"top_articles must be >= 1, got {self.top_articles}")

    @classmethod
    def from_settings(cls, settings: Settings) -> HysteresisConfig:
        """Build the config from Settings so HYSTERESIS_* env vars are honoured."""
        return cls(
            tier_low_ceiling=settings.tier_low_ceiling,
            tier_medium_ceiling=settings.tier_medium_ceiling,
            enter_medium_threshold=settings.hysteresis_enter_medium,
            exit_medium_threshold=settings.hysteresis_exit_medium,
            enter_high_threshold=settings.hysteresis_enter_high,
            exit_high_threshold=settings.hysteresis_exit_high,
            min_evidence=settings.hysteresis_min_evidence,
        )

    @classmethod
    def from_margins(
        cls,
        margin_low: float = 2.0,
        margin_high: float = 2.0,
        min_evidence: int = DEFAULT_HYSTERESIS_MIN_EVIDENCE,
        low_ceiling: float = DEFAULT_TIER_LOW_CEILING,
        medium_ceiling: float = DEFAULT_TIER_MEDIUM_CEILING,
    ) -> HysteresisConfig:
        """
        Create a HysteresisConfig symmetrically spaced around nominal ceilings.
        """
        return cls(
            tier_low_ceiling=low_ceiling,
            tier_medium_ceiling=medium_ceiling,
            enter_medium_threshold=low_ceiling + margin_low,
            exit_medium_threshold=low_ceiling - margin_low,
            enter_high_threshold=medium_ceiling + margin_high,
            exit_high_threshold=medium_ceiling - margin_high,
            min_evidence=min_evidence,
        )


# ------------------------------------------------------------------
# Pure State Machine Transition Logic
# ------------------------------------------------------------------


def initial_tier_for_score(score: float, config: HysteresisConfig) -> str:
    """
    Determine the baseline tier for a supplier without existing state
    based on nominal configured ceilings.
    """
    if score < config.tier_low_ceiling:
        return "low"
    if score < config.tier_medium_ceiling:
        return "medium"
    return "high"


def evaluate_transition(
    current_tier: str,
    score: float,
    config: HysteresisConfig,
) -> str:
    """
    Evaluate candidate tier transition from current accepted tier given a new score.

    Exact Boundary Semantics:
    - Current Tier 'low':
      * score >= enter_high_threshold (e.g. 74.0) -> 'high'
      * score >= enter_medium_threshold (e.g. 62.0) -> 'medium'
      * otherwise -> 'low'
    - Current Tier 'medium':
      * score >= enter_high_threshold (e.g. 74.0) -> 'high'
      * score < exit_medium_threshold (e.g. 58.0) -> 'low'
      * otherwise -> 'medium'
    - Current Tier 'high':
      * score < exit_medium_threshold (e.g. 58.0) -> 'low'
      * score < exit_high_threshold (e.g. 70.0) -> 'medium'
      * otherwise -> 'high'
    """
    mapped_current = map_tier_to_event_tier(current_tier)

    if mapped_current == "low":
        if score >= config.enter_high_threshold:
            return "high"
        if score >= config.enter_medium_threshold:
            return "medium"
        return "low"

    if mapped_current == "medium":
        if score >= config.enter_high_threshold:
            return "high"
        if score < config.exit_medium_threshold:
            return "low"
        return "medium"

    if mapped_current == "high":
        if score < config.exit_medium_threshold:
            return "low"
        if score < config.exit_high_threshold:
            return "medium"
        return "high"

    return mapped_current


_TIER_RANK: Dict[str, int] = {"low": 0, "medium": 1, "high": 2}
HISTORY_MAXLEN: int = 200


def select_supporting_articles(
    articles: List[Dict[str, Any]],
    previous_tier: str,
    new_tier: str,
    config: HysteresisConfig,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Return (top supporting articles, supporting count) for a move to new_tier.

    An article supports the move only if its own score points toward new_tier:
    - Upward move: article score >= the enter threshold of new_tier.
    - Downward move: article score < the exit threshold of the tier being left.
    Articles without a score cannot be judged and are not counted.
    Upward evidence is ranked highest score first, downward lowest score first.
    """
    scored = [a for a in articles if a.get("score") is not None]

    if _TIER_RANK[new_tier] > _TIER_RANK[previous_tier]:
        threshold = (
            config.enter_high_threshold if new_tier == "high" else config.enter_medium_threshold
        )
        supporting = [a for a in scored if a["score"] >= threshold]
        descending = True
    else:
        threshold = (
            config.exit_high_threshold if previous_tier == "high" else config.exit_medium_threshold
        )
        supporting = [a for a in scored if a["score"] < threshold]
        descending = False

    ranked = sorted(supporting, key=lambda a: a["score"], reverse=descending)
    return ranked[: config.top_articles], len(supporting)


def _build_explanation(
    supplier: str,
    previous_tier: str,
    new_tier: str,
    score: float,
    config: HysteresisConfig,
    top_articles: List[Dict[str, Any]],
    supporting_count: int,
    window_count: int,
) -> str:
    """Explain why the tier changed: which threshold was crossed and by which articles."""
    if _TIER_RANK[new_tier] > _TIER_RANK[previous_tier]:
        threshold = (
            config.enter_high_threshold if new_tier == "high" else config.enter_medium_threshold
        )
        rule = f"score {score:.2f} reached the '{new_tier}' entry threshold {threshold:.2f}"
    else:
        threshold = (
            config.exit_high_threshold if previous_tier == "high" else config.exit_medium_threshold
        )
        rule = f"score {score:.2f} fell below the '{previous_tier}' exit threshold {threshold:.2f}"

    drivers = "; ".join(f"\"{a['headline']}\" ({a['score']:.2f})" for a in top_articles)
    return (
        f"Supplier '{supplier}' moved from '{previous_tier}' to '{new_tier}': {rule}. "
        f"{supporting_count} of {window_count} article(s) in the window point toward "
        f"'{new_tier}' (minimum {config.min_evidence}). Top drivers: {drivers}."
    )


# ------------------------------------------------------------------
# Per-Supplier State Representation
# ------------------------------------------------------------------


@dataclass
class SupplierState:
    """
    Encapsulates the state machine status for a single supplier.
    Ensures complete state isolation between suppliers.
    """

    supplier: str
    accepted_tier: Optional[str] = None
    last_score: Optional[float] = None
    last_updated_at: Optional[str] = None
    transition_count: int = 0
    # Bounded so a long-running service does not grow memory without limit.
    history: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=HISTORY_MAXLEN))

    def initialize(self, tier: str, score: Optional[float] = None, timestamp: Optional[str] = None) -> None:
        """Initialize state when first observed."""
        self.accepted_tier = map_tier_to_event_tier(tier)
        self.last_score = round(float(score), 2) if score is not None else None
        self.last_updated_at = timestamp
        self.history.append(
            {
                "action": "initialize",
                "tier": self.accepted_tier,
                "score": self.last_score,
                "timestamp": timestamp,
            }
        )

    def apply_transition(
        self,
        new_tier: str,
        score: float,
        timestamp: Optional[str] = None,
        evidence_count: int = 0,
    ) -> str:
        """Apply an accepted tier transition and update history."""
        old_tier = self.accepted_tier
        self.accepted_tier = map_tier_to_event_tier(new_tier)
        self.last_score = round(float(score), 2)
        self.last_updated_at = timestamp
        self.transition_count += 1
        self.history.append(
            {
                "action": "transition",
                "previous_tier": old_tier,
                "new_tier": self.accepted_tier,
                "score": self.last_score,
                "evidence_count": evidence_count,
                "timestamp": timestamp,
            }
        )
        return self.accepted_tier

    def record_suppressed_transition(
        self,
        candidate_tier: str,
        score: float,
        reason: str,
        evidence_count: int,
        timestamp: Optional[str] = None,
    ) -> None:
        """Record a suppressed transition attempt for auditing and debugging."""
        self.history.append(
            {
                "action": "suppressed",
                "current_tier": self.accepted_tier,
                "candidate_tier": map_tier_to_event_tier(candidate_tier),
                "score": round(float(score), 2),
                "evidence_count": evidence_count,
                "reason": reason,
                "timestamp": timestamp,
            }
        )

    def reset(self) -> None:
        """Clear supplier state."""
        self.accepted_tier = None
        self.last_score = None
        self.last_updated_at = None
        self.transition_count = 0
        self.history.clear()


# ------------------------------------------------------------------
# Multi-Supplier Hysteresis Tracker
# ------------------------------------------------------------------


class SupplierHysteresisTracker:
    """
    Manages state machines for multiple suppliers independently.
    Emits score-change events only when accepted tiers change.
    """

    def __init__(
        self,
        config: Optional[HysteresisConfig] = None,
        publisher: Optional[EventPublisher] = None,
    ) -> None:
        if config is None:
            from src.config import get_settings

            config = HysteresisConfig.from_settings(get_settings())
        self.config = config
        self.publisher = publisher
        self._states: Dict[str, SupplierState] = {}

    def get_state(self, supplier: str) -> Optional[SupplierState]:
        """Get state for a specific supplier, if initialized."""
        return self._states.get(supplier.strip())

    def get_all_states(self) -> Dict[str, SupplierState]:
        """Return shallow copy of all tracked supplier states."""
        return dict(self._states)

    def reset(self, supplier: Optional[str] = None) -> None:
        """Reset state for a specific supplier or all suppliers."""
        if supplier is not None:
            clean = supplier.strip()
            if clean in self._states:
                self._states[clean].reset()
        else:
            self._states.clear()

    def set_state(
        self,
        supplier: str,
        tier: str,
        score: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> SupplierState:
        """Explicitly set or override a supplier's accepted tier."""
        clean = supplier.strip()
        state = SupplierState(supplier=clean)
        state.initialize(tier=tier, score=score, timestamp=timestamp)
        self._states[clean] = state
        return state

    def process_update(
        self,
        *,
        supplier: str,
        supplier_id: Optional[str] = None,
        risk_score: float,
        supporting_articles: Optional[List[Dict[str, Any]]] = None,
        occurred_at: Optional[str | datetime] = None,
        producer: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a new risk score evaluation for a supplier.

        Enforces:
        1. Initialization if the supplier has no previous state.
        2. Hysteresis threshold checks against previous accepted tier.
        3. Minimum evidence count gating before accepting candidate transitions.
        4. Event generation and optional publishing only upon accepted tier transition.

        Args:
            supplier: Name of the supplier.
            risk_score: Calculated risk score (0.0 to 100.0).
            supporting_articles: List of articles backing the score.
            occurred_at: Timestamp of observation.
            producer: Producer name for event envelope.

        Returns:
            Dict[str, Any] event envelope if an accepted transition occurred, else None.
        """
        clean_supplier = str(supplier).strip()
        if not clean_supplier:
            raise ValueError("Supplier name cannot be empty.")

        if (
            risk_score is None
            or isinstance(risk_score, bool)
            or not isinstance(risk_score, (int, float))
            or not math.isfinite(risk_score)
        ):
            raise ValueError(
                f"risk_score for '{clean_supplier}' must be a finite number, got {risk_score!r}"
            )
        # Compare on the raw score; round only for display so 61.996 does not become 62.00.
        raw_score = float(risk_score)
        display_score = round(raw_score, 2)

        formatted_articles = format_supporting_articles(supporting_articles)
        window_count = len(formatted_articles)

        # Retrieve or create independent state
        if clean_supplier not in self._states:
            self._states[clean_supplier] = SupplierState(supplier=clean_supplier)

        state = self._states[clean_supplier]

        if isinstance(occurred_at, datetime):
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            iso_timestamp = occurred_at.isoformat()
        else:
            iso_timestamp = occurred_at or datetime.now(timezone.utc).isoformat()

        # -------------------------------------------------------------
        # 1. State Initialization (Supplier has no previous state)
        # -------------------------------------------------------------
        if state.accepted_tier is None:
            init_tier = initial_tier_for_score(raw_score, self.config)
            if self.config.require_min_evidence_for_initial and window_count < self.config.min_evidence:
                logger.debug(
                    "Supplier '%s' initial update deferred: %d article(s) < min %d",
                    clean_supplier,
                    window_count,
                    self.config.min_evidence,
                )
                state.record_suppressed_transition(
                    candidate_tier=init_tier,
                    score=display_score,
                    reason="insufficient_initial_evidence",
                    evidence_count=window_count,
                    timestamp=iso_timestamp,
                )
                return None

            # The first accepted tier is a baseline, not a change, so no event is emitted.
            state.initialize(tier=init_tier, score=display_score, timestamp=iso_timestamp)
            return None

        # -------------------------------------------------------------
        # 2. Evaluate Candidate Transition with Hysteresis
        # -------------------------------------------------------------
        current_accepted = state.accepted_tier
        candidate_tier = evaluate_transition(
            current_tier=current_accepted,
            score=raw_score,
            config=self.config,
        )

        # Tier remains unchanged: retain accepted tier without emitting event
        if candidate_tier == current_accepted:
            state.last_score = display_score
            state.last_updated_at = iso_timestamp
            return None

        # -------------------------------------------------------------
        # 3. Minimum Evidence Check (articles that point toward the new tier)
        # -------------------------------------------------------------
        top_articles, supporting_count = select_supporting_articles(
            formatted_articles, current_accepted, candidate_tier, self.config
        )
        if supporting_count < self.config.min_evidence:
            logger.info(
                "Suppressed transition for '%s' from '%s' to '%s' (score %.2f): "
                "%d supporting article(s) < %d required. Retaining '%s'.",
                clean_supplier,
                current_accepted,
                candidate_tier,
                display_score,
                supporting_count,
                self.config.min_evidence,
                current_accepted,
            )
            state.record_suppressed_transition(
                candidate_tier=candidate_tier,
                score=display_score,
                reason="insufficient_evidence",
                evidence_count=supporting_count,
                timestamp=iso_timestamp,
            )
            state.last_score = display_score
            state.last_updated_at = iso_timestamp
            return None

        # -------------------------------------------------------------
        # 4. Build, publish, and only then commit the transition
        # -------------------------------------------------------------
        explanation = _build_explanation(
            supplier=clean_supplier,
            previous_tier=current_accepted,
            new_tier=candidate_tier,
            score=display_score,
            config=self.config,
            top_articles=top_articles,
            supporting_count=supporting_count,
            window_count=window_count,
        )

        event = build_score_changed_event(
            supplier=clean_supplier,
            supplier_id=supplier_id,
            previous_tier=current_accepted,
            new_tier=candidate_tier,
            risk_score=display_score,
            supporting_articles=top_articles,
            evidence_count=supporting_count,
            explanation=explanation,
            occurred_at=iso_timestamp,
            producer=producer or "supplier-risk-service",
        )

        # If publishing fails, keep the old tier so the next run retries the transition.
        routing_key = supplier_id or event.get("payload", {}).get("supplier_id") or clean_supplier
        if self.publisher is not None and not self.publisher.publish(event, key=routing_key):
            logger.error(
                "Publish failed for '%s' %s -> %s; transition not committed, will retry next run.",
                clean_supplier,
                current_accepted,
                candidate_tier,
            )
            state.record_suppressed_transition(
                candidate_tier=candidate_tier,
                score=display_score,
                reason="publish_failed",
                evidence_count=supporting_count,
                timestamp=iso_timestamp,
            )
            return None

        state.apply_transition(
            new_tier=candidate_tier,
            score=display_score,
            timestamp=iso_timestamp,
            evidence_count=supporting_count,
        )
        return event
