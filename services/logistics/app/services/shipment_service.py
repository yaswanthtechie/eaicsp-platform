import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

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

from app.services.carriers.base import CarrierError
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
# CARRIER INSTANCES
# ============================================================

CARRIERS = {
    Carrier.dhl: DHLAdapter(),
    Carrier.fedex: FedExAdapter(),
    Carrier.ups: UPSAdapter(),
    Carrier.bluedart: BlueDartAdapter(),
}


# ============================================================
# RELIABILITY CONFIGURATION
# ============================================================

RELIABILITY_WINDOW = 200

INITIAL_HISTORY_SIZE = 50

INITIAL_RELIABILITY = {
    Carrier.dhl: 0.87,
    Carrier.fedex: 0.92,
    Carrier.ups: 0.95,
    Carrier.bluedart: 0.90,
}


# ============================================================
# DETERMINISTIC INITIAL RELIABILITY HISTORY
# ============================================================

def _build_initial_history(
    score: float,
    size: int = INITIAL_HISTORY_SIZE,
) -> list[bool]:
    """
    Create deterministic initial carrier history.

    True  = on-time delivery
    False = late delivery

    A local seeded Random object is used so that
    restarting the application produces the same
    initial history.
    """

    seed = int(score * 10000) + size

    rng = random.Random(seed)

    history = [
        rng.random() < score
        for _ in range(size)
    ]

    return history


carrier_history: dict[Carrier, list[bool]] = {
    carrier: _build_initial_history(
        score,
        INITIAL_HISTORY_SIZE,
    )
    for carrier, score in INITIAL_RELIABILITY.items()
}


# ============================================================
# RELIABILITY FUNCTIONS
# ============================================================

def calculate_reliability_score(
    history: list[bool],
) -> float:
    """
    Calculate reliability from delivery history.

    Example:

        [True, True, True, False]

    Score:

        3 / 4 = 0.75
    """

    if not history:
        return 0.0

    return sum(history) / len(history)


def get_reliability_score(
    carrier: Carrier,
) -> float:
    """
    Return the current reliability score
    for a carrier.
    """

    history = carrier_history.get(
        carrier,
        [],
    )

    return round(
        calculate_reliability_score(history),
        4,
    )


def record_carrier_result(
    carrier: Carrier,
    on_time: bool,
) -> None:
    """
    Record an actual carrier delivery result.

    Only the most recent RELIABILITY_WINDOW
    results are retained.
    """

    if carrier not in carrier_history:
        carrier_history[carrier] = []

    carrier_history[carrier].append(
        bool(on_time)
    )

    if len(carrier_history[carrier]) > RELIABILITY_WINDOW:
        carrier_history[carrier] = (
            carrier_history[carrier][
                -RELIABILITY_WINDOW:
            ]
        )


def reset_reliability_history() -> None:
    """
    Reset all carrier reliability histories.

    Useful for tests.
    """

    carrier_history.clear()

    for carrier, score in INITIAL_RELIABILITY.items():
        carrier_history[carrier] = _build_initial_history(
            score,
            INITIAL_HISTORY_SIZE,
        )


# ============================================================
# RETRY CONFIGURATION
# ============================================================

RETRY_ATTEMPTS = 3

RETRY_DELAYS = (
    1,
    2,
)


def api_retry():
    """
    Compatibility helper for existing tests/imports.

    The actual carrier call in this service does NOT use
    this decorator around the complete carrier operation.

    The circuit breaker must be checked before every retry
    attempt.
    """

    return retry(
        retry=retry_if_exception_type(CarrierError),
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=4,
        ),
        reraise=True,
    )


# ============================================================
# CIRCUIT BREAKER
# ============================================================

