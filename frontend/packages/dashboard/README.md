# Executive Dashboard

## Project Structure

frontend/
└── packages/
    └── dashboard/
        └── src/
            ├──api/
            |    └── dashboard.ts
            ├── components/
            │   ├── AlertsPanel.tsx
            |   ├── ErrorBoundary.tsx
            │   ├── ForecastChart.tsx
            │   ├── InventoryHeatmap.tsx
            │   ├── InventoryTable.tsx
            │   ├── ForecastAccuracy.tsx
            │   ├── InventoryHealth.tsx
            |   ├── NarrativeInsights.tsx
            │   ├── SupplierRisk.tsx
            │   ├── ShipmentStatus.tsx
            │   ├── SupplierRiskDistribution.tsx
            │   ├── DashboardFilters.tsx
            │   ├── Skeleton.tsx
            |   └── export/
            │       ├── ExportCsvButton.tsx
            |       └── ExportPdfButton.tsx
            |
            ├── hooks/
            │   ├── useWebSocket.ts
            │
            ├── mocks/
            |   ├── api.ts
            │   ├── forecast.ts
            |   ├── forecastAccuracy.ts
            │   ├── inventory.ts
            │   ├── inventoryHealth.ts
            │   ├── shipments.ts
            │   ├── supplierRisk.ts
            |   ├── user.ts
            │   └── wsServer.ts
            │
            ├── types/
            │   ├── forecast.ts
            │   └── dashboard.ts
            │
            ├── test/
            │   ├── AlertsPanel.test.tsx
            │   ├── ForecastChart.test.tsx
            │   ├── InventoryHeatmap.test.tsx
            │   ├── InventoryTable.test.tsx
            │   ├── DashboardFilters.test.tsx
            │   ├── ForecastAccuracy.test.tsx
            │   ├── InventoryHealth.test.tsx
            |   ├── setup.ts
            |   ├── SupplierRiskDistribution.test.tsx
            │   ├── SupplierRisk.test.tsx
            |   └── useWebSocket.test.ts
            ├── utils/
            │   ├── exportCsv.ts
            |   ├── exportPdf.ts
            │   └── insights.ts
            │
            ├── App.tsx
            ├── main.tsx
            ├── index.css
            └── tokens.ts
# 1. What I Built

I built an **Executive Dashboard** using React + TypeScript to give a quick view of sales forecasts, inventory, supplier risk, shipments, and important alerts.

The dashboard includes:

* **Sales Forecast Chart** using Recharts with confidence bands and zoom.
* **Inventory Table** with search, low-stock filtering, and inventory details.
* **Inventory Heatmap** for warehouse and category inventory status.
* **Real-time Alert Panel** using WebSocket.
* **KPI views** for forecast accuracy, inventory health, supplier risk, and shipment status.
* **Dashboard Filters** for warehouse, category, and date range with URL persistence.
* **Loading Skeletons** for better loading-state handling.
* **Error Boundary** for handling unexpected component errors at the widget level.
* **Virtualized Inventory Table** for efficiently displaying long lists.
* **Automated tests** for the main components and WebSocket hook.


# 2. Forecast Chart

The Forecast Chart shows sales forecast data using **Recharts**.

I added:

* **Forecast data filtering** based on the date range selected from the Dashboard Filters.
* **Actual and forecast values** with a **confidence band** to show the expected forecast range.
* **Brush zoom** to focus on a specific section of the chart.
* **Loading, empty, and error states** for better handling of different data conditions.

The chart allows an executive to focus on a specific forecast period using the common dashboard date filter.

The forecast also safely handles an empty dataset. Default values are calculated only after checking that forecast data exists, so an empty forecast correctly reaches the empty state instead of causing an error before the component renders.


# 3. Inventory Table

The Inventory Table shows inventory details for each SKU. I used the shared Table and Badge components from the UI library.

It also has SKU search bar and a low-stock filter so users can quickly find items that need attention.

When no SKU matches the search, the empty state is passed correctly to the shared Table component. However, the empty-state styling currently comes from the shared UI component, so its background/color does not fully match the dashboard theme.

