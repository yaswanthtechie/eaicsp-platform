import { Routes, Route, Navigate } from "react-router-dom";

import Login from "../pages/Login";
import Orders from "../pages/Orders";
import OrderDetails from "../pages/OrderDetails";
import Invoice from "../pages/Invoice";

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" />} />

      <Route path="/login" element={<Login />} />

      <Route path="/orders" element={<Orders />} />
      

      <Route
        path="/orders/:poNumber"
        element={<OrderDetails />}
      />

      <Route
        path="/invoices/new"
        element={<Invoice />}
      />
    </Routes>
  );
}