import AppRoutes from "./routes/AppRoutes";
import OfflineBanner from "./components/OfflineBanner";

function App() {
  return (
    <>
      <OfflineBanner />
      <AppRoutes />
    </>
  );
}

export default App;