The inventory mock dataset was expanded to 12000 rows so that the **virtualization** implementation is exercised with a meaningful dataset rather than only a small number of records.

The table uses react-window so that only the rows required for the visible scroll area are rendered instead of rendering all 500 rows at once.

The Inventory Table also has a simulated failure path so its error state can be reached and tested instead of being an unreachable UI state.

# 4. Inventory Risk & Reorder Planning

### Inventory Heatmap

The inventory heatmap is implemented as a grouped warehouse status view. Each SKU is grouped by warehouse and uses status colors (healthy, warning, critical) to make inventory risk easy to scan.

It is intentionally not a continuous color-intensity heatmap because the current mock inventory data does not provide a normalized numeric metric suitable for intensity scaling.

The warehouse groups are derived from the available inventory data so SKUs from other warehouses are not silently omitted.

For this round, virtualization was added to the Inventory Heatmap so only the visible rows are rendered instead of rendering the entire inventory list at once. This helps the component handle large datasets more efficiently.

A 10k+ inventory dataset was also used to check that the heatmap remains usable at a larger scale. Memoization was added to avoid unnecessary recalculations and re-renders.

The Inventory Heatmap also has a simulated failure path so its error state can be reached and tested.

I considered adding an Inventory Risk & Reorder Planning view to give executives more actionable information about stock.

The idea is to show:

* Current stock
* Days remaining
* Reorder timing
* Recommended reorder quantity

For example: SKU007 → 8 days remaining → reorder before stock out.

The current inventory data includes average daily demand, so days remaining can be calculated. However, the current dashboard does not yet implement the full reorder planning view or recommended reorder quantity calculation.

This could be added later to help executives plan orders before a stock out instead of reacting only when stock is already low.


# 5. WebSocket and Alerts

I implemented a reusable `useWebSocket` hook to manage the WebSocket connection.

The mock WebSocket server runs on:

`ws://localhost:8080`

The server sends fake alerts to simulate real-time inventory events.

The WebSocket hook handles:

* Connection status.
* Receiving alerts.
* Disconnection.
* Automatic reconnection.
* Exponential backoff.
* Maximum retry attempts.
* Final failure state after all retry attempts are exhausted.

The Alert Panel displays the received alerts with their:

* Type
* Message
* Severity

The `useWebSocket` hook exposes a `failed` flag. The flag becomes `true` when the configured maximum retry attempts are reached. `AlertsPanel` uses this state to render its error UI, making the WebSocket error state reachable and testable.

This allows executives to see important inventory events as they happen and provides a visible error state when the WebSocket can no longer reconnect.

### Mock WebSocket Development Only

The mock WebSocket server is used only during development.

It is started only when `import.meta.env.DEV` is true, so the mock server is not started in the production build.

`mock-socket` is kept as a development dependency because it is only required for the mock WebSocket server and tests.


# 6. KPI Views and Dashboard Filters

### Forecast Accuracy

* Shows forecast accuracy values along with the corresponding dates.
* Displays a **90% target** to compare actual forecast performance against the expected accuracy level.
* Helps executives quickly understand forecast performance over time.

### Inventory Health

* Shows inventory status as **Healthy, Low Stock, and Critical**.
* Clicking a status provides detailed inventory information, including **stock, days remaining, and status**.
* Helps identify which inventory items need attention.

### Supplier Risk

* Shows supplier risk information including the **supplier name, risk score, confidence, and sentiment breakdown**.
* The sentiment breakdown includes **positive, negative, and neutral** values.
* Provides a quick summary of the supplier's overall risk and supporting information.

### Shipment Status

* Shows shipment information including **total, pending, in-transit, delivered, delayed, and cancelled** shipments.
* Displays the shipment progress using a **progress bar**.
* Helps executives quickly understand the current logistics and shipment status.

### Supplier Risk Distribution

* Displays a **bar chart** showing suppliers and their corresponding risk levels.
* Makes it easier to compare risk across different suppliers.
* Helps identify suppliers with higher risk levels that may need attention.

