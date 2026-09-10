import client from "../graphql/apollo";
import { revokeRefreshToken } from "../api/auth";
import { getRefreshToken, clearTokens } from "./tokenStorage";

export async function logout() {
  const refreshToken = getRefreshToken();

  try {
    if (refreshToken) {
      await revokeRefreshToken(refreshToken);
    }
  } finally {
    clearTokens();
    await client.clearStore();
    window.location.href = "/login";
  }
}