from __future__ import annotations

import asyncio
import logging
import random
import time
from datetime import UTC, datetime
from typing import Any

from app.schemas.shipment import (
    Carrier,
    CarrierRate,
    QuotePreference,
    QuoteRequest,
    QuoteResponse,
    ShipmentCreate,
    ShipmentEvent,
    Status,
)

from app.services.carriers.dhl import DHLAdapter
from app.services.carriers.fedex import FedExAdapter
from app.services.carriers.ups import UPSAdapter
from app.services.carriers.bluedart import BlueDartAdapter


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# IN-MEMORY STORAGE
# ============================================================

shipments: dict[int, ShipmentCreate] = {}

shipment_events: dict[int, list[ShipmentEvent]] = {}


# ============================================================
# CARRIERS
# ============================================================

CARRIERS = {
    Carrier.dhl: DHLAdapter(),
    Carrier.fedex: FedExAdapter(),
    Carrier.ups: UPSAdapter(),
    Carrier.bluedart: BlueDartAdapter(),
}


# ============================================================
# DYNAMIC RELIABILITY HISTORY
# ============================================================

carrier_history: dict[Carrier, list[Any]] = {
    Carrier.dhl: [],
    Carrier.fedex: [],
    Carrier.ups: [],
    Carrier.bluedart: [],
}


# Initial simulated reliability probabilities.
# These values are ONLY used to generate the initial
# simulated history. They are NOT returned directly
# as reliability_score.
INITIAL_RELIABILITY_PROBABILITY = {
    Carrier.dhl: 0.87,
    Carrier.fedex: 0.92,
    Carrier.ups: 0.95,
    Carrier.bluedart: 0.90,
}


def generate_reliability_history(
    shipments_per_carrier: int = 50,
) -> None:
    """
    Generate simulated historical shipment results.

    The generated history contains True/False values:

        True  -> shipment delivered on time
        False -> shipment delayed

    The reliability score is calculated later from this
    history instead of using a hardcoded score.
    """

    for carrier in Carrier:

        carrier_history[carrier] = []

        probability = INITIAL_RELIABILITY_PROBABILITY[
            carrier
        ]

        for _ in range(shipments_per_carrier):

            on_time = (
                random.random() < probability
            )

            carrier_history[carrier].append(
                on_time
            )


# Generate initial history when service starts.
generate_reliability_history()


# ============================================================
# RELIABILITY SCORE
# ============================================================

def calculate_reliability_score(
    history: list[Any],
) -> float:
    """
    Calculate reliability from tracked shipment history.

    Formula:

        reliability =
            on-time shipments / total shipments
    """

    if not history:
        return 0.0

    on_time_count = 0

    for record in history:

        if isinstance(record, bool):

            if record:
                on_time_count += 1

        elif isinstance(record, dict):

            if record.get("on_time") is True:
                on_time_count += 1

    return round(
        on_time_count / len(history),
        4,
    )


def get_reliability_score(
    carrier: Carrier,
) -> float:
    """
    Return the current reliability score calculated
    from the carrier's tracked history.
    """

    return calculate_reliability_score(
        carrier_history.get(
            carrier,
            [],
        )
    )


def record_carrier_result(
    carrier: Carrier,
    on_time: bool,
) -> None:
    """
    Add a new shipment result to carrier history.

    This allows reliability to change over time.
    """

    carrier_history.setdefault(
        carrier,
        [],
    ).append(on_time)


def simulate_carrier_history(
    shipments_per_carrier: int = 50,
) -> None:
    """
    Public helper used by tests/demo code to regenerate
    simulated carrier history.
    """

    generate_reliability_history(
        shipments_per_carrier
    )


def get_carrier_history(
    carrier: Carrier,
) -> list[Any]:
    """
    Return a copy of the carrier's history.
    """

    return list(
        carrier_history.get(
            carrier,
            [],
        )
    )


# ============================================================
# STATUS TRANSITIONS
# ============================================================