### Dashboard Filters

* Provides **warehouse, category, and date range** filters.

* Filter selections are persisted in the **URL**, so the selected dashboard state is maintained.

* The **URL is the single source of truth** for the dashboard filter state.

* Browser **Back/Forward navigation** correctly synchronizes the URL with the filter controls.

* The **Forecast Chart, Inventory Table, and Inventory Heatmap** update based on the selected filters.

* **Inventory Health** receives the selected warehouse and category filters and updates its inventory calculations accordingly.

* The **low-stock filter** is persisted in the URL and can be toggled through the Low Stock KPI.

* Clicking a KPI updates the **selected KPI state in the URL** and provides a drill-down to the relevant dashboard section.

* Filter and drill-down state is preserved when the dashboard is refreshed or shared through its URL.

### Dashboard API Layer

A thin API layer was added under `src/api/` so that dashboard components do not depend directly on mock data    files.

The API layer currently wraps the local mock data and provides the data-access boundary required by the dashboard.

This keeps the components separated from the current mock-data implementation and makes it easier to replace the mock sources with real backend APIs later without changing every component individually.

### KPI Cross-Filtering Limitation

The dashboard filters are implemented and working for the data sources that contain the required filter fields.

For **Supplier Risk** and **Shipment Status**, the current mock data was based on the supplier-risk and shipment data provided for the project. These datasets do not currently contain a specific **warehouse** or **category** field, so applying warehouse/category filters to these two KPIs would not produce a meaningful result.

Because of this, **Supplier Risk and Shipment Status cross-filtering is currently partial** rather than being artificially filtered with unrelated values.

In the next round, I plan to extend the mock data with the required warehouse/category dimensions and then connect these two KPI views to the dashboard filters. This will allow the Supplier Risk and Shipment Status results to change correctly when the user selects different filters.

I kept the current implementation aligned with the available source data rather than adding assumptions that are not present in the original dataset.


### Error Boundary

I implemented **separate Error Boundary instances around individual dashboard widgets**.

This prevents an error in one component from causing the entire dashboard to disappear. If a widget encounters an unexpected rendering error, only that widget shows its error state while the remaining dashboard continues to work.

Each protected widget also provides a retry action so the user can attempt to render the component again.


# 7. Round 7/8/9 Features

### Auto-Generated Narrative Insights

### Narrative Insights

Narrative insights are calculated from the dashboard data and displayed as plain-English summaries.

The insights update  when the underlying dashboard data changes. For example, changing the delayed shipment count from 10 to 50 updates the related insight.

The insight logic is maintained in `src/utils/insights.ts`, while `NarrativeInsights.tsx` displays the generated text.

The current implementation generates insights from the inventory, supplier, and shipment data instead of using completely fixed values.

The insight names the smallest group of warehouses that together hold at least half of the low-stock items. Warehouses tied at the cut-off are always included together, and if every warehouse is tied, the insight says items are spread evenly.

Examples include:

* The percentage of inventory items that need reorder.
* Highest-contributing warehouse or warehouse for low-stock inventory.
* Supplier risk information.
* Shipment status information.


### Role-Based Views

The dashboard supports two mock roles:

* `ceo`
* `warehouse_manager`

The role is mocked locally and does not call a live service.

The role can be changed through the URL using the role query parameter:

    ?role=ceo
    ?role=warehouse_manager

The dashboard reads the role from the URL and renders the corresponding view.

The `ceo` view provides executive-level information such as inventory, supplier risk, shipments, and  related dashboard insights.

The `warehouse_manager` view focuses on inventory and warehouse-related information and does not display supplier-risk information that is not relevant to that role.

Role-based tests verify that the dashboard renders the appropriate content for both supported roles and that role-specific content is hidden when it should not be displayed.

The role structure is kept contract-first so that the mock role can later be replaced by the real role service.

`?role=` is a development/demo switch for this contract-first round. In production, the role will come from Platform's JWT (`role` claim), using the same role names as Rahul's `Role` enum.

