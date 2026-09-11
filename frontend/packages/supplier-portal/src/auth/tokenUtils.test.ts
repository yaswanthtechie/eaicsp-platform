import { describe, it, expect, vi, afterEach } from "vitest";
import { isTokenExpiringSoon } from "./tokenUtils";

describe("isTokenExpiringSoon", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns false when the token expires later than 1 minute", () => {
    const currentTime = 1000000;

    vi.spyOn(Date, "now").mockReturnValue(currentTime * 1000);

    // exp = current time + 5 minutes
    const token = [
      btoa(JSON.stringify({ alg: "none", typ: "JWT" })),
      btoa(JSON.stringify({ exp: currentTime + 5 * 60 })),
      "",
    ].join(".");

    expect(isTokenExpiringSoon(token)).toBe(false);
  });

  it("returns true when the token expires within 1 minute", () => {
    const currentTime = 1000000;

    vi.spyOn(Date, "now").mockReturnValue(currentTime * 1000);

    // exp = current time + 30 seconds
    const token = [
      btoa(JSON.stringify({ alg: "none", typ: "JWT" })),
      btoa(JSON.stringify({ exp: currentTime + 30 })),
      "",
    ].join(".");

    expect(isTokenExpiringSoon(token)).toBe(true);
  });

  it("returns true when the token is already expired", () => {
    const currentTime = 1000000;

    vi.spyOn(Date, "now").mockReturnValue(currentTime * 1000);

    // exp = current time - 1 minute
    const token = [
      btoa(JSON.stringify({ alg: "none", typ: "JWT" })),
      btoa(JSON.stringify({ exp: currentTime - 60 })),
      "",
    ].join(".");

    expect(isTokenExpiringSoon(token)).toBe(true);
  });

  it("returns true for an invalid token", () => {
    expect(isTokenExpiringSoon("invalid-token")).toBe(true);
  });

  it("supports a custom expiry window", () => {
    const currentTime = 1000000;

    vi.spyOn(Date, "now").mockReturnValue(currentTime * 1000);

    // Token expires in 3 minutes.
    // With a 5-minute warning window, it should return true.
    const token = [
      btoa(JSON.stringify({ alg: "none", typ: "JWT" })),
      btoa(JSON.stringify({ exp: currentTime + 3 * 60 })),
      "",
    ].join(".");

    expect(isTokenExpiringSoon(token, 5)).toBe(true);
  });
});