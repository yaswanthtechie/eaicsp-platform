"""ETA / interval-regression evaluation: MAE by horizon, interval coverage."""
import numpy as np

from ._validation import check_same_length, to_float_array
from .metrics import mae


def _bucket_labels(horizons: np.ndarray, bins) -> list:
    """Assign each horizon to a [lo, hi) bucket (last bucket closed on the right)."""
    edges = np.asarray(bins, dtype=float)
    if (edges.ndim != 1 or edges.size < 2 or not np.all(np.isfinite(edges))
            or not np.all(np.diff(edges) > 0)):
        raise ValueError("bins must be >= 2 finite, strictly increasing edges")
    if horizons.min() < edges[0] or horizons.max() > edges[-1]:
        raise ValueError(
            f"horizons fall outside bins [{edges[0]:g}, {edges[-1]:g}]; "
            f"extend bins rather than silently dropping rows"
        )
    idx = np.minimum(np.searchsorted(edges, horizons, side="right") - 1, edges.size - 2)
    labels = []
    for i in idx:
        closing = "]" if i == edges.size - 2 else ")"
        labels.append((int(i), f"[{edges[i]:g}, {edges[i + 1]:g}{closing}"))
    return labels


def mae_by_horizon(y_true, y_pred, horizons, bins=None) -> dict:
    """MAE overall and per prediction horizon (exact value, or per bucket).

    Why: ETA error normally grows with how far ahead we predict; one overall
    MAE hides that. Each bucket also reports n so thin buckets are visible.
    Empty buckets are omitted; horizons outside `bins` raise.
    """
    yt = to_float_array(y_true, "y_true")
    yp = to_float_array(y_pred, "y_pred")
    h = to_float_array(horizons, "horizons")
    check_same_length(y_true=yt, y_pred=yp, horizons=h)

    if bins is None:
        keys = [(float(v), int(v) if float(v).is_integer() else float(v)) for v in h]
    else:
        keys = _bucket_labels(h, bins)

    groups = {}
    for i, key in enumerate(keys):
        groups.setdefault(key, []).append(i)

    by_horizon = {}
    for (_, label), rows in sorted(groups.items(), key=lambda kv: kv[0][0]):
        by_horizon[label] = {"mae": mae(yt[rows], yp[rows]), "n": len(rows)}
    return {"overall_mae": mae(yt, yp), "by_horizon": by_horizon}


def interval_coverage(y_true, lower, upper, nominal=None) -> dict:
    """Share of true values inside [lower, upper] (inclusive), plus mean width.

    Why: a '90% interval' should contain ~90% of outcomes. Coverage alone can
    be gamed with absurdly wide intervals, so mean width is always returned
    alongside it. Inverted intervals (lower > upper) raise: they indicate a bug
    upstream. If `nominal` is given, coverage_gap = coverage - nominal.
    """
    yt = to_float_array(y_true, "y_true")
    lo = to_float_array(lower, "lower")
    hi = to_float_array(upper, "upper")
    check_same_length(y_true=yt, lower=lo, upper=hi)
    if np.any(lo > hi):
        raise ValueError("interval_coverage: found lower > upper (inverted interval)")

    inside = (yt >= lo) & (yt <= hi)
    result = {
        "interval_coverage": float(inside.mean()),
        "mean_interval_width": float(np.mean(hi - lo)),
        "n": int(len(yt)),
    }
    if nominal is not None:
        if isinstance(nominal, bool) or not (0 < float(nominal) < 1):
            raise ValueError("nominal must be strictly between 0 and 1")
        result["nominal"] = float(nominal)
        result["coverage_gap"] = result["interval_coverage"] - float(nominal)
    return result