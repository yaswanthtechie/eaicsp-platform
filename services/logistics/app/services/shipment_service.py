from __future__ import annotations
import asyncio
import logging
import random
import time
from datetime import UTC, date, datetime
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
# STORAGE
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


# Generate initial simulated history.
def generate_reliability_history(
    shipments_per_carrier: int = 50,
) -> None:

    reliability_probability = {
        Carrier.dhl: 0.87,
        Carrier.fedex: 0.92,
        Carrier.ups: 0.95,
        Carrier.bluedart: 0.90,
    }

    for carrier in Carrier:

        carrier_history[carrier] = []

        probability = reliability_probability[carrier]

        for _ in range(shipments_per_carrier):

            on_time = random.random() < probability

            carrier_history[carrier].append(on_time)


generate_reliability_history()


# ============================================================
# RELIABILITY SCORE
# ============================================================

def calculate_reliability_score(
    history: list[Any],
) -> float:

    if not history:
        return 0.0

    on_time_count = 0

    for record in history:
        if isinstance(record, bool):

            if record is True:
                on_time_count += 1

        # Also support dictionary records.
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

    carrier_history.setdefault(
        carrier,
        [],
    ).append(on_time)


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
            f"{existing_shipment.status} -> "
            f"{shipment.status}"
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


class CircuitBreaker:

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
    ):

        self.failure_threshold = (
            failure_threshold
        )

        self.failure_count = 0

        self.state = "CLOSED"

    def record_success(self) -> None:

        self.failure_count = 0

        self.state = "CLOSED"

    def record_failure(self) -> None:

        self.failure_count += 1

        if (
            self.failure_count
            >= self.failure_threshold
        ):

            self.state = "OPEN"

    def is_open(self) -> bool:

        return self.state == "OPEN"

    def reset(self) -> None:

        self.failure_count = 0

        self.state = "CLOSED"


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


# Backward-compatible name.
def reset_circuit_breakers() -> None:

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

    result = {}

    for carrier, breaker in CIRCUIT_BREAKERS.items():

        result[carrier.value] = {
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "failure_threshold": (
                breaker.failure_threshold
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

    breaker = CIRCUIT_BREAKERS[carrier]

    # Circuit OPEN
    if breaker.is_open():

        warning = (
            f"{carrier.value.title()} "
            f"circuit is OPEN"
        )

        logger.warning(warning)

        return None, warning

    adapter = CARRIERS.get(carrier)

    if adapter is None:

        warning = (
            f"{carrier.value.title()} unavailable"
        )

        return None, warning

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

        if carrier == Carrier.fedex:
            carrier_name = "FedEx"

        elif carrier == Carrier.dhl:
            carrier_name = "DHL"

        elif carrier == Carrier.ups:
            carrier_name = "UPS"

        elif carrier == Carrier.bluedart:
            carrier_name = "BlueDart"

        else:
            carrier_name = carrier.value

        warning = f"{carrier_name} unavailable"

        logger.warning(
            f"{warning}: {exc}"
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
# UPDATE RATE WITH DYNAMIC RELIABILITY
# ============================================================

def apply_dynamic_reliability(
    rate: CarrierRate,
) -> CarrierRate:

    score = get_reliability_score(
        rate.carrier
    )

    return rate.model_copy(
        update={
            "reliability_score": score
        }
    )


# ============================================================
# SEQUENTIAL QUOTE
# ============================================================

def get_quote_response_sequential(
    origin: str,
    destination: str,
    weight_kg: float,
    preference: QuotePreference = (
        QuotePreference.cheapest
    ),
) -> QuoteResponse:

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

            warnings.append(warning)

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
    preference: QuotePreference,
) -> QuoteResponse:

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

            warnings.append(warning)

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
# BULK QUOTE
# ============================================================

async def get_bulk_quotes(
    requests: list[QuoteRequest],
) -> dict:

    if len(requests) > 20:

        raise ValueError(
            "Batch quote supports up to 20 shipments"
        )

    if len(requests) == 0:

        return {
            "quotes": [],
            "performance": {
                "shipment_count": 0,
                "sequential_seconds": 0.0,
                "parallel_seconds": 0.0,
                "speedup": 0.0,
                "speedup_percentage": 0.0,
                "parallel_is_faster": False,
            },
        }

    # ----------------------------------------
    # Sequential benchmark
    # ----------------------------------------

    sequential_start = time.perf_counter()

    sequential_quotes = (
        get_bulk_quotes_sequential(
            requests
        )
    )

    sequential_seconds = (
        time.perf_counter()
        - sequential_start
    )

    # ----------------------------------------
    # Parallel benchmark
    # ----------------------------------------

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

    # ----------------------------------------
    # Speedup
    # ----------------------------------------

    if parallel_seconds > 0:

        speedup = (
            sequential_seconds
            / parallel_seconds
        )

    else:

        speedup = 0.0

    if sequential_seconds > 0:

        speedup_percentage = (
            (
                sequential_seconds
                - parallel_seconds
            )
            / sequential_seconds
        ) * 100

    else:

        speedup_percentage = 0.0

    parallel_is_faster = (
        parallel_seconds
        < sequential_seconds
    )

    performance = {

        "shipment_count": len(requests),

        "sequential_seconds": round(
            sequential_seconds,
            4,
        ),

        "parallel_seconds": round(
            parallel_seconds,
            4,
        ),

        "speedup": round(
            speedup,
            2,
        ),

        "speedup_percentage": round(
            speedup_percentage,
            2,
        ),

        "parallel_is_faster": (
            parallel_is_faster
        ),
    }

    logger.info(
        "Bulk quote: %s shipments | "
        "Sequential: %.4fs | "
        "Parallel: %.4fs | "
        "Speedup: %.2fx",
        len(requests),
        sequential_seconds,
        parallel_seconds,
        speedup,
    )

    return {
        "quotes": parallel_quotes,
        "performance": performance,
    }


# ============================================================
# CONSOLIDATION
# ============================================================

def get_consolidation_suggestions() -> list[dict]:

    grouped: dict[
        str,
        list[ShipmentCreate],
    ] = {}

    for shipment in shipments.values():

        grouped.setdefault(
            shipment.destination.strip().lower(),
            [],
        ).append(shipment)

    suggestions = []

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
                                "2+ shipments have "
                                "the same destination "
                                "and delivery dates "
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

    if key in known_routes:
        return known_routes[key]

    return 500


def explain_eta(
    shipment_or_id: ShipmentCreate | int,
) -> dict:

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

    weather_flag = False

    estimated_days = baseline

    if reliability < 0.80:

        estimated_days += 1

    if distance > 1500:

        estimated_days += 1

    explanation = (
        f"The ETA is approximately "
        f"{estimated_days} day(s). "
        f"The route distance is about "
        f"{distance} km. "
        f"{carrier.value.title()} has a "
        f"baseline of {baseline} day(s), "
        f"with a current reliability score "
        f"of {reliability:.2f}. "
        f"No weather delay is currently "
        f"simulated."
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
# HISTORY
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