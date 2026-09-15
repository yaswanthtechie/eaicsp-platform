from scipy import stats
import numpy as np


def paired_significance_test(scores_a: list, scores_b: list, alpha: float = 0.05) -> dict:
    """
    Paired t-test comparing model A's and model B's scores across matching folds
    (e.g., MAPE from each of 5 walk-forward folds for each model).

    scores_a, scores_b: lists of the same length, each entry is that model's
    score on the same fold -- order must correspond (fold 1 vs fold 1, etc.)

    Returns whether the difference is statistically significant at the given
    alpha level, plus the mean difference and p-value, so the result is
    interpretable, not just a yes/no.

    Zero-variance case (every fold shows an identical difference): a t-test
    is numerically unstable here (scipy warns of precision loss), so no
    p-value is computed -- p_value is explicitly None rather than a
    fabricated 0.0 or 1.0, with "significant" and the interpretation set
    based on whether the constant difference is non-zero.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError("scores_a and scores_b must be the same length (paired per fold).")
    if len(scores_a) < 2:
        raise ValueError("Need at least 2 folds to run a paired significance test.")

    diffs = [a - b for a, b in zip(scores_a, scores_b)]

    if len(diffs) > 0 and np.allclose(diffs, diffs[0], atol=1e-9):
        mean_diff = diffs[0]
        return {
            "mean_difference": mean_diff,
            "p_value": None,
            "significant": mean_diff != 0,
            "alpha": alpha,
            "interpretation": (
                f"Every fold shows an identical difference of {mean_diff:.4f} "
                f"(zero variance across folds) -- a p-value cannot be meaningfully "
                f"computed here, so none is reported. "
                + ("Treated as a real, consistent difference since it is non-zero."
                   if mean_diff != 0 else "No difference at all.")
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


def wilcoxon_significance_test(scores_a: list, scores_b: list, alpha: float = 0.05) -> dict:
    """
    Wilcoxon signed-rank test -- a non-parametric alternative to the paired
    t-test. Doesn't assume the fold differences are normally distributed,
    which matters when there are very few folds (e.g. 3-5, the typical
    walk-forward fold count in this project) -- with that little data, a
    t-test's normality assumption is hard to trust.

    scores_a, scores_b: lists of the same length, paired per fold, same
    convention as paired_significance_test().

    Raises ValueError if fewer than 2 folds are given, or if every fold
    shows an identical difference (Wilcoxon is undefined when all
    differences are zero or ranks can't be computed -- same zero-variance
    edge case paired_significance_test() handles specially).
    """
    if len(scores_a) != len(scores_b):
        raise ValueError("scores_a and scores_b must be the same length (paired per fold).")
    if len(scores_a) < 2:
        raise ValueError("Need at least 2 folds to run a Wilcoxon signed-rank test.")

    diffs = [a - b for a, b in zip(scores_a, scores_b)]
    mean_diff = sum(diffs) / len(diffs)

    if np.allclose(diffs, 0, atol=1e-9):
        raise ValueError(
            "wilcoxon_significance_test: all fold differences are zero -- "
            "the test is undefined in this case."
        )

    try:
        stat, p_value = stats.wilcoxon(scores_a, scores_b)
    except ValueError as e:
        raise ValueError(f"wilcoxon_significance_test: {e}")

    return {
        "mean_difference": mean_diff,
        "p_value": float(p_value),
        "significant": bool(p_value < alpha),
        "alpha": alpha,
        "interpretation": (
            f"(Wilcoxon signed-rank, non-parametric) Model A's mean score differs "
            f"from Model B's by {mean_diff:.4f}. "
            + (
                f"This difference IS statistically significant (p={p_value:.4f} < {alpha})."
                if p_value < alpha
                else f"This difference is NOT statistically significant (p={p_value:.4f} >= {alpha}) -- "
                     f"could be due to random noise across folds."
            )
        ),
    }