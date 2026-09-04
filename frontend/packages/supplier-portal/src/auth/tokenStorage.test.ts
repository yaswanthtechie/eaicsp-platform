import { describe, it, expect, beforeEach } from "vitest";

import {
  saveTokens,
  getAccessToken,
  getRefreshToken,
  clearTokens,
  isAuthenticated,
  updateAccessToken,
} from "./tokenStorage";

describe("tokenStorage", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("stores tokens in localStorage when Remember Me is enabled", () => {
    saveTokens("access-123", "refresh-123", true);

    expect(localStorage.getItem("accessToken")).toBe("access-123");
    expect(localStorage.getItem("refreshToken")).toBe("refresh-123");

    expect(sessionStorage.getItem("accessToken")).toBeNull();
    expect(sessionStorage.getItem("refreshToken")).toBeNull();
  });

  it("stores tokens in sessionStorage when Remember Me is disabled", () => {
    saveTokens("access-123", "refresh-123", false);

    expect(sessionStorage.getItem("accessToken")).toBe("access-123");
    expect(sessionStorage.getItem("refreshToken")).toBe("refresh-123");

    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(localStorage.getItem("refreshToken")).toBeNull();
  });

  it("gets stored access and refresh tokens", () => {
    saveTokens("access-123", "refresh-123", true);

    expect(getAccessToken()).toBe("access-123");
    expect(getRefreshToken()).toBe("refresh-123");
  });

  it("checks authentication correctly", () => {
    expect(isAuthenticated()).toBe(false);

    saveTokens("access-123", "refresh-123", true);

    expect(isAuthenticated()).toBe(true);
  });

  it("clears tokens from both storages", () => {
    saveTokens("access-123", "refresh-123", true);

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("updates an access token in localStorage", () => {
    saveTokens("old-access", "refresh-123", true);

    updateAccessToken("new-access");

    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("refresh-123");
  });

  it("updates an access token in sessionStorage", () => {
    saveTokens("old-access", "refresh-123", false);

    updateAccessToken("new-access");

    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("refresh-123");
  });
});