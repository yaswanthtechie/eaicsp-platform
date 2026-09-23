# Feature Catalog

| Feature | Type | Meaning | Version |
|---|---|---|---|
| target_lag_1 | Lag | Previous observation value at the configured lag. | v1 |
| target_lag_7 | Lag | Previous observation value at the configured lag. | v1 |
| target_lag_30 | Lag | Previous observation value at the configured lag. | v1 |
| target_roll_mean_7 | Rolling Mean | Rolling mean of previous observations. | v1 |
| target_roll_std_7 | Rolling Std | Rolling standard deviation of previous observations. | v1 |
| target_roll_mean_30 | Rolling Mean | Rolling mean of previous observations. | v1 |
| target_roll_std_30 | Rolling Std | Rolling standard deviation of previous observations. | v1 |
| day_of_week | Calendar | Day of the week represented as a numeric value. | v1 |
| month | Calendar | Month extracted from the date. | v1 |
| day_of_month | Calendar | Day of the month extracted from the date. | v1 |
| is_weekend | Calendar | Indicates whether the date falls on a weekend. | v1 |
| is_month_start | Calendar | Indicates whether the date is the first day of a month. | v1 |
| is_month_end | Calendar | Indicates whether the date is the last day of a month. | v1 |
| is_holiday | Holiday | Indicates whether the date is an Indian public holiday. | v1 |
| day_of_week_x_is_holiday | Interaction | Interaction between the component features. | v1 |