LEGAL_TRANSITIONS = {

    Status.pending: [
        Status.in_transit,
        Status.cancelled,
    ],

    Status.in_transit: [
        Status.delayed,
        Status.delivered,
        Status.cancelled,
    ],

    Status.delayed: [
        Status.in_transit,
        Status.delivered,
        Status.cancelled,
    ],

    Status.delivered: [],

    Status.cancelled: [],
}


def is_valid_transition(
    from_status: Status,
    to_status: Status,
) -> bool:
    """
    Validate shipment status transition.
    """

    if from_status == to_status:
        return True

    return to_status in LEGAL_TRANSITIONS.get(
        from_status,
        [],
    )


# ============================================================
# EVENT MANAGEMENT
# ============================================================

def event_location_for_status(
    status: Status,
    shipment: ShipmentCreate,
) -> str:

    if status == Status.delivered:
        return shipment.destination

    if status == Status.in_transit:
        return "In Transit"

    if status == Status.delayed:
        return "Delayed"

    if status == Status.cancelled:
        return shipment.origin

    return shipment.origin


def record_event(
    shipment: ShipmentCreate,
) -> ShipmentEvent:
    """
    Record a shipment status event.
    """

    event = ShipmentEvent(
        shipment_id=shipment.shipment_id,
        status=shipment.status,
        timestamp=datetime.now(UTC),
        location=event_location_for_status(
            shipment.status,
            shipment,
        ),
    )

    shipment_events.setdefault(
        shipment.shipment_id,
        [],
    ).append(event)

    return event


# ============================================================
# SHIPMENT CRUD
# ============================================================

def create_shipment(
    shipment: ShipmentCreate,
) -> ShipmentCreate:
    """
    Create a shipment and record its first event.
    """

    shipments[shipment.shipment_id] = shipment

    record_event(shipment)

    return shipment


def shipment_exists(
    shipment_id: int,
) -> bool:

    return shipment_id in shipments


def get_all_shipments() -> list[ShipmentCreate]:

    return list(
        shipments.values()
    )


def get_shipment(
    shipment_id: int,
) -> ShipmentCreate | None:

    return shipments.get(
        shipment_id
    )


def update_shipment(
    shipment_id: int,
    shipment: ShipmentCreate,
) -> ShipmentCreate | None:
    """
    Update shipment after validating status transition.
    """

    existing_shipment = get_shipment(
        shipment_id
    )

    if existing_shipment is None:
        return None

    if not is_valid_transition(
        existing_shipment.status,
        shipment.status,
    ):

        raise ValueError(
            f"Invalid status transition: "
            f"{existing_shipment.status.value} -> "
            f"{shipment.status.value}"
        )

    shipments[shipment_id] = shipment

    if shipment.status != existing_shipment.status:

        record_event(shipment)

    return shipment


def delete_shipment(
    shipment_id: int,
) -> ShipmentCreate | None:

    shipment_events.pop(
        shipment_id,
        None,
    )

    return shipments.pop(
        shipment_id,
        None,
    )


def filter_shipments_by_status(
    status: Status,
) -> list[ShipmentCreate]:

    return [
        shipment
        for shipment in shipments.values()
        if shipment.status == status
    ]


# ============================================================
# CIRCUIT BREAKER
# ============================================================

CIRCUIT_FAILURE_THRESHOLD = 3

CIRCUIT_RECOVERY_SECONDS = 5.0


