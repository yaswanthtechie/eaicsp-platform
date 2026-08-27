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

I built an **Executive Dashboard**  using react + TypeScript to give a quick view of sales forecasts, inventory, and important alerts.

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

# 3. Inventory Table

The Inventory Table shows inventory details for each SKU. I used the shared Table and Badge components from the UI library.

It also has SKU search bar  and a low-stock filter so users can quickly find items that need attention.

When no SKU matches the search, the empty state is passed correctly to the shared Table component. However, the empty-state styling currently comes from the shared UI component, so its background/color does not fully match the dashboard theme.

This is a shared UI styling issue, not an issue with the inventory search or filtering logic.

# 4. Inventory Risk & Reorder Planning

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

ws://localhost:8080

The server sends fake alerts to simulate real-time inventory events.

The WebSocket hook handles:

* Connection status.
* Receiving alerts.
* Disconnection.
* Automatic reconnection.
* Exponential backoff.
* Maximum retry attempts.

The Alert Panel displays the received alerts with their:

* Type
* Message
* Severity

This allows executives to see important inventory events as they happen.

# 6. Shared UI Components

I also started using the shared UI components instead of creating separate versions inside the dashboard.

I used components such as:

* `Badge`
* `Button`
* `Table`
* `AlertBanner`
* `Spinner`

This keeps the dashboard consistent with the rest of the application and makes the UI components reusable.

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

## Test Cleanup

While creating the tests, I faced an issue where the DOM from one test could affect another test.

I fixed this by using `cleanup()` after every test so that each test starts with a fresh DOM.

For example:

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

This was especially useful for tests that use fake timers and WebSocket reconnection delays.

# 8. Challenges Faced

### Loading, Empty, and Error States

Initially, I was not familiar with handling these states. After understanding the pattern, I implemented them across the required views.

### Recharts

I had some difficulty while creating the forecast chart with Recharts. I referred to the documentation and examples to understand how the chart components work and then implemented the chart successfully.

### WebSocket Connection

While working on the Alert Panel, the WebSocket was repeatedly switching between connected and disconnected states.

I found that the connection logic was being triggered again because of unnecessary re-renders. I used `useCallback` to keep the connection function stable.

After that, I added automatic reconnection with **exponential backoff** and tested the behavior with the mock WebSocket server.

### Testing

While writing the tests, previous DOM elements were sometimes affecting the next test. Using `cleanup()` after each test fixed the issue and kept the tests isolated.

# 9. How to Run

Open the project in VS Code and run:

cd frontend/packages/dashboard
npm install
npm build
npm run dev

To run the test suite all in VS Code Terminal run:

npm test


Open the local development URL shown in the terminal, for example:

http://localhost:5173

The dashboard uses the mock WebSocket server:

ws://localhost:8080