### PDF and CSV Export

The dashboard supports exporting dashboard data in both PDF and CSV formats.

The export functionality is kept inside the `src/components/export/`,while the export logic is maintained in `src/utils/`.

The exported data follows the currently selected dashboard filters and role where applicable.

CSV export creates a downloadable with specified like invent0ry,supplier,shipment CSV file separately.CSV export applies proper CSV escaping and security hardening for values that could contain commas, quotes, or line breaks. Formula-injection protection is also applied to values beginning with spreadsheet formula characters.

PDF export creates a downloadable.The exported PDF contains role-appropriate dashboard information. For example, supplier-risk information is included for the `ceo` role and excluded from the `warehouse_manager` view.

### Accessibility

**Status: accessibility fixes applied; a full automated audit has not been run yet.**

What was fixed and tested:

* **Inventory Heatmap rows** are keyboard-reachable (`tabIndex=0`, `role="button"`) with a descriptive `aria-label` (SKU, product, stock, reorder point). Details appear on focus, Enter or Space, and hide on Escape. Covered by 5 tests in `InventoryHeatmap.test.tsx`.
* The **product details panel** is announced to screen readers (`role="status"`, `aria-live="polite"`).
* **Loading, error and empty states** are announced (`aria-busy`, `role="alert"`, `role="status"`).
* All **filter and export controls** have accessible names (`aria-label`).
* **KPI cards** are real `<button>` elements, so they already work with the keyboard.

Not done yet:

* Automated audit (axe / Lighthouse) and a written list of its findings.
* Colour-contrast check of the status colours in `tokens.ts`.
* Manual screen-reader walkthrough (NVDA / VoiceOver).

**Next-round accessibility follow-up:**

The remaining items require additional accessibility testing and tooling that I have not worked with yet. They are therefore intentionally kept as **not done** rather than being marked as completed. These will be treated as a **high-priority accessibility follow-up in the next round**.

### Performance at Real Scale

The inventory mock data was expanded to support a large dataset of more than 12,000 inventory items.

The Inventory Table and Inventory Heatmap use virtualization so that the dashboard does not render every inventory item at the same time.

Memoization is used to reduce unnecessary calculations and renders. The Inventory Heatmap uses useMemo for grouped and derived data and useCallback for reusable status calculation functions such as getStatus and getStatusColor.

React Profiler measurements are used to record actual render performance while working with the large dataset.

This provides a real performance check at a scale closer to production data instead of testing only with a small mock dataset.


# 8. Testing

I added tests using **Vitest** and **React Testing Library**.

All component test files are organized inside the `src/test` folder.

Tests were added for:

* `AlertsPanel`
* `App.role`
* `ForecastChart`
* `InventoryHeatmap`
* `InventoryTable`
* `DashboardFilters`
* `ExportCsvButton`
* `Insights`
* `ExportCsv`
* `ExportPdf`
* `ForecastAccuracy`
* `InventoryHealth`
* `SupplierRisk`
* `SupplierRiskDistribution`
* `ShipmentStatus`
* `useWebSocket`

The tests cover:

* Loading states.
* Empty states.
* Error states.
* User interactions.
* Dashboard filter behavior.
* Inventory filtering.
* KPI behavior.
* WebSocket connection states.
* Receiving alerts.
* Reconnection.
* Exponential backoff.
* Maximum retry failure.

WebSocket tests also cover reconnect and backoff behavior, including retry attempts, increasing retry delays, successful reconnection, and failure after the maximum retry count is reached.

A `setup.ts` file is also included in the test folder for common test setup and configuration.


## Test Cleanup

While creating the tests, I faced an issue where the DOM from one test could affect another test.

I fixed this by using `cleanup()` after every test so that each test starts with a fresh DOM.

For example:

```ts
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
```

This was especially useful for tests that use fake timers and WebSocket reconnection delays.

# 9. Challenges Faced

### Loading, Empty, and Error States

Initially, I was not familiar with handling these states. After understanding the pattern, I implemented them across the required views.

