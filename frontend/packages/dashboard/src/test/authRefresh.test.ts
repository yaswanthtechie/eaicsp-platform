import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getAuthSession,
  refreshAuthSession,
  saveAuthSession,
} from "../api/auth";

function fakeJwt(): string {
  const payload = btoa(JSON.stringify({ role: "ceo", exp: 4102444800 }));
  return `header.${payload}.signature`;
}

function mockRefreshResponse() {
  return vi.fn(
    async () =>
      new Response(
        JSON.stringify({
          access_token: fakeJwt(),
          refresh_token: "new-refresh-token",
          token_type: "bearer",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  );
}

describe("refreshAuthSession", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it("shares one refresh request between concurrent callers", async () => {
    saveAuthSession({
      access_token: fakeJwt(),
      refresh_token: "old-refresh-token",
      token_type: "bearer",
    });
    const fetchMock = mockRefreshResponse();
    vi.stubGlobal("fetch", fetchMock);

    const [first, second] = await Promise.all([
      refreshAuthSession(),
      refreshAuthSession(),
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(first).toBe(second);
    expect(getAuthSession()?.refresh_token).toBe("new-refresh-token");
  });

  it("starts a new request once the previous one has finished", async () => {
    saveAuthSession({
      access_token: fakeJwt(),
      refresh_token: "old-refresh-token",
      token_type: "bearer",
    });
    const fetchMock = mockRefreshResponse();
    vi.stubGlobal("fetch", fetchMock);

    await refreshAuthSession();
    await refreshAuthSession();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});