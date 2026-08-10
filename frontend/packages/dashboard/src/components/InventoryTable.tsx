import { useState,useEffect } from "react";
import { inventory } from "../mocks/inventory";
import { colors } from "../tokens";

export default function InventoryTable() {
  const [showLowStock, setShowLowStock] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() =>{
      setLoading(false);
    },1000);
    return () =>clearTimeout(timer);
  },[]);

  if(loading){
    return <h2>Loading Inventory Table...</h2>;
  }
  if(error){
    return(
      <div>
        <h2>Something went wrong in table.</h2>
        <button onClick={() => setError(false)}>Retry</button>
      </div>
    );
  }
  if(inventory.length == 0){
    return <h2>No Table data available.</h2>;
  }
  const filteredInventory = inventory.filter((item) => {
    if (showLowStock) {
      return item.needs_reorder;
    }
    return true;
  });

  return (
    <div
      style={{
        background: colors.surface,
        padding: 20,
        borderRadius: 10,
        marginTop: 30,
      }}
    >
      <h2 style={{ color: colors.text,textAlign:"center" }}>
        Inventory Table
      </h2>
      <label
        style={{
          color: colors.text,
          display: "block",
          marginBottom: 15,
        }}
      >
        <input
          type="checkbox"
          checked={showLowStock}
          onChange={(e) => setShowLowStock(e.target.checked)}
        />

        {" "}Show only low stock
      </label>

      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
        }}
      >
        <thead>
          <tr
            style={{
              background: colors.primary,
              color: "white",
            }}
          >
            <th style={{ padding: 10 }}>sku_id</th>

            <th style={{ padding: 10 }}>product_name</th>

            <th style={{ padding: 10 }}>warehouse_id</th>

            <th style={{ padding: 10 }}>quantity_on_hand</th>

            <th style={{ padding: 10 }}>reorder_point</th>

            <th style={{ padding: 10 }}>needs_reorder</th>
          </tr>
        </thead>

        <tbody>
          {filteredInventory.map((item) => (
            <tr
              key={item.sku_id}
              style={{
                borderBottom: `1px solid ${colors.border}`,
                textAlign: "center",
                color: colors.text,
              }}
            >
              <td style={{ padding: 10 }}>
                {item.sku_id}
              </td>

              <td style={{ padding: 10 }}>
                {item.product_name}
              </td>

              <td style={{ padding: 10 }}>
                {item.warehouse_id}
              </td>

              <td style={{ padding: 10 }}>
                {item.quantity_on_hand}
              </td>

              <td style={{ padding: 10 }}>
                {item.reorder_point}
              </td>

              <td style={{ padding: 5 }}>
                {item.needs_reorder ? (
                  <span
                    style={{
                      background: colors.danger,
                      color: "white",
                      padding: "5px 12px",
                      borderRadius: "20px",
                      fontSize: "14px",
                    }}
                  >
                    Low Stock
                  </span>
                ) : (
                  <span
                    style={{
                      background: colors.success,
                      color: "white",
                      padding: "5px 12px",
                      borderRadius: "20px",
                      fontSize: "14px",
                    }}
                  >
                    In Stock
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}