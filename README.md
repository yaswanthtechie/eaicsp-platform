# EAICSP Platform
Enterprise AI-Powered Supply Chain Platform.

## Structure
- `services/` — backend microservices (Pod 1)
- `ml-services/` — ML models (Pod 2)
- `frontend/` — dashboard + supplier portal (Pod 3)
- `data-platform/` — ETL, pipelines (Pod 0)
- `infra/` — docker, k8s
- `docs/` — architecture

## Rules
- Never push to `master` or another protected main branch. Branch → PR → review → merge.
- Branch naming: `yourname/what-you-did` (e.g. `gopi/anomaly-detection`)
- No secrets in code. Use `.env` (gitignored).
- Every service follows the `_reference/` pattern.

## Getting started
1. Clone
2. `git checkout -b yourname/your-service`
3. Work in your assigned folder only
4. Push, open PR, wait for review
﻿# UI Library

## Overview

This project is a reusable UI component library built using **React**, **TypeScript**, and **Vite**.

The goal was to build reusable, fully typed UI components without using `any`, maintain consistent styling using design tokens, and demonstrate all components in a showcase page.

---

# Components Implemented

The following reusable components have been implemented:

- Button
- Card
- Badge
- KPI Card
- Table
- Modal
- Tabs
- Spinner
- Toast

Each component is designed to be reusable and can be imported into other React applications.

---

# Features

- React + TypeScript
- Fully typed components
- No use of `any`
- Reusable UI components
- Shared design tokens (`tokens.ts`)
- Mock data stored in `src/mocks`
- Showcase page demonstrating all components
- Loading and empty states where applicable

---

# Project Structure

```
src/
├── components/
│   ├── Badge.tsx
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── KpiCard.tsx
│   ├── Modal.tsx
│   ├── Spinner.tsx
│   ├── Table.tsx
│   ├── Tabs.tsx
│   └── Toast.tsx
│
├── mocks/
│
├── App.tsx
├── App.css
├── index.css
├── main.tsx
└── tokens.ts
```

---

# Technologies Used

- React
- TypeScript
- Vite
- CSS

---

# How to Run

### Install dependencies

```bash
npm install
```

### Start the development server

```bash
npm run dev
```

### Open in browser

```
http://localhost:5173
```

---

# What I Found

During this assignment, I learned:

- How to build reusable React components.
- How to define component props using TypeScript interfaces and types.
- How to avoid using `any` by using proper TypeScript types.
- How to use shared design tokens for colors, spacing, and border radius.
- How to build a generic Table component using TypeScript generics.
- How to organize components in a reusable project structure.
- How different UI components can be composed together in a showcase page.

---

# What I Got Stuck On

Some challenges I encountered during development were:

- Understanding TypeScript generics in the Table component.
- Managing component props and state with strict TypeScript typing.
- Organizing the project structure for a reusable UI library.
- Understanding how to prepare the project for submission in a shared Git repository and create a pull request.
- Resolving minor TypeScript and import errors while integrating components.

These issues were resolved by reviewing the project requirements, testing the components, and updating the code accordingly

round 14

# Business Backtest — What Is a Better Forecast Worth?

## 1. Objective

Forecast accuracy metrics such as MAE and RMSE measure prediction errors, but they do not directly show the business impact of a forecasting model.

This milestone evaluates whether better demand forecasts can improve inventory decisions by reducing stockouts and lost sales while controlling inventory holding costs.

The simulation compares four forecasting approaches:

- **Ensemble:** Combined forecast from the existing forecasting system.
- **Prophet:** Prophet-only forecast.
- **XGBoost:** XGBoost-only forecast.
- **Naive:** Simple baseline forecast based on historical demand.

All approaches use the same historical evaluation period and inventory-policy assumptions.

## 2. Business Backtest Methodology

The simulation replays historical demand one day at a time.

For each simulation day:

1. Use only historical data available up to that day.
2. Generate the selected model's demand forecast and prediction interval.
3. Calculate the reorder point and safety stock.
4. Place a replenishment order when inventory reaches the reorder threshold.
5. Receive the order after the configured supplier lead time.
6. Serve actual demand from available inventory.
7. Record stockouts, lost sales, inventory levels, and holding costs.

The same inventory policy, initial stock, lead time, and evaluation period are used for every forecasting approach to ensure a fair comparison.

## 3. Reorder Policy

The reorder point is based on expected demand during supplier lead time plus safety stock.

**Reorder point = Expected lead-time demand + Safety stock**

Safety stock uses forecast uncertainty represented by prediction intervals. The chosen interval and service-level target should be configurable and documented.

When inventory position reaches or falls below the reorder point, the simulation places a replenishment order according to the configured order policy.

The order arrives only after the supplier lead time. Future actual demand must not be used to generate the forecast or decide the order.

## 4. Business Metrics

The simulation reports the following metrics for each forecasting approach.

| Metric | Definition |
|---|---|
| Stockout days | Number of days when demand cannot be fully served from available inventory |
| Lost-sales units | Total units of demand that could not be fulfilled |
| Average inventory | Average on-hand inventory across the evaluation period |
| Holding cost | Estimated cost of carrying inventory during the evaluation period |

### Holding-cost assumption

The default illustrative assumption is an annual inventory holding-cost rate of **20% of item value**.

Holding cost is estimated as:

`Average inventory value × Annual holding-cost rate × Evaluation days / 365`

If item cost is unavailable, use an explicitly documented configurable unit-cost assumption. Report the result as an estimate, not as verified company savings.

## 5. Leakage Prevention

The backtest must simulate the information available at each historical decision date.

- Forecasts must use only data available on the forecast date.
- Prediction intervals and safety stock must not use future evaluation outcomes.
- Replenishment orders must respect supplier lead time.
- Actual demand must reduce available inventory only when that demand occurs.
- The same starting inventory and inventory policy must be applied to all approaches.

The simulation must not use future actual sales to decide past purchase orders.

## 6. Outputs

The business backtest should generate a results table with one row per forecasting approach, including:

- Forecasting approach
- Stockout days
- Lost-sales units
- Average inventory held
- Estimated holding cost

Where useful, results should also be grouped by SKU or SKU category to identify where forecast improvements have little or no business benefit.

Recommended output files:

- `reports/business_backtest_results.csv` — detailed numerical results.
- `reports/business_backtest_summary.md` — manager-readable findings and limitations.

## 7. Interpretation

The best forecasting approach is not necessarily the one with the lowest MAE.

A forecast may reduce stockouts but increase average inventory and holding cost. The final evaluation should compare the inventory trade-offs and explain whether the reduction in lost sales justifies the additional cost of holding stock.

The report must identify SKU groups where the improvement is small, absent, or outweighed by increased inventory costs.

Do not claim that the ensemble saves money unless the simulation results support that conclusion.

## 8. Definition of Done

-  Day-by-day historical inventory simulation is implemented.
-  No future information is used at historical forecast dates.
-  Ensemble, Prophet-only, XGBoost-only, and naive approaches are compared.
-  Stockout days, lost-sales units, average inventory, and holding cost are reported.
-  Holding-cost assumptions are documented.
-  Tests cover reorder logic, lead time, inventory depletion, and metric calculations.
-  A plain-English summary explains the business impact and identifies where forecasting improvements do not help.

