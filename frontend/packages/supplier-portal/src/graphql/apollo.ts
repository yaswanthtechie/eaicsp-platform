import { ApolloClient, InMemoryCache } from "@apollo/client";

const client = new ApolloClient({
  uri: import.meta.env.VITE_GRAPHQL_URL || "http://localhost:4000",
  cache: new InMemoryCache(),
});

export default client;