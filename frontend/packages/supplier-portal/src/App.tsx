import AppRoutes from "./routes/AppRoutes";
import OfflineBanner from "./components/OfflineBanner";
import { useOfflineActionSync } from "./hooks/useOfflineActionSync";

function App() {
  useOfflineActionSync();

  return (
    <>
      <OfflineBanner />
      <AppRoutes />
    </>
  );
}

export default App;