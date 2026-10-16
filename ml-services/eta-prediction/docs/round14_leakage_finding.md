# Round 14 ETA Model Leakage Finding

## Scope

Round 14 required the inherited ETA model and the rebuilt ETA model to be
evaluated on the same chronological test period. If the inherited model
performed better, its feature construction had to be inspected for possible
future-information leakage.

## Comparison

Both models were evaluated on the same chronological test period.

| Model | Test MAE | Interval Coverage |
|---|---:|---:|
| Inherited ETA model | 4.3012 days | 94.46% |
| Round 14 ETA model | 4.6000 days | 95.83% |

The inherited model achieved lower MAE on this test period.

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

## Finding

The inherited model's lower MAE is **not evidence of data leakage**.

The feature inspection did not identify post-departure information being used
as an inherited model feature. The Round 14 historical features are also
constructed using strict as-of historical information.

Therefore, the performance difference is reported as a genuine experimental
result rather than being attributed to an identified leakage problem.

The inherited model performed better on MAE for this test period, while the
Round 14 model achieved higher prediction-interval coverage.

## Conclusion

No confirmed post-departure feature leakage was identified in the inherited
ETA model.

The Round 14 implementation preserves point-in-time feature construction for
the newly introduced historical ETA features. The lower inherited-model MAE
should therefore be treated as an honest comparison result, not as evidence
that the inherited model was benefiting from leakage.