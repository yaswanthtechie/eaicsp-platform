import { Server } from "mock-socket";

interface MockAlert {
  id: string;
  type: "low-stock" | "forecast-change" | "system";
  severity: "error" | "warning" | "info";
  message: string;
  timestamp: string;
}

const alerts: Omit<MockAlert, "id" | "timestamp">[] = [
  {
    type: "low-stock",
    severity: "error",
    message: "SKU007 (Chocolates) quantity below threshold",
  },
  {
    type: "low-stock",
    severity: "warning",
    message: "SKU012 (Shampoo) reorder needed",
  },
  {
    type: "forecast-change",
    severity: "warning",
    message: "Predicted demand increased 12% for next week",
  },
  {
    type: "forecast-change",
    severity: "warning",
    message: "Predicted demand decreased 12% for next week",
  },
  {
    type: "low-stock",
    severity: "warning",
    message: "SKU014 (Detergent) reorder needed",
  },
  {
    type: "system",
    severity: "info",
    message: "Dashboard data sync completed",
  },
  {
    type: "low-stock",
    severity: "warning",
    message: "SKU009 (Biscuits) quantity below threshold",
  },
  {
    type: "system",
    severity: "info",
    message: "Forecast model updated successfully",
  },
];

let serverStarted = false;

export function startMockWebSocketServer() {
  if (serverStarted) return;

  serverStarted = true;

  const server = new Server("ws://localhost:8080");

  server.on("connection", (socket) => {
    console.log("Mock WebSocket connected..");

    const sendAlert = () => {
      const randomAlert =
        alerts[Math.floor(Math.random() * alerts.length)];

      const alert: MockAlert = {
        id: crypto.randomUUID(),
        ...randomAlert,
        timestamp: new Date().toISOString(),
      };

      socket.send(JSON.stringify(alert));

      const nextTime = 3000 + Math.random() * 2000;

      setTimeout(sendAlert, nextTime);
    };

    sendAlert();

    socket.on("close", () => {
      console.log("Mock WebSocket disconnected..");
    });
  });

  console.log("Mock WebSocket server started");
}