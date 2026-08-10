import ForecastChart from "./components/ForecastChart";
import InventoryTable from "./components/InventoryTable";
import { colors } from "./tokens";

function App() {
  return (
    <div
      style={{
        background: colors.bg,
        minHeight: "100vh",
        padding: 20,
      }}
    >
      <div
        style={{
          background: colors.surface,
          padding: 20,
          borderRadius: 10,
          marginBottom: 20,
        }}
      >
        <h1
          style={{
            color: colors.text,
            textAlign: "center",
            margin: 0,
          }}
        >
          Executive Dashboard
        </h1>
      </div>
      
      <div
        style={{
          background: colors.surface,
          padding: 20,
          borderRadius: 10,
          marginBottom: 20,
        }}
      >
        <ForecastChart />
      </div>

      <div
        style={{
          background: colors.surface,
          padding: 20,
          borderRadius: 10,
        }}
      >
        <InventoryTable />
      </div>
    </div>
  );
}

export default App;