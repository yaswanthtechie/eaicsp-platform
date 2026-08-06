import client from "../graphql/apollo";
import { clearTokens } from "./tokenStorage";

export async function logout() {
  clearTokens();

  await client.clearStore();

  window.location.href = "/login";
}