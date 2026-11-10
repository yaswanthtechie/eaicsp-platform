# Round 14 ETA Model Leakage Finding

## Scope

Round 14 required the inherited ETA model and the rebuilt ETA model to be
evaluated on the same chronological test period. If the inherited model
performed better, its feature construction had to be inspected for possible
future-information leakage.

## Comparison table

| Model | Test MAE | Nominal Coverage | Actual Coverage | Mean Interval Width |
|---|---:|---:|---:|---:|
| Inherited ETA model | 4.3012 days | 80% | 94.46% | 20.39 days |
| Round 14 ETA model | 4.6000 days | 80% | 95.83% | 22.91 days |

Both models over-cover the 80% target, so both intervals are wider than they need to be. Round 14's higher coverage comes from its wider interval and is not an improvement. Exact values: `results/round14_metrics.json`.

## Leakage investigation

The inherited model's feature construction was inspected for information
that would only become available after shipment departure.

The inherited model uses:

- purchase-time calendar features
- origin and destination coordinates
- geographic distance
- item count
- total weight
- total volume
- freight value
- product category

Actual delivery timestamps are used to construct the supervised target, but
they are not included as model features.

The feature extraction code also explicitly guards against leakage columns
such as:

- `order_status`
- `order_delivered_customer_date`
- `order_delivered_carrier_date`

being present in the final feature dataset.

## Round 14 historical features

Round 14 adds historical ETA features using the shared feature engineering
library.

Because Olist does not provide a separate carrier field, `seller_id` is used
as the carrier proxy. The route is represented as seller state to customer
state.

The historical ETA features are generated using an as-of historical join.
Only shipment outcomes strictly before the current shipment's scheduled
departure time are available to the historical aggregates.

Therefore, the current shipment's own delivery outcome is not used to
construct its historical features.

### One-at-a-time historical-feature ablation

| Configuration | Test MAE (days) |
|---|---:|
| All six historical features | `4.6000` |
| Remove `historical_on_time_rate_carrier` | `4.5490` |
| Remove `historical_avg_transit_days_carrier` | `4.8385` |
| Remove `historical_on_time_rate_route` | `4.5054` |
| Remove `historical_avg_transit_days_route` | `4.7188` |
| Remove `historical_avg_transit_days_carrier_route` | `4.7133` |
| Remove `historical_on_time_rate_departure_season` | `4.4103` |

### Ablation Conclusion

Removing `historical_on_time_rate_departure_season` alone reduces MAE from 4.60 to 4.41, recovering most of the gap to the inherited model (4.30). The seasonal on-time rate is the main cause of the regression: it is likely noisy or non-stationary across the chronological split, so the model learns a seasonal pattern from training years that does not hold in the test period. Removing `historical_avg_transit_days_carrier` makes MAE worse (4.84), so carrier transit history is the most useful of the six features.

### Dependency on Round 9–11 results

The Round 9–11 ETA-anomaly correlation analysis was implemented as a standalone statistical analysis. It consumes precomputed ETA errors and anomaly results and does not import, load, or invoke the inherited ETA model.

Therefore, the R14 rebuild does not invalidate that correlation analysis and no Round 9–11 rerun is required because of the R14 model rebuild.

The model referred to as the **inherited model** in the Round 14 comparison is a model retrained using the inherited feature set on the same chronological training/test split; it is not the previously committed production model artifact.

## Finding

The inherited model's lower MAE is **not evidence of data leakage**.

The feature inspection did not identify post-departure information being used
as an inherited model feature. The Round 14 historical features are also
constructed using strict as-of historical information.

Therefore, the performance difference is reported as a genuine experimental
result rather than being attributed to an identified leakage problem.

## Conclusion

No confirmed post-departure feature leakage was identified in the inherited
ETA model.

The Round 14 implementation preserves point-in-time feature construction for
the newly introduced historical ETA features. The lower inherited-model MAE
should therefore be treated as an honest comparison result, not as evidence
that the inherited model was benefiting from leakage.