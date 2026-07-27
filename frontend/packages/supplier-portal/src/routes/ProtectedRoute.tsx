import { Navigate } from "react-router-dom";
import { TOKEN_KEY } from "../constants/storage";


type ProtectedRouteProps = {
  children: React.ReactNode;
};

export default function ProtectedRoute({
  children,
}: ProtectedRouteProps) {
  const token = localStorage.getItem(TOKEN_KEY);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}