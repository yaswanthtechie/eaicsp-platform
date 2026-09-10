# Executive Dashboard

## Project Structure

frontend/

└── packages/
└── dashboard/
    └── src/
        ├── components/
        │   ├── AlertsPanel.tsx
        │   ├── ForecastChart.tsx
        │   ├── InventoryHeatmap.tsx
        │   ├── InventoryTable.tsx
        │   ├── AlertsPanel.test.tsx
        │   ├── ForecastChart.test.tsx
        │   ├── InventoryHeatmap.test.tsx
        │   └── InventoryTable.test.tsx
        │
        ├── hooks/
        │   ├── useWebSocket.ts
        │   └── useWebSocket.test.ts
        │
        ├── mocks/
        │   ├── api.ts
        │   ├── forecast.ts
        │   ├── inventory.ts
        │   └── wsServer.ts
        │
        ├── types/
        │   └── forecast.ts
        │
        ├── App.tsx
        ├── main.tsx
        └── tokens.ts

# 1. What I Built

I built an **Executive Dashboard** using React + TypeScript to give a quick view of sales forecasts, inventory, and important alerts.

The dashboard includes:

* **Sales Forecast Chart** using Recharts.
* **Inventory Table** with a low-stock filter.
* **Inventory Heatmap** for inventory.
* **Real-time Alert Panel** using WebSocket.
* Loading, empty, and error states.
* Automated tests for the main components and WebSocket hook.

# 2. Forecast Chart

The Forecast Chart shows sales forecast data using **Recharts**.

I added:

* Start date selection.
* End date selection.
* Forecast data for the selected date range.
* Reset button to return to the full chart.

This allows an executive to focus on a specific period instead of viewing the entire forecast at once.

The forecast also safely handles an empty dataset. The default start and end dates are calculated only after checking that forecast data exists, so an empty forecast can correctly reach the empty state instead of causing an error before the component renders.

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

`mock-socket` is kept as a development dependency because it is only required for the mock WebSocket server and tests.

# 6. Shared UI Components

The dashboard uses the shared UI components such as Button, Badge, Table, AlertBanner, and Spinner.

Currently, these components are imported directly from the shared UI source because the UI library is not yet set up as an `@eaicsp/ui` package.

**Known limitation:** The dashboard does not currently consume the UI library through an `@eaicsp/ui` package dependency or package entry point. The components are imported directly from the shared UI source using relative paths.

The proper `@eaicsp/ui` package integration is not completed yet. This requires changes to the shared UI package configuration and workspace dependency setup.


# 7. Testing

I added tests using **Vitest** and **React Testing Library**.

Tests were added for:

* `ForecastChart`
* `InventoryTable`
* `InventoryHeatmap`
* `AlertsPanel`
* `useWebSocket`

The tests cover things such as:

* Loading states.
* Empty states.
* Error states.
* User interactions.
* Date selection.
* Reset functionality.
* Inventory filtering.
* WebSocket connection states.
* Receiving alerts.
* Reconnection.
* Exponential backoff.

WebSocket tests also cover reconnect/backoff behavior, including retry attempts, increasing retry delays, successful reconnection, and failure after the maximum retry count is reached.

The tests verify that when the maximum retry count is exhausted, the WebSocket `failed` state becomes `true` and the Alerts Panel can display its error state.

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

When real API integration is added, the loading state should be driven by the actual asynchronous request lifecycle.

### Recharts

I had some difficulty while creating the forecast chart with Recharts. I referred to the documentation and examples to understand how the chart components work and then implemented the chart successfully.

I also fixed the empty forecast handling so default date calculations do not access forecast data before checking whether the dataset is empty.

### WebSocket Connection

While working on the Alert Panel, the WebSocket was repeatedly switching between connected and disconnected states.

I found that the connection logic was being triggered again because of unnecessary re-renders. I used `useCallback` to keep the connection function stable.

After that, I added automatic reconnection with **exponential backoff** and tested the behavior with the mock WebSocket server.

The hook also exposes a `failed` state when the maximum retry attempts are exhausted, allowing the Alerts Panel to display its error state.

Reconnect and backoff behavior is covered by the WebSocket test suite.

### Testing

While writing the tests, previous DOM elements were sometimes affecting the next test. Using `cleanup()` after each test fixed the issue and kept the tests isolated.

# 9. TypeScript Strict Mode

TypeScript strict mode is enabled for the dashboard.

This ensures that the TypeScript compiler performs stricter type checking during development and builds and helps prevent new type-safety issues from being introduced.

# 10. How to Run

Open the project in VS Code and run:

cd frontend/packages/dashboard

npm install

npm run build

npm run dev

To run the test suite all in VS Code Terminal run:

npm test


Open the local development URL shown in the terminal, for example:

`http://localhost:5173`

The dashboard uses the mock WebSocket server during development:

`ws://localhost:8080`

The mock WebSocket server is development-only and is not started as part of the production build.
