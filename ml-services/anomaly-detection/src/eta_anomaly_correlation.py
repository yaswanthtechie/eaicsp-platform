"""
Milestone 4 - are ETA prediction errors correlated with anomaly flags?

STANDALONE analysis. Needs only numpy, pandas and scipy. It takes two
tables (ETA predictions with errors, and anomaly results) joined on a
shared key, so it works with whatever the ETA service and Harish's
contract define. Nothing here imports the ETA or anomaly services.

Research question:

    Do shipments / time slots flagged as anomalous have different ETA
    error than unflagged ones?

Method (all reported, none cherry-picked):

    - Mann-Whitney U on |ETA error|, flagged vs unflagged
    - Cliff's delta: effect size, independent of sample size
    - Point-biserial correlation between flag and |ETA error|
    - Bootstrap CI and permutation test for the median difference
    - Spearman between continuous anomaly score and |ETA error|
    - Minimum detectable effect at 80% power, so a null result says
      what it can and cannot rule out

Verdict rule (set before looking at data):

    association_detected     p < alpha AND |Cliff's delta| >= min_effect
    no_association_detected  otherwise
    insufficient_data        fewer than `min_group` rows in a group

A null is a valid, honest finding. Correlation here is not causation:
both signals can share an upstream cause (e.g. a disruption).
"""

import numpy as np
import pandas as pd
from scipy import stats


# Romano et al. thresholds for |Cliff's delta|.
EFFECT_LABELS = [
    (0.147, "negligible"),
    (0.330, "small"),
    (0.474, "medium"),
    (1.001, "large"),
]


def effect_label(delta):
    for limit, label in EFFECT_LABELS:
        if abs(delta) < limit:
            return label

    return "large"


def join_eta_and_anomaly(
    eta_df,
    anomaly_df,
    key,
    eta_error_col="eta_error",
    flag_col="is_anomaly",
    score_col=None,
):
    """
    Inner-join ETA errors with anomaly results on `key`.

    Returns a frame with: key, eta_error, is_anomaly [, anomaly_score].
    Raises if the join is empty so a wrong key never yields a quiet
    "no correlation".
    """

    for frame, cols, name in (
        (eta_df, [key, eta_error_col], "eta_df"),
        (anomaly_df, [key, flag_col] + ([score_col] if score_col else []), "anomaly_df"),
    ):
        missing = [c for c in cols if c not in frame.columns]

        if missing:
            raise ValueError(f"{name} is missing columns: {missing}")

    left = eta_df[[key, eta_error_col]].rename(
        columns={eta_error_col: "eta_error"}
    )

    right_cols = [key, flag_col] + ([score_col] if score_col else [])

    right = anomaly_df[right_cols].rename(
        columns={flag_col: "is_anomaly", score_col: "anomaly_score"}
        if score_col
        else {flag_col: "is_anomaly"}
    )

    joined = left.merge(right, on=key, how="inner")

    if joined.empty:
        raise ValueError(
            f"Join on '{key}' produced no rows. Check that both tables "
            "share the same key values."
        )

    joined["is_anomaly"] = joined["is_anomaly"].astype(int)

    return joined.dropna(subset=["eta_error", "is_anomaly"])


def _minimum_detectable_delta(n1, n2, alpha, power=0.80):
    """Approximate smallest |Cliff's delta| detectable at `power`."""

    se = np.sqrt((n1 + n2 + 1) / (3.0 * n1 * n2))

    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)

    return float(min(1.0, z * se))


