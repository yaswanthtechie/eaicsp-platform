import {
  ApolloClient,
  InMemoryCache,
  HttpLink,
  from,
} from "@apollo/client";

import authLink from "./authLink";

const httpLink = new HttpLink({
  uri: import.meta.env.VITE_GRAPHQL_URL || "http://localhost:4000",
});

const client = new ApolloClient({
  link: from([
    authLink,
    httpLink,
  ]),

  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          purchaseOrders: {
            keyArgs: false,

            merge(existing = {}, incoming) {
              const existingEdges = existing.edges || [];
              const incomingEdges = incoming.edges || [];

              return {
                ...incoming,
                edges: [...existingEdges, ...incomingEdges],
              };
            },
          },
        },
      },
    },
  }),
});

export default client;