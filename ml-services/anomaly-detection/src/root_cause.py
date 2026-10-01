"""
M4 - root-cause hints: "this resembles past incident type X".

INFERENCE SIDE ONLY. Safe for predict.py to import.

The incident library is built at training time by
src/incident_library.py and saved to models/incident_library.joblib.
This module only reads it.

How matching works:

    1. Turn the reading into a signature: how far each feature is
       from normal (signed z-score), plus how far humidity is from
       what the temperature says it should be (relationship residual).

    2. Compare that signature against every labeled past incident
       using cosine similarity (direction of the deviation, not size).

    3. Take the K most similar past incidents and let them vote.
       The winning type is the hint. If even the best match is weak,
       say "unknown" instead of guessing.
"""

from collections import Counter

import numpy as np


FEATURES = ["temperature", "humidity", "stock_count"]

K_NEIGHBOURS = 5

# Below this similarity we refuse to name a type.
MIN_SIMILARITY = 0.80


def reading_signature(reading, stats):
    """
    Signed deviation vector for one reading.

    [z_temperature, z_humidity, z_stock_count, z_humidity_residual]
    """

    z = [
        (float(reading[f]) - stats["mean"][f]) / stats["std"][f]
        for f in FEATURES
    ]

    expected_humidity = (
        stats["humidity_intercept"]
        + stats["humidity_slope"] * float(reading["temperature"])
    )

    residual = (
        float(reading["humidity"]) - expected_humidity
    ) / stats["residual_std"]

    return np.array(z + [residual])


def _cosine(signature, library_signatures):
    norms = np.linalg.norm(library_signatures, axis=1) * np.linalg.norm(signature)

    return (library_signatures @ signature) / np.where(norms == 0, 1.0, norms)


def match_incident(reading, library):
    """
    Return the most similar past incident type for an anomalous reading.

    {
        "incident_type": "temperature_spike" | ... | "unknown",
        "similarity": 0.97,
        "description": "...",
        "similar_past_incidents": 5,
    }
    """

    signature = reading_signature(reading, library["stats"])

    if not np.any(signature):
        return None

    similarity = _cosine(signature, library["signatures"])

    nearest = np.argsort(similarity)[::-1][:K_NEIGHBOURS]
    nearest_types = [library["labels"][i] for i in nearest]

    best_type, votes = Counter(nearest_types).most_common(1)[0]

    best_similarity = float(
        np.mean(
            [similarity[i] for i in nearest if library["labels"][i] == best_type]
        )
    )

    if best_similarity < MIN_SIMILARITY:
        return {
            "incident_type": "unknown",
            "similarity": round(best_similarity, 4),
            "description": (
                "Does not closely resemble any labeled past incident type."
            ),
            "similar_past_incidents": 0,
        }

    return {
        "incident_type": best_type,
        "similarity": round(best_similarity, 4),
        "description": library["descriptions"][best_type],
        "similar_past_incidents": int(votes),
    }