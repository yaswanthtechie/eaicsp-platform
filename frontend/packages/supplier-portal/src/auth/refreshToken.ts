import { getRefreshToken, updateAccessToken } from "./tokenStorage";
import { refreshToken } from "../api/auth";

export async function refreshAccessToken() {
  const refreshTokenValue = getRefreshToken();

  if (!refreshTokenValue) {
    throw new Error("No refresh token found");
  }

  const response = await refreshToken(refreshTokenValue);

  updateAccessToken(response.access_token);

  return response.access_token;
}