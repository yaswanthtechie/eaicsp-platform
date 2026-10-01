import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { buildASTSchema, parse } from "graphql";

describe("GraphQL schema", () => {
  it("parses successfully", () => {
    const schemaPath = resolve(
      process.cwd(),
      "src/graphql/schema.graphql"
    );

    const schema = readFileSync(schemaPath, "utf8");

    expect(() => {
      buildASTSchema(parse(schema));
    }).not.toThrow();
  });
});