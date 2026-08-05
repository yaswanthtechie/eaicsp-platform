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
  keyArgs: [
    "status",
    "poNumber",
    "minAmount",
    "maxAmount",
    "startDate",
    "endDate",
  ],

  merge(existing, incoming, { args }) {
    if (!args?.after) {
      return incoming;
    }

    return {
      ...incoming,
      edges: [
        ...(existing?.edges ?? []),
        ...incoming.edges,
      ],
    };
  },
},
        },
      },
    },
  }),
});

export default client;