class CircuitBreaker:
    """
    Local circuit breaker for one carrier.

    States:

        CLOSED
        OPEN
        HALF_OPEN

    CLOSED:
        Carrier calls are allowed.

    OPEN:
        Carrier calls are blocked.

    HALF_OPEN:
        One recovery attempt is allowed.
    """

    def __init__(
        self,
        failure_threshold: int = (
            CIRCUIT_FAILURE_THRESHOLD
        ),
        recovery_timeout: float = (
            CIRCUIT_RECOVERY_SECONDS
        ),
    ):

        self.failure_threshold = (
            failure_threshold
        )

        self.recovery_timeout = (
            recovery_timeout
        )

        self.failure_count = 0

        self.state = "CLOSED"

        self.opened_at: float | None = None

        self._lock = asyncio.Lock()

    def record_success(self) -> None:
        """
        Close/reset circuit after successful request.
        """

        self.failure_count = 0

        self.state = "CLOSED"

        self.opened_at = None

    def record_failure(self) -> None:
        """
        Record a carrier failure.
        """

        self.failure_count += 1

        if (
            self.failure_count
            >= self.failure_threshold
        ):

            self.state = "OPEN"

            self.opened_at = time.monotonic()

    def is_open(self) -> bool:
        """
        Return True when carrier calls should currently
        be blocked.

        After recovery_timeout, allow HALF_OPEN state.
        """

        if self.state != "OPEN":
            return False

        if self.opened_at is None:
            return True

        elapsed = (
            time.monotonic()
            - self.opened_at
        )

        if elapsed >= self.recovery_timeout:

            self.state = "HALF_OPEN"

            return False

        return True

    def is_available(self) -> bool:
        """
        Return whether a carrier call can be attempted.
        """

        return not self.is_open()

    def reset(self) -> None:
        """
        Completely reset the circuit.
        """

        self.failure_count = 0

        self.state = "CLOSED"

        self.opened_at = None


CIRCUIT_BREAKERS = {
    carrier: CircuitBreaker()
    for carrier in Carrier
}


def reset_circuit_breaker(
    carrier: Carrier,
) -> None:

    breaker = CIRCUIT_BREAKERS.get(
        carrier
    )

    if breaker:

        breaker.reset()


def reset_all_circuit_breakers() -> None:

    for breaker in CIRCUIT_BREAKERS.values():

        breaker.reset()


def reset_circuit_breakers() -> None:
    """
    Backward-compatible function name.
    """

    reset_all_circuit_breakers()


def is_circuit_open(
    carrier: Carrier,
) -> bool:

    breaker = CIRCUIT_BREAKERS.get(
        carrier
    )

    if breaker is None:
        return False

    return breaker.is_open()


def get_circuit_breaker_status() -> dict:
    """
    Return status of every carrier circuit breaker.
    """

    result = {}

    for carrier, breaker in (
        CIRCUIT_BREAKERS.items()
    ):

        result[carrier.value] = {
            "state": breaker.state,
            "failure_count": (
                breaker.failure_count
            ),
            "failure_threshold": (
                breaker.failure_threshold
            ),
            "recovery_timeout_seconds": (
                breaker.recovery_timeout
            ),
        }

    return result


# ============================================================
# SINGLE CARRIER CALL
# ============================================================

def call_one_carrier(
    carrier: Carrier,
    origin: str,
    destination: str,
    weight_kg: float,
) -> tuple[CarrierRate | None, str | None]:
    """
    Call one carrier through the local circuit breaker.

    IMPORTANT:

    The circuit breaker check happens BEFORE calling
    the carrier adapter.

    Therefore an OPEN carrier is not repeatedly hammered.
    """

    breaker = CIRCUIT_BREAKERS[carrier]

    # --------------------------------------------------------
    # CIRCUIT OPEN
    # --------------------------------------------------------

    if breaker.is_open():

        warning = (
            f"{carrier.value.title()} "
            f"circuit is OPEN"
        )

        logger.warning(
            warning
        )

        return None, warning

    # --------------------------------------------------------
    # GET CARRIER
    # --------------------------------------------------------

    adapter = CARRIERS.get(
        carrier
    )

    if adapter is None:

        warning = (
            f"{carrier.value.title()} unavailable"
        )

        return None, warning

    # --------------------------------------------------------
    # CALL CARRIER
    # --------------------------------------------------------

    try:

        rate = adapter.get_rate(
            origin,
            destination,
            weight_kg,
        )

        breaker.record_success()

        return rate, None

    except Exception as exc:

        breaker.record_failure()

        carrier_names = {
            Carrier.dhl: "DHL",
            Carrier.fedex: "FedEx",
            Carrier.ups: "UPS",
            Carrier.bluedart: "BlueDart",
        }

        carrier_name = carrier_names.get(
            carrier,
            carrier.value,
        )

        warning = (
            f"{carrier_name} unavailable"
        )

        logger.warning(
            "%s: %s",
            warning,
            exc,
        )

        return None, warning


# ============================================================
# SORT RATES
# ============================================================

