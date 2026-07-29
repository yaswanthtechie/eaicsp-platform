import pandas as pd

def find_outliers(series: pd.Series) -> dict:
    """
    Find outliers in a numeric pandas Series using the IQR method.
    Returns lower limit, upper limit, outlier mask, and outlier count.
    """
    
    q1=series.quantile(0.25)
    q3=series.quantile(0.75)

    iqr=q3-q1

    lower_limit=q1 - (1.5 * iqr)
    upper_limit=q3 + (1.5 * iqr)

    outlier_mask = (series < lower_limit) | (series > upper_limit)

    return {
        "lower_limit":lower_limit,
        "upper_limit":upper_limit,
        "outlier_mask":outlier_mask,
        "outlier_count":int(outlier_mask.sum())
    }
