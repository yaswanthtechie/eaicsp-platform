## Retraining Cycle 0 – Initial Promotion

Run Name: yearly_retrain_2016

Status: Finished

### Model Details

| Metric | Value |
|---|---:|
| MAPE | 1.325453757759904 |
| RMSE | 7370.6375045205605 |

### Ensemble Search

11 ensemble weight combinations were tested automatically.

Selected weights:

- Prophet: 0.8
- XGBoost: 0.2

### Promotion Decision

Promotion Status: PROMOTED

Reason: No existing promoted baseline was available, so the candidate
was promoted as the initial model.

MLflow confirms:

- `promotion_status: promoted`
- `grid_search_status: winner_selected`

Evidence: MLflow run `yearly_retrain_2016`