def sort_rates(
    rates: list[CarrierRate],
    preference: QuotePreference,
) -> list[CarrierRate]:

    if preference == QuotePreference.cheapest:

        return sorted(
            rates,
            key=lambda rate: rate.price,
        )

    if preference == QuotePreference.fastest:

        return sorted(
            rates,
            key=lambda rate: rate.estimated_days,
        )

    if preference == QuotePreference.most_reliable:

        return sorted(
            rates,
            key=lambda rate: (
                rate.reliability_score,
                -rate.estimated_days,
                -rate.price,
            ),
            reverse=True,
        )

    return rates


# ============================================================
# APPLY DYNAMIC RELIABILITY
# ============================================================

def apply_dynamic_reliability(
    rate: CarrierRate,
) -> CarrierRate:
    """
    Replace the carrier's static mock reliability with
    the score calculated from tracked shipment history.
    """

    score = get_reliability_score(
        rate.carrier
    )

    return rate.model_copy(
        update={
            "reliability_score": score
        }
    )


# ============================================================
# SEQUENTIAL SINGLE QUOTE
# ============================================================

def get_quote_response_sequential(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = (
        QuotePreference.cheapest
    ),
) -> QuoteResponse:
    """
    Query all carriers one after another.

    Used as the R4 performance baseline.
    """

    rates: list[CarrierRate] = []

    warnings: list[str] = []

    for carrier in CARRIERS:

        rate, warning = call_one_carrier(
            carrier,
            origin,
            destination,
            weight_kg,
        )

        if rate is not None:

            rate = apply_dynamic_reliability(
                rate
            )

            rates.append(rate)

        if warning:

            warnings.append(
                warning
            )

    rates = sort_rates(
        rates,
        preference,
    )

    return QuoteResponse(
        rates=rates,
        warnings=warnings,
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def get_quote_response(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = (
        QuotePreference.cheapest
    ),
) -> QuoteResponse:

    return get_quote_response_sequential(
        origin,
        destination,
        weight_kg,
        preference,
    )


def get_quotes(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = (
        QuotePreference.cheapest
    ),
) -> QuoteResponse:

    return get_quote_response(
        origin,
        destination,
        weight_kg,
        preference,
    )


# ============================================================
# ASYNC SINGLE QUOTE
# ============================================================

async def get_quote_response_async(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = (
        QuotePreference.cheapest
    ),
) -> QuoteResponse:
    """
    Query all carriers concurrently.

    asyncio.gather() is used here as required by R4.
    """

    tasks = []

    for carrier in CARRIERS:

        task = asyncio.to_thread(
            call_one_carrier,
            carrier,
            origin,
            destination,
            weight_kg,
        )

        tasks.append(task)

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    rates: list[CarrierRate] = []

    warnings: list[str] = []

    for result in results:

        if isinstance(
            result,
            Exception,
        ):

            warnings.append(
                f"Carrier unavailable: {result}"
            )

            continue

        rate, warning = result

        if rate is not None:

            rate = apply_dynamic_reliability(
                rate
            )

            rates.append(rate)

        if warning:

            warnings.append(
                warning
            )

    rates = sort_rates(
        rates,
        preference,
    )

    return QuoteResponse(
        rates=rates,
        warnings=warnings,
    )


# ============================================================
# BULK QUOTE - PARALLEL
# ============================================================

async def get_bulk_quotes_parallel(
    requests: list[QuoteRequest],
) -> list[QuoteResponse]:
    """
    Process all shipments concurrently.

    There are two levels of concurrency:

    Level 1:
        Multiple shipments run together.

    Level 2:
        For each shipment, all carriers run together
        using asyncio.gather().
    """

    tasks = [
        get_quote_response_async(
            request.origin,
            request.destination,
            request.weight_kg,
            request.preference,
        )
        for request in requests
    ]

    return await asyncio.gather(
        *tasks
    )


# ============================================================
# BULK QUOTE - SEQUENTIAL
# ============================================================

def get_bulk_quotes_sequential(
    requests: list[QuoteRequest],
) -> list[QuoteResponse]:
    """
    Process shipments one by one.

    This is the baseline used to measure R4 speedup.
    """

    results = []

    for request in requests:

        result = get_quote_response_sequential(
            request.origin,
            request.destination,
            request.weight_kg,
            request.preference,
        )

        results.append(result)

    return results


# ============================================================
# R4 BULK QUOTE
# ============================================================

async def get_bulk_quotes(
    requests: list[QuoteRequest],
    benchmark: bool = False,
) -> dict:
    """
    R4 bulk quote implementation.

    Requirements:

    - Maximum 20 shipments.
    - All carriers queried in parallel.
    - asyncio.gather() used.
    - Parallel execution time measured.
    - Optional sequential benchmark.
    - Speedup calculated and logged.
    """

    # --------------------------------------------------------
    # VALIDATE REQUEST
    # --------------------------------------------------------

    if len(requests) == 0:

        raise ValueError(
            "At least one shipment is required"
        )

    if len(requests) > 20:

        raise ValueError(
            "Batch quote supports up to 20 shipments"
        )

    # --------------------------------------------------------
    # PARALLEL QUOTE
    # --------------------------------------------------------

    parallel_start = time.perf_counter()

    parallel_quotes = (
        await get_bulk_quotes_parallel(
            requests
        )
    )

    parallel_seconds = (
        time.perf_counter()
        - parallel_start
    )

    # --------------------------------------------------------
    # DEFAULT PERFORMANCE
    # --------------------------------------------------------

    performance = {
        "shipment_count": len(requests),
        "parallel_seconds": round(
            parallel_seconds,
            4,
        ),
        "sequential_seconds": None,
        "speedup": None,
    }

    # --------------------------------------------------------
    # BENCHMARK MODE
    # --------------------------------------------------------

    if benchmark:

        sequential_start = time.perf_counter()

        get_bulk_quotes_sequential(
            requests
        )

        sequential_seconds = (
            time.perf_counter()
            - sequential_start
        )

        if parallel_seconds > 0:

            speedup = (
                sequential_seconds
                / parallel_seconds
            )

        else:

            speedup = 0.0

        performance[
            "sequential_seconds"
        ] = round(
            sequential_seconds,
            4,
        )

        performance[
            "speedup"
        ] = round(
            speedup,
            2,
        )

        logger.info(
            "R4 BULK QUOTE BENCHMARK | "
            "Shipments=%s | "
            "Sequential=%.4fs | "
            "Parallel=%.4fs | "
            "Speedup=%.2fx",
            len(requests),
            sequential_seconds,
            parallel_seconds,
            speedup,
        )

    else:

        logger.info(
            "R4 BULK QUOTE | "
            "Shipments=%s | "
            "Parallel=%.4fs",
            len(requests),
            parallel_seconds,
        )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {
        "quotes": parallel_quotes,
        "performance": performance,
    }


# ============================================================
# CONSOLIDATION SUGGESTIONS
# ============================================================

def get_consolidation_suggestions() -> list[dict]:
    """
    Simple rule-based consolidation.

    Rule:

        2 or more shipments
        +
        same destination
        +
        delivery dates within 2 days
        =
        consolidation suggestion
    """

    grouped: dict[
        str,
        list[ShipmentCreate],
    ] = {}

    # --------------------------------------------------------
    # GROUP BY DESTINATION
    # --------------------------------------------------------

    for shipment in shipments.values():

        destination = (
            shipment.destination
            .strip()
            .lower()
        )

        grouped.setdefault(
            destination,
            [],
        ).append(shipment)

    suggestions = []

    # --------------------------------------------------------
    # FIND SHIPMENTS WITHIN 2 DAYS
    # --------------------------------------------------------

    for destination, group in grouped.items():

        if len(group) < 2:
            continue

        group.sort(
            key=lambda shipment: (
                shipment.estimated_delivery
            )
        )

        for index in range(
            len(group) - 1
        ):

            first = group[index]

            for second in group[
                index + 1:
            ]:

                days_apart = abs(
                    (
                        second.estimated_delivery
                        - first.estimated_delivery
                    ).days
                )

                if days_apart <= 2:

                    suggestions.append(
                        {
                            "shipment_ids": [
                                first.shipment_id,
                                second.shipment_id,
                            ],
                            "destination": (
                                first.destination
                            ),
                            "suggestion": (
                                "These shipments can "
                                "be combined to "
                                "potentially save "
                                "delivery cost."
                            ),
                            "reason": (
                                "2 or more shipments "
                                "have the same "
                                "destination and "
                                "delivery dates "
                                "within 2 days."
                            ),
                            "days_apart": days_apart,
                        }
                    )

    return suggestions


# ============================================================
# ETA EXPLANATION
# ============================================================

CARRIER_BASELINE_DAYS = {
    Carrier.dhl: 2,
    Carrier.fedex: 3,
    Carrier.ups: 4,
    Carrier.bluedart: 2,
}


def estimate_distance_km(
    origin: str,
    destination: str,
) -> int:
    """
    Simple rule-based distance lookup.

    This is intentionally not route optimization.
    """

    known_routes = {

        (
            "hyderabad",
            "mumbai",
        ): 710,

        (
            "mumbai",
            "hyderabad",
        ): 710,

        (
            "hyderabad",
            "delhi",
        ): 1550,

        (
            "delhi",
            "hyderabad",
        ): 1550,

        (
            "hyderabad",
            "bangalore",
        ): 570,

        (
            "bangalore",
            "hyderabad",
        ): 570,

        (
            "hyderabad",
            "chennai",
        ): 630,

        (
            "chennai",
            "hyderabad",
        ): 630,
    }

    key = (
        origin.strip().lower(),
        destination.strip().lower(),
    )

    return known_routes.get(
        key,
        500,
    )


def explain_eta(
    shipment_or_id: ShipmentCreate | int,
) -> dict:
    """
    Return a plain-English ETA explanation.

    Factors:

    - Distance
    - Carrier baseline
    - Dynamic reliability
    - Mock weather flag
    """

    # --------------------------------------------------------
    # GET SHIPMENT
    # --------------------------------------------------------

    if isinstance(
        shipment_or_id,
        int,
    ):

        shipment = get_shipment(
            shipment_or_id
        )

        if shipment is None:

            raise ValueError(
                "Shipment not found"
            )

    else:

        shipment = shipment_or_id

    # --------------------------------------------------------
    # BASIC DATA
    # --------------------------------------------------------

    carrier = shipment.carrier

    distance = estimate_distance_km(
        shipment.origin,
        shipment.destination,
    )

    baseline = CARRIER_BASELINE_DAYS.get(
        carrier,
        3,
    )

    reliability = get_reliability_score(
        carrier
    )

    # --------------------------------------------------------
    # WEATHER FLAG
    # --------------------------------------------------------

    weather_flag = False

    # --------------------------------------------------------
    # ETA CALCULATION
    # --------------------------------------------------------

    estimated_days = baseline

    # Lower reliability adds one day.
    if reliability < 0.80:

        estimated_days += 1

    # Long distance adds one day.
    if distance > 1500:

        estimated_days += 1

    # Mock weather rule.
    if weather_flag:

        estimated_days += 1

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    weather_text = (
        "A weather delay is simulated."
        if weather_flag
        else
        "No weather delay is currently simulated."
    )

    explanation = (
        f"The ETA is approximately "
        f"{estimated_days} day(s). "
        f"The route distance is about "
        f"{distance} km. "
        f"{carrier.value.title()} has a "
        f"baseline delivery time of "
        f"{baseline} day(s). "
        f"The current dynamically calculated "
        f"reliability score is "
        f"{reliability:.2f}. "
        f"{weather_text}"
    )

    return {
        "shipment_id": shipment.shipment_id,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "carrier": carrier.value,
        "distance_km": distance,
        "carrier_baseline_days": baseline,
        "reliability_score": reliability,
        "weather_flag": weather_flag,
        "estimated_days": estimated_days,
        "explanation": explanation,
    }


# ============================================================
# SHIPMENT HISTORY
# ============================================================

def get_shipment_history(
    shipment_id: int,
) -> list[ShipmentEvent]:

    return sorted(
        shipment_events.get(
            shipment_id,
            [],
        ),
        key=lambda event: event.timestamp,
    )