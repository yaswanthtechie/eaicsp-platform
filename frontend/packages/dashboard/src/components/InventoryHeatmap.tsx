import { useState, useEffect} from "react";
import { inventory } from "../mocks/inventory";
import { colors } from "../tokens";

export default function InventoryHeatmap() {
  const [hovered, setHovered] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  
    useEffect(() => {
      const timer = setTimeout(() =>{
        setLoading(false);
      },1000);
      return () =>clearTimeout(timer);
    },[]);
  
    if(loading){
      return <h2 style={{ color: colors.text}}>Loading Inventory Heatmap...</h2>;
    }
    if(error){
      return(
        <div>
          <h2>Something went wrong in Heatmap Data.</h2>
          <button onClick={() => setError(false)}>Retry</button>
        </div>
      );
    }
    if(inventory.length == 0){
      return <h2 style={{ color: colors.text}}>No  Inventory Heatmap data available.</h2>;
    }

  const getColor = (quantity: number, reorder: number)=> {
    if (quantity < reorder) {
        return colors.danger;
    }
    if (quantity < reorder * 1.5) {
        return colors.warning;
    }
    return colors.success;
  };

  const warehouses = ["WH001", "WH002", "WH003"];
  return (
    <div
      style={{
        background: colors.surface,
        padding: 20,
        borderRadius: 10,
      }}
    >
      <h2 style={{ color: colors.text,textAlign:"center" }}>
        Warehouse Inventory Heatmap
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
        }}
      >
        {warehouses.map((warehouse) => (
          <div key={warehouse}>
            <h3
              style={{
                color: colors.text,
                textAlign: "center",
              }}
            >
              {warehouse}
            </h3>

            {inventory
              .filter((item) => item.warehouse_id === warehouse)
              .map((item) => (
                <div
                  key={item.sku_id}
                  onMouseEnter={() => setHovered(item.sku_id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{
                    position: "relative",
                    padding: 15,
                    border: `1px solid ${colors.border}`,
                    color: colors.text,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span>{item.sku_id}</span>

                  <span
                    style={{
                      color: getColor(
                        item.quantity_on_hand,
                        item.reorder_point
                      ),
                    }}
                  >
                    ●
                  </span>

                  <span>{item.quantity_on_hand}</span>

                  {hovered === item.sku_id && (
                    <div
                      style={{
                        position: "absolute",
                        background: colors.bg,
                        padding: 10,
                        borderRadius: 6,
                        top: 35,
                        left: 20,
                        zIndex: 1,
                      }}
                    >
                      <div>SKU: {item.sku_id}</div>
                      <div>Product: {item.product_name}</div>
                      <div>Quantity: {item.quantity_on_hand}</div>
                      <div>Reorder Point: {item.reorder_point}</div>
                    </div>
                  )}
                </div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}