# Executive Dashboard
## Project Structure

frontend/
└── packages/
    └── dashboard/
        ├── public/
        ├── src/
        │   ├── assets/
        │   ├── components/
        │   │   ├── ForecastChart.tsx
        │   │   └── InventoryTable.tsx
        │   ├── mocks/
        │   │   ├── forecast.ts
        │   │   └── inventory.ts
        │   ├── types/
        │   │   └── forecast.ts
        │   ├── App.tsx
        │   ├── index.css
        │   ├── main.tsx
        │   └── tokens.ts
        ├── .gitignore
        ├── eslint.config.js
        ├── index.html
        ├── package.json
        ├── tsconfig.json
        ├── vite.config.ts
        └── README.md




## 1. I Built

* Built a **Sales Forecast Chart** using **Recharts** with mock sales data.
* Created an **Inventory Table** for the Executive Dashboard.
* Added a filter to display only the products with **low stock**.


## 2. How to Run the Project

1. Open the project in **VS Code**.
2. Open the terminal and run:

npm run dev

3. Open the local development URL displayed in the terminal (for example, `http://localhost:5173`) in Chrome or any other web browser.

## 3. If I Had Another Day

If I had another day, I would add more mock sales data to the forecast chart. The current chart uses only a small dataset to demonstrate the functionality, and adding more data would make the chart more meaningful and realistic.


## 4. Challenges Faced

While implementing the **Loading**, **Empty**, and **Error** states, I initially got stuck because I was not familiar with handling these states. After understanding the concept, I was able to implement them and now feel comfortable working with these states.

I also faced some difficulty while creating the sales forecast chart using Recharts. I referred to the Recharts documentation and the examples provided to understand how the chart components work. After practicing, I was able to build the chart successfully and gained confidence in using Recharts.


# Round - 2
## Forecast Chart, WebSocket, and Alert Panel Integration

I worked on enhancing the forecast chart by adding a **date calendar option**, allowing executives to select custom **start and end dates** and view the forecast data for the selected date range and added **reset button** to get back  the full chart.

I implemented the **useWebSocket** hook to manage the WebSocket connection. It helps track whether the server is started and whether the client is connected or disconnected. The main socket communication happens through this hook, which receives data from the mock WebSocket server.

After that, I built the **Alert Panel**, where executives can see real-time alerts coming from the mock WebSocket server. Each alert contains a **type, message, and severity**. The main alert logic is defined in the mock WebSocket server, which sends alerts with different types and severity levels.Provide alerts to the executive.

Finally, I integrated all these components into **App.tsx**  with i used server these should connect both as the same port number(`ws://localhost:8080`) and connected the application flow through **main.tsx**, making the complete functionality visible on the executive dashboard.

# Run the project
1. Open the project in **VS Code**.
2. Open the terminal and run:

npm install mock-socket
npm run dev 


# Challenges  Faced

While working on the Alert Panel, I faced an issue where the panel was working correctly, but the WebSocket connection was repeatedly showing  **connected and disconnected** states on close with alerts are changing very fast. 
After researching the issue, I found that unnecessary re-renders were causing the connection logic to run again. I used **useCallback** to keep the function reference stable, which prevented unnecessary re-renders and resolved the connection issue.