The error states were also updated so they have reachable failure paths rather than only existing as unused UI branches.

The WebSocket error state is triggered when the maximum retry attempts are exhausted. The other dashboard views have simulated failure paths so their error UIs can also be rendered and tested.

The current loading states use simulated delays around locally imported mock data. They demonstrate the required loading UI behavior, but are not connected to real backend request latency yet.

When real API integration is added, the loading state should be driven by the actual asynchronous request.

### Virtualized Inventory Table and Inventory Heatmap

For the Inventory Table, I used virtualization with `react-window` to handle long lists more efficiently.

Instead of rendering all rows at once, only the rows needed for the visible scroll area are rendered. As the user scrolls, the required rows are rendered.

### Memoization and React Profiler

I used React memoization techniques where appropriate to reduce unnecessary recalculation and rendering work.

The inventory filtering and inventory calculations use `useMemo` so that derived data is not recalculated when unrelated dashboard state changes.

I also added React `Profiler` measurements around the heavier dashboard components:

* `InventoryTable`
* `InventoryHeatmap`
* `ForecastChart`

The Profiler records both the actual render duration and the base duration for each render.

#### Recorded Profiler Measurements

The following measurements were recorded from the browser profiler while interacting with the dashboard and while real-time WebSocket updates were being received:

### Performance Measurements

Measured using React DevTools Profiler.

| **Component** | **Dataset size** | **Interaction measured** |**Actual duration** |
|---|---:|---|---:|
| InventoryTable | 12,000 items | Initial render | 9.50 ms |
| App | 12,000 items | Initial render | 9.00 ms |
| InventoryHeatmap | 12,000 items | Initial render | 4.60 ms |
| CartesianGrid | -- | Initial render | 3.90 ms |
| SupplierRisk | -- | Initial render | 2.50 ms |
| InventoryHealth | 12,000 items | Initial render | 2.30 ms |
| ShipmentStatus | -- | Initial render | 1.80 ms |

Before virtualization the heatmap measured about 122 ms, after virtualizing the item lists, only about 60 rows are in the DOM at once, which is why it now measures about 4.6 ms.

The profiler results show the measured dashboard components and their actual render durations for the recorded runs.

These measurements were captured directly using React DevTools Profiler and provide a baseline for future performance monitoring and optimization.


# 10. TypeScript Strict Mode

TypeScript strict mode is enabled for the dashboard.

This ensures that the TypeScript compiler performs stricter type checking during development and builds and helps prevent new type-safety issues from being introduced.

# 11. How to Run

Open the project in VS Code and run the following commands in the terminal:

```bash
cd frontend/packages/dashboard
npm install
npm run build
npm run dev
```

To run the complete test suite:

```bash
npm test
```

Open the local development URL shown in the terminal, for example:

`http://localhost:5173`

The dashboard uses a mock WebSocket server during development:

`ws://localhost:8080`

The mock WebSocket server is development-only and is not started as part of the production build.

# 12. Current UI and Next Steps

The current dashboard UI is functional and covers the required dashboard features, but the overall visual design and layout still need improvement.

In the next round, I will work on the UI using the available **UI component library** to improve consistency, spacing, alignment, responsiveness, and overall visual polish.

The functionality and dashboard logic are already implemented, so the next focus will be on improving the user experience and making the dashboard look more professional.

#### Profiler Recording Note

React DevTools Profiler was used to measure the dashboard rendering performance during actual interactions.

The measurements were captured while changing the warehouse filter, scrolling through the Inventory Heatmap, and receiving dashboard updates.

The performance test used the 12,000-item inventory dataset across 4 warehouses with virtualization and memoization enabled.

The recorded profiler measurements represent actual render activity captured during these interactions.

**Note:** The original tasks assigned to me for this dashboard were **Round 7, Round 8, and Round 9**. In the PDF, the same work is referenced as **Round 9, Round 10, and Round 11** because I started this dashboard two tasks behind the other Workstreams. I have kept **Round 7/8/9** in this README because that is the original round numbering under which I started and tracked this implementation.

