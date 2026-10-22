# Does a better forecast save money? (generated from the CSVs)

Question: to keep 98% of demand in stock, how much stock does each forecast make us hold? Replayed day by day over 1108 days, 7-day supplier lead time, no future data used.

| Volume tier | Stock needed: ensemble | Best naive (stock) | Stock saved | Holding cost saved over 1108 days | Verdict |
|---|---|---|---|---|---|
| aggregate (~34,000/day) | 12,561.8 | a 28-day average (16,953.8) | 26% | 26,665 | the ensemble pays off |
| fast movers (~200/day) | 84.6 | a 28-day average (106.0) | 20% | 130 | the ensemble pays off |
| medium movers (~30/day) | 25.3 | a 28-day average (28.1) | 10% | 17 | forecasting helps, but the ensemble adds nothing over Prophet alone |
| slow movers (~5/day) | 13.5 | a 28-day average (15.5) | 13% | 12 | forecasting helps, but the ensemble adds nothing over Prophet alone |

## In plain English

- The ensemble pays off for: aggregate (~34,000/day), fast movers (~200/day).
- medium movers (~30/day): forecasting helps, but the ensemble adds nothing over Prophet alone.
- slow movers (~5/day): forecasting helps, but the ensemble adds nothing over Prophet alone.

## Read this before quoting the numbers

- Money is an estimate: unit value 10.0 (assumed, the data has no prices), holding cost 20% of value per year.
- Volume tiers: binomial thinning of ONE aggregate series (not real SKUs).
- Ensemble weights: walk-forward: Prophet weight re-chosen at every refit from realised errors only, grid 0.0-1.0, lookback 365 origins; ensemble_50_50 = fixed 0.5/0.5.
- 'Stock saved' compares approaches at the SAME fill rate. At a fixed safety setting (metrics_headline.csv) approaches land on different fill rates, so their stockout days are not directly comparable.
