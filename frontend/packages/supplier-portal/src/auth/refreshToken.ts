import { getRefreshToken, saveTokens } from "./tokenStorage";

export async function refreshAccessToken() {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    throw new Error("No refresh token found");
  }

  // Temporary mock implementation
  const newAccessToken = "new-access-token";

  saveTokens(
    newAccessToken,
    refreshToken,
    true
  );

  return newAccessToken;
}