class CircuitBreaker:
    """
    Local per-carrier circuit breaker.

    CLOSED:
        Carrier requests are allowed.

    OPEN:
        Carrier requests are blocked.

    HALF_OPEN:
        After the recovery timeout, exactly one trial
        request is allowed.
    """

    FAILURE_THRESHOLD = 3

    RECOVERY_TIMEOUT = 30

    def __init__(self):
        self.failure_count = 0
        self.state = "CLOSED"
        self.opened_at: Optional[float] = None
        self.half_open_trial = False

    def record_failure(self) -> None:
        """
        Record one carrier failure.

        Three consecutive failures open the circuit.
        """

        self.failure_count += 1

        if self.failure_count >= self.FAILURE_THRESHOLD:
            self.state = "OPEN"
            self.opened_at = time.monotonic()
            self.half_open_trial = False

    def record_success(self) -> None:
        """
        Successful carrier call closes the circuit.
        """

        self.failure_count = 0
        self.state = "CLOSED"
        self.opened_at = None
        self.half_open_trial = False

    def is_open(self) -> bool:
        """
        Return True when the carrier call should be blocked.

        OPEN -> HALF_OPEN after recovery timeout.

        In HALF_OPEN, only one trial request is allowed.
        """

        # ----------------------------------------------------
        # CLOSED
        # ----------------------------------------------------

        if self.state == "CLOSED":
            return False

        # ----------------------------------------------------
        # OPEN
        # ----------------------------------------------------

        if self.state == "OPEN":

            if (
                self.opened_at is not None
                and (
                    time.monotonic()
                    - self.opened_at
                    >= self.RECOVERY_TIMEOUT
                )
            ):
                self.state = "HALF_OPEN"
                self.half_open_trial = False

            else:
                return True

        # ----------------------------------------------------
        # HALF_OPEN
        # ----------------------------------------------------

        if self.state == "HALF_OPEN":

            if self.half_open_trial:
                return True

            self.half_open_trial = True

            return False

        return False


CIRCUIT_BREAKERS = {
    carrier: CircuitBreaker()
    for carrier in Carrier
}


def is_circuit_open(
    carrier: Carrier,
) -> bool:
    """
    Check whether a carrier circuit is blocking calls.
    """

    return CIRCUIT_BREAKERS[
        carrier
    ].is_open()


def reset_circuit_breaker(
    carrier: Carrier,
) -> None:
    """
    Reset one carrier circuit breaker.
    """

    breaker = CIRCUIT_BREAKERS[carrier]

    breaker.failure_count = 0
    breaker.state = "CLOSED"
    breaker.opened_at = None
    breaker.half_open_trial = False


def reset_all_circuit_breakers() -> None:
    """
    Reset every carrier circuit breaker.
    """

    for carrier in Carrier:
        reset_circuit_breaker(carrier)


# ============================================================
# STATUS TRANSITIONS
# ============================================================

VALID_TRANSITIONS = {
    Status.pending: {
        Status.in_transit,
        Status.cancelled,
    },

    Status.in_transit: {
        Status.delayed,
        Status.delivered,
        Status.cancelled,
    },

    Status.delayed: {
        Status.in_transit,
        Status.delivered,
        Status.cancelled,
    },

    Status.delivered: set(),

    Status.cancelled: set(),
}


def is_valid_transition(
    current_status: Status,
    new_status: Status,
) -> bool:
    """
    Check whether a shipment status transition is valid.
    """

    if current_status == new_status:
        return True

    return new_status in VALID_TRANSITIONS.get(
        current_status,
        set(),
    )


# ============================================================
# SHIPMENT CRUD
# ============================================================

def shipment_exists(
    shipment_id: int,
) -> bool:
    """
    Check whether a shipment exists.
    """

    return shipment_id in shipments


def create_shipment(
    shipment: ShipmentCreate,
) -> ShipmentCreate:
    """
    Create a shipment and record its initial event.
    """

    if shipment.shipment_id in shipments:
        raise ValueError(
            "Shipment already exists"
        )

    shipments[shipment.shipment_id] = shipment

    shipment_events[
        shipment.shipment_id
    ] = [
        ShipmentEvent(
            shipment_id=shipment.shipment_id,
            status=shipment.status,
            timestamp=datetime.now(),
            location=shipment.origin,
        )
    ]

    return shipment


def get_all_shipments() -> list[ShipmentCreate]:
    """
    Return all shipments.
    """

    return list(
        shipments.values()
    )


def get_shipments(
    status: Optional[Status] = None,
) -> list[ShipmentCreate]:
    """
    Return shipments.

    Optional status filtering is supported.
    """

    if status is None:
        return get_all_shipments()

    return [
        shipment
        for shipment in shipments.values()
        if shipment.status == status
    ]


