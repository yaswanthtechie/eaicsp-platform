import { setContext } from "@apollo/client/link/context";
import { getAccessToken } from "../auth/tokenStorage";

const authLink = setContext((_, { headers }) => {
  const token = getAccessToken();

  return {
    headers: {
      ...headers,
      Authorization: token ? `Bearer ${token}` : "",
    },
  };
});

export default authLink;