from scipy import stats


def paired_significance_test(scores_a: list, scores_b: list, alpha: float = 0.05) -> dict:
    """
    Paired t-test comparing model A's and model B's scores across matching folds
    (e.g., MAPE from each of 5 walk-forward folds for each model).

    scores_a, scores_b: lists of the same length, each entry is that model's
    score on the same fold -- order must correspond (fold 1 vs fold 1, etc.)

    Returns whether the difference is statistically significant at the given
    alpha level, plus the mean difference and p-value, so the result is
    interpretable, not just a yes/no.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError("scores_a and scores_b must be the same length (paired per fold).")
    if len(scores_a) < 2:
        raise ValueError("Need at least 2 folds to run a paired significance test.")

    diffs = [a - b for a, b in zip(scores_a, scores_b)]

    if len(set(diffs)) == 1:
        # Every fold shows the identical difference -- zero variance, so a
        # t-test is numerically unstable (scipy warns "precision loss").
        # Treat a non-zero constant difference as trivially significant.
        mean_diff = diffs[0]
        return {
            "mean_difference": mean_diff,
            "p_value": 0.0 if mean_diff != 0 else 1.0,
            "significant": mean_diff != 0,
            "alpha": alpha,
            "interpretation": (
                f"Every fold shows an identical difference of {mean_diff:.4f} "
                f"(zero variance across folds) -- "
                + ("treated as a real, consistent difference."
                   if mean_diff != 0 else "no difference at all.")
            ),
        }

    t_stat, p_value = stats.ttest_rel(scores_a, scores_b)
    mean_diff = sum(diffs) / len(diffs)

    return {
        "mean_difference": mean_diff,
        "p_value": float(p_value),
        "significant": bool(p_value < alpha),
        "alpha": alpha,
        "interpretation": (
            f"Model A's mean score differs from Model B's by {mean_diff:.4f}. "
            + (
                f"This difference IS statistically significant (p={p_value:.4f} < {alpha})."
                if p_value < alpha
                else f"This difference is NOT statistically significant (p={p_value:.4f} >= {alpha}) -- "
                     f"could be due to random noise across folds."
            )
        ),
    }