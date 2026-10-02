import { readFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { buildSchema, graphql } from "graphql";
import type { Plugin } from "vite";
import { dashboardMock } from "../mocks/dashboardMock.ts";

// Executes real GraphQL against src/graphql/schema.graphql.
const schema = buildSchema(
  readFileSync(
    new URL("../graphql/schema.graphql", import.meta.url),
    "utf8",
  ),
);

const rootValue = {
  dashboard: () => dashboardMock,
};

interface GraphqlRequestBody {
  query?: unknown;
  variables?: unknown;
  operationName?: unknown;
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk: Buffer) => {
      body += chunk.toString();
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function sendJson(res: ServerResponse, status: number, payload: unknown) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(payload));
}

async function handleGraphql(
  req: IncomingMessage,
  res: ServerResponse,
  next: () => void,
) {
  if (req.url?.split("?")[0] !== "/graphql") {
    next();
    return;
  }

  if (req.method !== "POST") {
    sendJson(res, 405, { errors: [{ message: "Use POST" }] });
    return;
  }

  try {
    const body = JSON.parse(await readBody(req)) as GraphqlRequestBody;

    if (typeof body.query !== "string") {
      sendJson(res, 400, { errors: [{ message: "Missing query" }] });
      return;
    }

    const result = await graphql({
      schema,
      source: body.query,
      rootValue,
      variableValues:
        typeof body.variables === "object" && body.variables !== null
          ? (body.variables as Record<string, unknown>)
          : undefined,
      operationName:
        typeof body.operationName === "string"
          ? body.operationName
          : undefined,
    });

    sendJson(res, 200, result);
  } catch {
    sendJson(res, 400, { errors: [{ message: "Invalid JSON body" }] });
  }
}

// Serves POST /graphql from both npm run dev and npm run preview.
export function graphqlMockServer(): Plugin {
  return {
    name: "graphql-mock-server",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        void handleGraphql(req, res, next);
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        void handleGraphql(req, res, next);
      });
    },
  };
}