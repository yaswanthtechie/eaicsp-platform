import client from "../graphql/apollo";
import { getRefreshToken, clearTokens } from "./tokenStorage";

const API_BASE_URL =
  import.meta.env.VITE_AUTH_URL || "http://localhost:8005";

export async function logout() {
  const refreshToken = getRefreshToken();

  try {
    if (refreshToken) {
      await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
      });
    }
  } finally {
    clearTokens();
    await client.clearStore();
    window.location.href = "/login";
  }
}