def filter_shipments_by_status(
    shipment_status: Status,
) -> list[ShipmentCreate]:
    """
    Filter shipments by status.

    This name is kept for the route layer.
    """

    return get_shipments(
        shipment_status
    )


def get_shipment(
    shipment_id: int,
) -> Optional[ShipmentCreate]:
    """
    Return a shipment if it exists.

    Returns None when not found.
    """

    return shipments.get(
        shipment_id
    )


def update_shipment(
    shipment_id: int,
    shipment: ShipmentCreate,
) -> ShipmentCreate:
    """
    Update an existing shipment.

    Status transition validation is enforced.
    """

    existing = shipments.get(
        shipment_id
    )

    if existing is None:
        raise ValueError(
            "Shipment not found"
        )

    if not is_valid_transition(
        existing.status,
        shipment.status,
    ):
        raise ValueError(
            "Invalid status transition: "
            f"{existing.status.value} -> "
            f"{shipment.status.value}"
        )

    shipments[shipment_id] = shipment

    shipment_events.setdefault(
        shipment_id,
        [],
    ).append(
        ShipmentEvent(
            shipment_id=shipment_id,
            status=shipment.status,
            timestamp=datetime.now(),
            location=shipment.destination,
        )
    )

    # --------------------------------------------------------
    # RECORD ACTUAL DELIVERY PERFORMANCE
    # --------------------------------------------------------

    if shipment.status == Status.delivered:

        if (
            shipment.actual_delivery is not None
            and shipment.estimated_delivery is not None
        ):
            on_time = (
                shipment.actual_delivery
                <= shipment.estimated_delivery
            )
        else:
            on_time = False

        record_carrier_result(
            shipment.carrier,
            on_time,
        )

    return shipment


def delete_shipment(
    shipment_id: int,
) -> Optional[ShipmentCreate]:
    """
    Delete a shipment.

    Returns the deleted shipment.

    Returns None when it does not exist.
    """

    shipment = shipments.pop(
        shipment_id,
        None,
    )

    if shipment is None:
        return None

    shipment_events.pop(
        shipment_id,
        None,
    )

    return shipment


# ============================================================
# SHIPMENT HISTORY
# ============================================================

def get_shipment_history(
    shipment_id: int,
) -> list[ShipmentEvent]:
    """
    Return shipment status history.

    Raises ValueError when shipment does not exist.
    """

    if shipment_id not in shipments:
        raise ValueError(
            "Shipment not found"
        )

    return shipment_events.get(
        shipment_id,
        [],
    )


# ============================================================
# CARRIER RATE
# ============================================================

