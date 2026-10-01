"""Internal input validation shared by the metric modules (not public API)."""
import numpy as np


def to_float_array(values, name: str) -> np.ndarray:
    """Convert input to a 1-D finite float array, or raise a clear error.

    Why: NaN/inf/empty inputs silently poison means and sorts, producing a
    plausible-looking wrong number. Failing loudly here means every metric
    built on top inherits the same strict behaviour.
    """
    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: values must be numeric") from exc
    if arr.ndim != 1:
        raise ValueError(f"{name}: must be 1-D, got shape {arr.shape}")
    if arr.size == 0:
        raise ValueError(f"{name}: must not be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name}: contains NaN or infinite values")
    return arr


def to_binary_array(values, name: str) -> np.ndarray:
    """Convert input to a 1-D int array containing only 0 and 1.

    Why: labels like {-1, 1} (sklearn style) would otherwise be miscounted
    silently; the framework requires an explicit remap by the caller.
    """
    arr = to_float_array(values, name)
    if not np.all((arr == 0) | (arr == 1)):
        raise ValueError(f"{name}: labels must be exactly 0 or 1")
    return arr.astype(int)


def check_same_length(**named_arrays) -> None:
    """Raise if the given arrays differ in length.

    Why: zip() and numpy broadcasting hide length mismatches, which usually
    mean predictions are misaligned with actuals.
    """
    lengths = {k: len(v) for k, v in named_arrays.items()}
    if len(set(lengths.values())) > 1:
        raise ValueError(f"mismatched lengths: {lengths}")