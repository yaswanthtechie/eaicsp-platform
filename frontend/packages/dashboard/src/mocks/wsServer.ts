import { Server } from "mock-socket";
import type { AlertMessage, InventoryItem, InventoryUpdate } from "../types/forecast";


const alerts: Omit<AlertMessage, "id" | "timestamp">[] = [
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

  {
    type: "low-stock",
    severity: "error",
    message: "SKU004 (Cooking Oil) quantity below threshold",
  }
];

let serverStarted = false;

export function startMockWebSocketServer() {
  if (serverStarted) return;

  serverStarted = true;

  const server = new Server("ws://localhost:8080");

  server.on("connection", (socket) => {
    console.log("Mock WebSocket connected");

    let alertTimer: ReturnType<typeof setTimeout>;
    let inventoryTimer: ReturnType<typeof setTimeout>;

    const sendAlert = () => {
      const randomAlert =
        alerts[Math.floor(Math.random() * alerts.length)];

      const alert: AlertMessage = {
        id: crypto.randomUUID(),
        ...randomAlert,
        timestamp: new Date().toISOString(),
      };

      console.log(
        "Alert sent:",
        alert.timestamp,
        alert.message
      );

      socket.send(JSON.stringify(alert));

      const nextTime = 3000 + Math.random() * 2000;

      alertTimer = setTimeout(sendAlert, nextTime);
    };
    
    const sendInventoryUpdate = () => {
      const inventoryItem : InventoryItem = {
        sku_id: "SKU017",
        product_name: "Rice",
        category: "Food",
        warehouse_id: "WH004",
        quantity_on_hand: 40,
        reorder_point: 50,
        needs_reorder:  true,
        avg_daily_demand: 6
      };

      const update:InventoryUpdate = {
        type: "inventory_update",
        item: inventoryItem,
      };

      console.log("Inventory update sent:",update);

      socket.send(JSON.stringify(update));

      inventoryTimer = setTimeout(sendInventoryUpdate, 5000);

    };

    sendAlert();
    inventoryTimer = setTimeout(sendInventoryUpdate, 5000);

    socket.on("close", () => {
      clearTimeout(alertTimer);
      clearTimeout(inventoryTimer)

      console.log("Mock WebSocket disconnected.");
    });
  });

  console.log("Mock WebSocket server started");
}