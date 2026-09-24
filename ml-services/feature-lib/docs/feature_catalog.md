# Feature Catalog

| Feature | Type | Meaning | Version |
|---|---|---|---|
| target_lag_1 | Lag | Target value from 1 observation(s) earlier; shifted backward to avoid using the current target and prevent data leakage. | v1 |
| target_lag_7 | Lag | Target value from 7 observation(s) earlier; shifted backward to avoid using the current target and prevent data leakage. | v1 |
| target_lag_30 | Lag | Target value from 30 observation(s) earlier; shifted backward to avoid using the current target and prevent data leakage. | v1 |
| target_roll_mean_7 | Rolling Mean | Mean of the previous 7 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v1 |
| target_roll_std_7 | Rolling Std | Standard deviation of the previous 7 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v1 |
| target_roll_mean_30 | Rolling Mean | Mean of the previous 30 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v1 |
| target_roll_std_30 | Rolling Std | Standard deviation of the previous 30 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v1 |
| day_of_week | Calendar | Numeric day-of-week extracted from the date, where the value represents the weekday. | v1 |
| month | Calendar | Numeric month extracted from the date. | v1 |
| day_of_month | Calendar | Day of the month extracted from the date. | v1 |
| is_weekend | Calendar | Binary indicator showing whether the date falls on a weekend. | v1 |
| is_month_start | Calendar | Binary indicator showing whether the date is the first day of a month. | v1 |
| is_month_end | Calendar | Binary indicator showing whether the date is the last day of a month. | v1 |
| is_holiday | Holiday | Binary indicator showing whether the date is an Indian public holiday. | v1 |
| day_of_week_x_is_holiday | Interaction | Interaction between day_of_week and is_holiday. | v1 |
| target_lag_1 | Lag | Target value from 1 observation(s) earlier; shifted backward to avoid using the current target and prevent data leakage. | v2 |
| target_lag_7 | Lag | Target value from 7 observation(s) earlier; shifted backward to avoid using the current target and prevent data leakage. | v2 |
| target_lag_30 | Lag | Target value from 30 observation(s) earlier; shifted backward to avoid using the current target and prevent data leakage. | v2 |
| target_roll_mean_7 | Rolling Mean | Mean of the previous 7 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v2 |
| target_roll_std_7 | Rolling Std | Standard deviation of the previous 7 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v2 |
| target_roll_mean_30 | Rolling Mean | Mean of the previous 30 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v2 |
| target_roll_std_30 | Rolling Std | Standard deviation of the previous 30 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v2 |
| target_roll_mean_14 | Rolling Mean | Mean of the previous 14 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v2 |
| target_roll_std_14 | Rolling Std | Standard deviation of the previous 14 observations; the rolling calculation is shifted by one observation to avoid using the current target and prevent data leakage. | v2 |
| day_of_week | Calendar | Numeric day-of-week extracted from the date, where the value represents the weekday. | v2 |
| month | Calendar | Numeric month extracted from the date. | v2 |
| day_of_month | Calendar | Day of the month extracted from the date. | v2 |
| is_weekend | Calendar | Binary indicator showing whether the date falls on a weekend. | v2 |
| is_month_start | Calendar | Binary indicator showing whether the date is the first day of a month. | v2 |
| is_month_end | Calendar | Binary indicator showing whether the date is the last day of a month. | v2 |
| is_holiday | Holiday | Binary indicator showing whether the date is an Indian public holiday. | v2 |
| day_of_week_x_is_holiday | Interaction | Interaction between day_of_week and is_holiday. | v2 |