def _call_carrier_with_retry(
    carrier: Carrier,
    origin: str,
    destination: str,
    weight_kg: float,
) -> CarrierRate:
    """
    Call one carrier with retry + circuit breaker.

    The circuit breaker is checked BEFORE EVERY retry
    attempt.
    """

    adapter = CARRIERS[carrier]

    last_error: Optional[CarrierError] = None

    for attempt in range(
        1,
        RETRY_ATTEMPTS + 1,
    ):

        # ----------------------------------------------------
        # CHECK CIRCUIT BEFORE EVERY ATTEMPT
        # ----------------------------------------------------

        breaker = CIRCUIT_BREAKERS[carrier]

        if breaker.is_open():

            raise CarrierError(
                f"{carrier.value} circuit breaker is open"
            )

        try:

            rate = adapter.get_rate(
                origin,
                destination,
                weight_kg,
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            breaker.record_success()

            rate.reliability_score = (
                get_reliability_score(
                    carrier
                )
            )

            return rate

        except CarrierError as exc:

            last_error = exc

            breaker.record_failure()

            # ------------------------------------------------
            # STOP IMMEDIATELY IF BREAKER OPENED
            # ------------------------------------------------

            if breaker.state == "OPEN":

                raise CarrierError(
                    f"{carrier.value} circuit breaker is open"
                ) from exc

            # ------------------------------------------------
            # NO MORE RETRIES
            # ------------------------------------------------

            if attempt >= RETRY_ATTEMPTS:

                raise

            # ------------------------------------------------
            # EXPONENTIAL BACKOFF
            # ------------------------------------------------

            delay = RETRY_DELAYS[
                attempt - 1
            ]

            time.sleep(
                delay
            )

    if last_error is not None:
        raise last_error

    raise CarrierError(
        f"{carrier.value} carrier request failed"
    )


def _get_carrier_rate(
    carrier: Carrier,
    origin: str,
    destination: str,
    weight_kg: float,
) -> CarrierRate:
    """
    Get one carrier rate.

    This wrapper is kept for compatibility with
    existing tests and code.
    """

    return _call_carrier_with_retry(
        carrier=carrier,
        origin=origin,
        destination=destination,
        weight_kg=weight_kg,
    )


# ============================================================
# SINGLE QUOTE
# ============================================================

def get_quotes(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference,
) -> QuoteResponse:
    """
    Get quotes from all available carriers.

    Synchronous version used by existing code/tests.
    """

    rates: list[CarrierRate] = []

    warnings: list[str] = []

    carrier_names = {
        Carrier.dhl: "DHL",
        Carrier.fedex: "FedEx",
        Carrier.ups: "UPS",
        Carrier.bluedart: "BlueDart",
    }

    for carrier in Carrier:

        try:

            rate = _get_carrier_rate(
                carrier=carrier,
                origin=origin,
                destination=destination,
                weight_kg=weight_kg,
            )

            rates.append(
                rate
            )

        except CarrierError as exc:

            display_name = carrier_names.get(
                carrier,
                carrier.value,
            )

            warnings.append(
                f"{display_name} unavailable: {str(exc)}"
            )

    if preference == QuotePreference.cheapest:

        rates.sort(
            key=lambda rate: rate.price
        )

    elif preference == QuotePreference.fastest:

        rates.sort(
            key=lambda rate: rate.estimated_days
        )

    elif preference == QuotePreference.most_reliable:

        rates.sort(
            key=lambda rate: rate.reliability_score,
            reverse=True,
        )

    return QuoteResponse(
        rates=rates,
        warnings=warnings,
    )


# ============================================================
# ASYNC SINGLE QUOTE
# ============================================================

async def _async_get_quotes(
    request: QuoteRequest,
) -> QuoteResponse:
    """
    Get quotes from all carriers concurrently.

    Synchronous carrier calls are moved to worker
    threads using asyncio.to_thread().
    """

    carrier_names = {
        Carrier.dhl: "DHL",
        Carrier.fedex: "FedEx",
        Carrier.ups: "UPS",
        Carrier.bluedart: "BlueDart",
    }

    async def call_one_carrier(
        carrier: Carrier,
    ) -> CarrierRate:

        return await asyncio.to_thread(
            _call_carrier_with_retry,
            carrier,
            request.origin,
            request.destination,
            request.weight_kg,
        )

    tasks = [
        call_one_carrier(carrier)
        for carrier in Carrier
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    rates: list[CarrierRate] = []

    warnings: list[str] = []

    for carrier, result in zip(
        Carrier,
        results,
    ):

        if isinstance(
            result,
            Exception,
        ):

            display_name = carrier_names.get(
                carrier,
                carrier.value,
            )

            warnings.append(
                f"{display_name} unavailable: {str(result)}"
            )

        else:

            rates.append(
                result
            )

    if request.preference == QuotePreference.cheapest:

        rates.sort(
            key=lambda rate: rate.price
        )

    elif request.preference == QuotePreference.fastest:

        rates.sort(
            key=lambda rate: rate.estimated_days
        )

    elif request.preference == QuotePreference.most_reliable:

        rates.sort(
            key=lambda rate: rate.reliability_score,
            reverse=True,
        )

    return QuoteResponse(
        rates=rates,
        warnings=warnings,
    )


# ============================================================
# SEQUENTIAL BULK QUOTES
# ============================================================

async def _sequential_bulk_quotes(
    requests: list[QuoteRequest],
) -> list[QuoteResponse]:
    """
    Execute shipment quotes sequentially.

    Used only for benchmarking.
    """

    results: list[QuoteResponse] = []

    for request in requests:

        result = await _async_get_quotes(
            request
        )

        results.append(
            result
        )

    return results


# ============================================================
# PARALLEL BULK QUOTES
# ============================================================

async def _parallel_bulk_quotes(
    requests: list[QuoteRequest],
) -> list[QuoteResponse]:
    """
    Execute all shipment quotes concurrently.

    R4 requirement:

        asyncio.gather()

    Each shipment creates four concurrent carrier calls.
    """

    tasks = [
        _async_get_quotes(request)
        for request in requests
    ]

    return await asyncio.gather(
        *tasks
    )


# ============================================================
# BULK QUOTE
# ============================================================

async def get_bulk_quotes(
    requests: list[QuoteRequest],
    benchmark: bool = False,
) -> dict:
    """
    R4 asynchronous bulk quotation.

    Maximum batch size:

        20 shipments

    benchmark=true:

        sequential execution is measured first,
        followed by parallel execution.

    Measuring sequential first prevents the
    parallel benchmark from opening circuit breakers
    before the sequential measurement.
    """

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    if not requests:
        raise ValueError(
            "At least one shipment is required"
        )

    if len(requests) > 20:
        raise ValueError(
            "Maximum 20 shipments are allowed"
        )

    # --------------------------------------------------------
    # BENCHMARK MODE
    # --------------------------------------------------------

    if benchmark:

        # Reset circuit breakers before benchmark.
        #
        # This ensures the sequential and parallel
        # measurements start from a clean state.
        reset_all_circuit_breakers()

        # ----------------------------------------------------
        # SEQUENTIAL EXECUTION
        # ----------------------------------------------------

        sequential_start = time.perf_counter()

        sequential_quotes = (
            await _sequential_bulk_quotes(
                requests
            )
        )

        sequential_seconds = (
            time.perf_counter()
            - sequential_start
        )

        # ----------------------------------------------------
        # RESET BEFORE PARALLEL RUN
        # ----------------------------------------------------

        reset_all_circuit_breakers()

        # ----------------------------------------------------
        # PARALLEL EXECUTION
        # ----------------------------------------------------

        parallel_start = time.perf_counter()

        quotes = await _parallel_bulk_quotes(
            requests
        )

        parallel_seconds = (
            time.perf_counter()
            - parallel_start
        )

        # ----------------------------------------------------
        # SPEEDUP
        # ----------------------------------------------------

        if parallel_seconds > 0:

            speedup = (
                sequential_seconds
                / parallel_seconds
            )

        else:

            speedup = 0.0

        performance = {
            "shipment_count": len(requests),
            "parallel_seconds": round(
                parallel_seconds,
                6,
            ),
            "sequential_seconds": round(
                sequential_seconds,
                6,
            ),
            "speedup": round(
                speedup,
                2,
            ),
        }

        logger.info(
            "R4 bulk quote benchmark: "
            "shipments=%s sequential=%.4fs "
            "parallel=%.4fs speedup=%.2fx",
            len(requests),
            sequential_seconds,
            parallel_seconds,
            speedup,
        )

        return {
            "quotes": quotes,
            "performance": performance,
        }

    # --------------------------------------------------------
    # NORMAL MODE
    # --------------------------------------------------------

    parallel_start = time.perf_counter()

    quotes = await _parallel_bulk_quotes(
        requests
    )

    parallel_seconds = (
        time.perf_counter()
        - parallel_start
    )

    performance = {
        "shipment_count": len(requests),
        "parallel_seconds": round(
            parallel_seconds,
            6,
        ),
        "sequential_seconds": None,
        "speedup": None,
    }

    return {
        "quotes": quotes,
        "performance": performance,
    }


# ============================================================
# CONSOLIDATION
# ============================================================

def _normalize_destination(
    destination: str,
) -> str:
    """
    Normalize destination text for comparison.
    """

    return " ".join(
        destination.strip().lower().split()
    )


def get_consolidation_suggestions() -> list[dict]:
    """
    Find active shipments that can potentially
    be consolidated.

    Conditions:

    1. Same destination.
    2. Estimated delivery within 2 days.
    3. Shipment is not delivered.
    4. Shipment is not cancelled.
    """

    active_shipments = [
        shipment
        for shipment in shipments.values()
        if shipment.status
        not in {
            Status.delivered,
            Status.cancelled,
        }
    ]

    suggestions: list[dict] = []

    visited: set[int] = set()

    for index, first in enumerate(
        active_shipments
    ):

        if first.shipment_id in visited:
            continue

        group = [
            first
        ]

        first_destination = (
            _normalize_destination(
                first.destination
            )
        )

        for second in active_shipments[
            index + 1:
        ]:

            second_destination = (
                _normalize_destination(
                    second.destination
                )
            )

            if (
                first_destination
                != second_destination
            ):
                continue

            date_difference = abs(
                (
                    first.estimated_delivery
                    - second.estimated_delivery
                ).days
            )

            if date_difference <= 2:

                group.append(
                    second
                )

        if len(group) >= 2:

            shipment_ids = [
                shipment.shipment_id
                for shipment in group
            ]

            visited.update(
                shipment_ids
            )

            total_weight = sum(
                shipment.weight_kg
                for shipment in group
            )

            suggestions.append(
                {
                    "shipment_ids": shipment_ids,
                    "destination": first.destination,
                    "shipment_count": len(group),
                    "total_weight_kg": total_weight,
                    "reason": (
                        "Shipments have the same "
                        "destination and estimated "
                        "delivery dates within 2 days."
                    ),
                }
            )

    return suggestions


# ============================================================
# ETA DISTANCE
# ============================================================

DISTANCES_KM = {

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


def _get_distance(
    origin: str,
    destination: str,
) -> int:
    """
    Return known route distance.

    Unknown routes use 500 km as a mock distance.
    """

    key = (
        origin.strip().lower(),
        destination.strip().lower(),
    )

    return DISTANCES_KM.get(
        key,
        500,
    )


# ============================================================
# ETA EXPLANATION
# ============================================================

def explain_eta(
    shipment_id: int,
) -> dict:
    """
    Explain the shipment ETA using:

    - origin
    - destination
    - route distance
    - carrier
    - carrier estimated days
    - dynamic reliability
    """

    shipment = shipments.get(
        shipment_id
    )

    if shipment is None:
        raise ValueError(
            "Shipment not found"
        )

    carrier = shipment.carrier

    adapter = CARRIERS.get(
        carrier
    )

    if adapter is None:
        raise ValueError(
            "Unsupported carrier"
        )

    distance_km = _get_distance(
        shipment.origin,
        shipment.destination,
    )

    reliability_score = (
        get_reliability_score(
            carrier
        )
    )

    # --------------------------------------------------------
    # GET ESTIMATED DAYS
    # --------------------------------------------------------

    try:

        rate = _get_carrier_rate(
            carrier=carrier,
            origin=shipment.origin,
            destination=shipment.destination,
            weight_kg=shipment.weight_kg,
        )

        estimated_days = rate.estimated_days

    except CarrierError:

        estimated_days_by_carrier = {
            Carrier.dhl: 2,
            Carrier.fedex: 3,
            Carrier.ups: 4,
            Carrier.bluedart: 2,
        }

        estimated_days = (
            estimated_days_by_carrier.get(
                carrier,
                0,
            )
        )

    # --------------------------------------------------------
    # RELIABILITY DESCRIPTION
    # --------------------------------------------------------

    if reliability_score >= 0.90:

        reliability_description = (
            "high carrier reliability"
        )

    elif reliability_score >= 0.75:

        reliability_description = (
            "moderate carrier reliability"
        )

    else:

        reliability_description = (
            "lower carrier reliability"
        )

    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------

    explanation = (
        f"Estimated delivery is based on the "
        f"{carrier.value.upper()} carrier estimate "
        f"of {estimated_days} days, the route distance "
        f"of approximately {distance_km} km, and the "
        f"current reliability score of "
        f"{reliability_score:.2f}, indicating "
        f"{reliability_description}."
    )

    return {
        "shipment_id": shipment_id,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "carrier": carrier.value,
        "distance_km": distance_km,
        "reliability_score": reliability_score,
        "estimated_days": estimated_days,
        "explanation": explanation,
    }


# ============================================================
# CIRCUIT BREAKER STATUS
# ============================================================

def get_circuit_breaker_status() -> dict:
    """
    Return current circuit breaker information
    for every carrier.
    """

    result = {}

    for carrier, breaker in (
        CIRCUIT_BREAKERS.items()
    ):

        result[
            carrier.value
        ] = {
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "threshold": breaker.FAILURE_THRESHOLD,
            "recovery_timeout_seconds": (
                breaker.RECOVERY_TIMEOUT
            ),
        }

    return result