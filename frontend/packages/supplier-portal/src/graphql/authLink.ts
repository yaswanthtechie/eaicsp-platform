import { setContext } from "@apollo/client/link/context";

import {
  getAccessToken,
  getRefreshToken,
  updateAccessToken,
} from "../auth/tokenStorage";

import { isTokenExpiringSoon } from "../auth/tokenUtils";
import { refreshToken } from "../api/auth";

const authLink = setContext(async (_, { headers }) => {
  let accessToken = getAccessToken();

  if (accessToken && isTokenExpiringSoon(accessToken)) {
    const refresh = getRefreshToken();

    if (refresh) {
      try {
        const data = await refreshToken(refresh);

        updateAccessToken(data.access_token);

        accessToken = data.access_token;
      } catch (error) {
        console.error("Token refresh failed", error);
      }
    }
  }

  return {
    headers: {
      ...headers,
      Authorization: accessToken
        ? `Bearer ${accessToken}`
        : "",
    },
  };
});

export default authLink;