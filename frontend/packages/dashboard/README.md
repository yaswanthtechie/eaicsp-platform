# Executive Dashboard

## Project Structure

frontend/
└── packages/
    └── dashboard/
        └── src/
            ├── components/
            │   ├── AlertsPanel.tsx
            |   ├── ErrorBoundary.tsx
            │   ├── ForecastChart.tsx
            │   ├── InventoryHeatmap.tsx
            │   ├── InventoryTable.tsx
            │   ├── ForecastAccuracy.tsx
            │   ├── InventoryHealth.tsx
            │   ├── SupplierRisk.tsx
            │   ├── ShipmentStatus.tsx
            │   ├── SupplierRiskDistribution.tsx
            │   ├── DashboardFilters.tsx
            │   └── Skeleton.tsx
            │
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
            │
            ├── App.tsx
            ├── main.tsx
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
* **Error Boundary** for handling unexpected component errors.
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

This is a shared UI styling issue, not an issue with the inventory search or filtering logic.

The Inventory Table also has a simulated failure path so its error state can be reached and tested instead of being an unreachable UI state.

# 4. Inventory Risk & Reorder Planning

### Inventory Heatmap

The inventory heatmap is implemented as a grouped warehouse status view. Each SKU is grouped by warehouse and uses status colors (healthy, warning, critical) to make inventory risk easy to scan.

It is intentionally not a continuous color-intensity heatmap because the current mock inventory data does not provide a normalized numeric metric suitable for intensity scaling.

The warehouse groups are derived from the available inventory data so SKUs from other warehouses are not silently omitted.

The Inventory Heatmap also has a simulated failure path so its error state can be reached and tested.

I considered adding an Inventory Risk & Reorder Planning view to give executives more actionable information about stock.

The idea is to show:

Current stock

Days remaining

Reorder timing

Recommended reorder quantity

For example: SKU007 → 8 days remaining → reorder before stock out.

I did not implement this calculation because the current mock data does not include daily sales or average demand, which is required to calculate the remaining days accurately.

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

`mock-socket` is kept as a development dependency because it is only required for the mock WebSocket server and tests.1

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
* The **Forecast Chart, Inventory Table, and Inventory Heatmap** update based on the selected filters.


# 7. Testing

I added tests using **Vitest** and **React Testing Library**.

All component test files are organized inside the `src/test` folder.

Tests were added for:

* `AlertsPanel`
* `ForecastChart`
* `InventoryHeatmap`
* `InventoryTable`
* `DashboardFilters`
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

# 8. Challenges Faced

### Loading, Empty, and Error States

Initially, I was not familiar with handling these states. After understanding the pattern, I implemented them across the required views.

The error states were also updated so they have reachable failure paths rather than only existing as unused UI branches.

The WebSocket error state is triggered when the maximum retry attempts are exhausted. The other dashboard views have simulated failure paths so their error UIs can also be rendered and tested.

The current loading states use simulated delays around locally imported mock data. They demonstrate the required loading UI behavior, but are not connected to real backend request latency yet.

When real API integration is added, the loading state should be driven by the actual asynchronous request.

### Virtualized Inventory Table

For the Inventory Table, I used virtualization with `react-window` to handle long lists more efficiently.

Instead of rendering all rows at once, only the rows needed for the visible scroll area are rendered. As the user scrolls, the required rows are rendered.

### Memoization and React Profiler

I used React `memo` selectively for components where avoiding unnecessary re-renders could improve performance.

I also used the React Profiler to observe component rendering time and identify components that were re-rendering.

One challenge was the Inventory Heatmap. The Heatmap receives filtered inventory data, so when warehouse or category filters change, its props also change. In this case, `memo` cannot prevent the re-render because the component actually needs to update with the new data.

The Profiler also did not always provide a separate client render result for the Heatmap, so the optimization could not be measured independently in every case. This helped me understand that memoization should be used based on actual prop changes and rendering behavior rather than applied to every component.


### Testing

While writing the tests, previous DOM elements were sometimes affecting the next test. Using `cleanup()` after each test fixed the issue and kept the tests isolated.

# 9. TypeScript Strict Mode

TypeScript strict mode is enabled for the dashboard.

This ensures that the TypeScript compiler performs stricter type checking during development and builds and helps prevent new type-safety issues from being introduced.

# 10. How to Run

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

# 11. Current UI and Next Steps

The current dashboard UI is functional and covers the required dashboard features, but the overall visual design and layout still need improvement.

In the next round, I will work on the UI using the available **UI component library** to improve consistency, spacing, alignment, responsiveness, and overall visual polish.

The functionality and dashboard logic are already implemented, so the next focus will be on improving the user experience and making the dashboard look more professional.

