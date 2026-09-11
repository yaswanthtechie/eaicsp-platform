import {
  ApolloClient,
  InMemoryCache,
  HttpLink,
  from,
} from "@apollo/client";

import authLink from "./authLink";

interface PurchaseOrderEdge {
  cursor: string;
}

interface PurchaseOrderConnection {
  edges: PurchaseOrderEdge[];
  pageInfo: {
    hasNextPage: boolean;
    endCursor: string | null;
  };
}

const httpLink = new HttpLink({
  uri:
    import.meta.env.VITE_GRAPHQL_URL ||
    "http://localhost:4000/graphql",
});

const client = new ApolloClient({
  link: from([
    authLink,
    httpLink,
  ]),

  cache: new InMemoryCache({
    typePolicies: {
      PurchaseOrder: {
        keyFields: ["poNumber"],
      },

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

            merge(
              existing: PurchaseOrderConnection | undefined,
              incoming: PurchaseOrderConnection,
              { args }
            ) {
              const existingEdges =
                existing?.edges ?? [];

              const incomingEdges =
                incoming.edges ?? [];

              // First page / refresh:
              // Keep previously loaded pages when the
              // first page is fetched again.
              if (!args?.after) {
                if (existingEdges.length === 0) {
                  return incoming;
                }

                const incomingCursors = new Set(
                  incomingEdges.map(
                    (edge) => edge.cursor
                  )
                );

                const existingAdditionalEdges =
                  existingEdges.filter(
                    (edge) =>
                      !incomingCursors.has(edge.cursor)
                  );

                return {
                  ...incoming,
                  edges: [
                    ...incomingEdges,
                    ...existingAdditionalEdges,
                  ],
                  pageInfo:
                    existingAdditionalEdges.length > 0
                      ? existing?.pageInfo ??
                        incoming.pageInfo
                      : incoming.pageInfo,
                };
              }

              // Load More:
              // Append only edges that are not already cached.
              const existingCursors = new Set(
                existingEdges.map(
                  (edge) => edge.cursor
                )
              );

              const newEdges =
                incomingEdges.filter(
                  (edge) =>
                    !existingCursors.has(edge.cursor)
                );

              return {
                ...incoming,
                edges: [
                  ...existingEdges,
                  ...newEdges,
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