def analyze_correlation(
    df,
    alpha=0.05,
    min_effect=0.147,
    min_group=10,
    n_bootstrap=2000,
    n_permutations=2000,
    seed=42,
):
    """
    Run the full analysis on a joined frame (see join_eta_and_anomaly).
    """

    for column in ("eta_error", "is_anomaly"):
        if column not in df.columns:
            raise ValueError(f"df is missing column '{column}'.")

    rng = np.random.default_rng(seed)

    error = df["eta_error"].to_numpy(dtype=float)
    flag = df["is_anomaly"].to_numpy(dtype=int)
    abs_error = np.abs(error)

    flagged = abs_error[flag == 1]
    normal = abs_error[flag == 0]

    report = {
        "n": int(len(df)),
        "n_flagged": int(flagged.size),
        "n_unflagged": int(normal.size),
        "flag_rate": float(flag.mean()) if len(df) else 0.0,
        "alpha": alpha,
        "min_effect": min_effect,
    }

    if flagged.size < min_group or normal.size < min_group:
        report["verdict"] = "insufficient_data"
        report["summary"] = (
            f"Need at least {min_group} rows in each group; got "
            f"{flagged.size} flagged and {normal.size} unflagged."
        )

        return report

    # Mann-Whitney U and Cliff's delta (flagged vs unflagged).

    u_stat, mw_p = stats.mannwhitneyu(
        flagged, normal, alternative="two-sided"
    )

    delta = float(2.0 * u_stat / (flagged.size * normal.size) - 1.0)

    # Point-biserial (equivalent to Pearson with a 0/1 variable).

    if np.std(abs_error) > 0:
        r_pb, r_pb_p = stats.pointbiserialr(flag, abs_error)
    else:
        r_pb, r_pb_p = 0.0, 1.0

    # Median difference: bootstrap CI and permutation test.

    observed = float(np.median(flagged) - np.median(normal))

    boot = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        a = rng.choice(flagged, flagged.size, replace=True)
        b = rng.choice(normal, normal.size, replace=True)
        boot[i] = np.median(a) - np.median(b)

    ci_low, ci_high = np.percentile(boot, [2.5, 97.5])

    perm = np.empty(n_permutations)

    for i in range(n_permutations):
        shuffled = rng.permutation(flag)
        perm[i] = (
            np.median(abs_error[shuffled == 1])
            - np.median(abs_error[shuffled == 0])
        )

    perm_p = float(
        (np.sum(np.abs(perm) >= abs(observed)) + 1) / (n_permutations + 1)
    )

    # Signed error: do flagged shipments run systematically late/early?

    bias_p = float(
        stats.mannwhitneyu(
            error[flag == 1], error[flag == 0], alternative="two-sided"
        ).pvalue
    )

    report.update(
        {
            "median_abs_error_flagged": float(np.median(flagged)),
            "median_abs_error_unflagged": float(np.median(normal)),
            "median_difference": observed,
            "median_difference_ci95": [float(ci_low), float(ci_high)],
            "permutation_p": perm_p,
            "mann_whitney_p": float(mw_p),
            "cliffs_delta": delta,
            "effect_size": effect_label(delta),
            "point_biserial_r": float(r_pb),
            "point_biserial_p": float(r_pb_p),
            "signed_error_bias_p": bias_p,
            "min_detectable_delta_80pct_power": _minimum_detectable_delta(
                flagged.size, normal.size, alpha
            ),
        }
    )

    if "anomaly_score" in df.columns and df["anomaly_score"].nunique() > 1:
        rho, rho_p = stats.spearmanr(df["anomaly_score"], abs_error)

        report["score_spearman_rho"] = float(rho)
        report["score_spearman_p"] = float(rho_p)

    detected = mw_p < alpha and abs(delta) >= min_effect

    report["verdict"] = (
        "association_detected" if detected else "no_association_detected"
    )

    report["summary"] = _summary(report, detected)

    return report


def _summary(report, detected):
    mde = report["min_detectable_delta_80pct_power"]

    if detected:
        return (
            f"Flagged readings have a different |ETA error| "
            f"(Cliff's delta {report['cliffs_delta']:+.2f}, "
            f"{report['effect_size']}; p={report['mann_whitney_p']:.3g}). "
            "This is an association, not proof of cause."
        )

    if report["mann_whitney_p"] < report["alpha"]:
        return (
            f"Statistically significant (p={report['mann_whitney_p']:.3g}) "
            f"but the effect is {report['effect_size']} (Cliff's delta "
            f"{report['cliffs_delta']:+.2f}, below the practical "
            f"threshold {report['min_effect']}). Not treated as a "
            "meaningful association."
        )

    return (
        f"No association detected (Cliff's delta "
        f"{report['cliffs_delta']:+.2f}, p={report['mann_whitney_p']:.3g}). "
        f"With {report['n_flagged']} flagged rows, effects smaller than "
        f"|delta| ~ {mde:.2f} could not be reliably detected, so only "
        "larger relationships are ruled out."
    )


def make_synthetic_joint(
    n=3000,
    anomaly_rate=0.05,
    coupling=0.0,
    seed=42,
):
    """
    Synthetic joint dataset for VALIDATING THE METHOD, not a finding
    about the real services.

    coupling = 0   ETA error independent of anomaly flag (null world)
    coupling > 0   flagged rows get larger ETA errors by (1 + coupling)
    """

    rng = np.random.default_rng(seed)

    flag = (rng.random(n) < anomaly_rate).astype(int)

    error = rng.normal(0.0, 8.0, n) * (1.0 + coupling * flag)

    score = rng.normal(0.0, 1.0, n) + 3.0 * flag

    return pd.DataFrame(
        {
            "shipment_id": np.arange(n),
            "eta_error": error,
            "is_anomaly": flag,
            "anomaly_score": score,
        }
    )


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent

    # Real data:
    # python -m src.eta_anomaly_correlation eta.csv anomaly.csv key [label]
    if len(sys.argv) in (4, 5):
        eta = pd.read_csv(sys.argv[1])
        anomaly = pd.read_csv(sys.argv[2])
        frame = join_eta_and_anomaly(eta, anomaly, key=sys.argv[3])
        label = sys.argv[4] if len(sys.argv) == 5 else "real"
    else:
        # No shared key yet: validate the method on synthetic worlds.
        frame = make_synthetic_joint(coupling=0.0)
        label = "synthetic_null"

    result = analyze_correlation(frame)

    print(f"[{label}]")
    print(json.dumps(result, indent=2))

    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / f"eta_anomaly_correlation_{label}.json", "w") as f:
        json.dump(result, f, indent=2)