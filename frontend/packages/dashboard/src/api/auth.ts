import type { UserRole } from "../mocks/user";

export type { UserRole };

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthSession extends AuthTokens {
  role: UserRole;
}

interface ErrorResponse {
  detail?: unknown;
}

interface TokenOrMfaResponse {
  access_token?: unknown;
  refresh_token?: unknown;
  token_type?: unknown;
  mfa_required?: unknown;
}

interface JwtPayload {
  exp?: unknown;
  role?: unknown;
}

/**
 * "unauthorized" - the platform rejected us (wrong password, expired or
 *                  revoked token). The user has to sign in again.
 * "unavailable"  - the platform could not be reached or failed (5xx).
 *                  Worth retrying; not the user's fault.
 * "unsupported"  - signed in fine, but this dashboard can't serve the
 *                  account (role without a view, MFA account).
 */
export type AuthErrorKind = "unauthorized" | "unavailable" | "unsupported";

export class AuthError extends Error {
  readonly kind: AuthErrorKind;

  constructor(kind: AuthErrorKind, message: string) {
    super(message);
    this.name = "AuthError";
    this.kind = kind;
  }
}

const SERVICE_UNAVAILABLE = "Authentication service is unavailable.";

// Empty means same origin: in dev, the Vite proxy forwards
// /api/v1/auth to the platform service on :8005 (see vite.config.ts).
const AUTH_BASE_URL: string = import.meta.env.VITE_AUTH_BASE_URL ?? "";

const AUTH_SESSION_KEY = "dashboard_auth";

async function postToAuth(
  path: string,
  init: RequestInit,
): Promise<Response> {
  try {
    return await fetch(`${AUTH_BASE_URL}/api/v1/auth${path}`, {
      method: "POST",
      ...init,
    });
  } catch {
    throw new AuthError("unavailable", SERVICE_UNAVAILABLE);
  }
}

async function errorFromResponse(response: Response): Promise<AuthError> {
  // When the platform is down, the Vite proxy answers with a 5xx
  // instead of the fetch failing, so treat 5xx as "unavailable" too.
  if (response.status >= 500) {
    return new AuthError("unavailable", SERVICE_UNAVAILABLE);
  }

  let message = `Authentication request failed (${response.status})`;

  try {
    const body = (await response.json()) as ErrorResponse;

    if (typeof body.detail === "string") {
      message = body.detail;
    }
  } catch {
    // Keep the generic message for non-JSON error bodies.
  }

  return new AuthError("unauthorized", message);
}

async function readTokens(response: Response): Promise<AuthTokens> {
  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  const body = (await response.json()) as TokenOrMfaResponse;

  if (body.mfa_required === true) {
    throw new AuthError(
      "unsupported",
      "This account uses multi-factor sign-in, which the dashboard does not support yet.",
    );
  }

  if (
    typeof body.access_token !== "string" ||
    typeof body.refresh_token !== "string"
  ) {
    throw new AuthError(
      "unavailable",
      "Unexpected response from the authentication service.",
    );
  }

  return {
    access_token: body.access_token,
    refresh_token: body.refresh_token,
    token_type: typeof body.token_type === "string" ? body.token_type : "bearer",
  };
}

export async function login(
  username: string,
  password: string,
): Promise<AuthTokens> {
  const response = await postToAuth("/login", {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      username,
      password,
    }),
  });

  return readTokens(response);
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<AuthTokens> {
  const response = await postToAuth("/refresh", {
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      refresh_token: refreshToken,
    }),
  });

  return readTokens(response);
}

/**
 * Revoke the refresh token on the platform. The platform's /logout
 * requires the access token as a Bearer header, and rejects the call
 * with 401 without it.
 */
export async function logout(session: AuthTokens): Promise<void> {
  try {
    await postToAuth("/logout", {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        refresh_token: session.refresh_token,
      }),
    });
  } catch {
    // The local session is cleared by the caller either way.
  }
}

function decodeJwtPayload(token: string): JwtPayload {
  const parts = token.split(".");

  if (parts.length !== 3) {
    throw new AuthError("unauthorized", "Invalid authentication token.");
  }

  try {
    const json = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    const payload: unknown = JSON.parse(json);

    if (typeof payload === "object" && payload !== null) {
      return payload as JwtPayload;
    }
  } catch {
    // Fall through to the error below.
  }

  throw new AuthError("unauthorized", "Invalid authentication token.");
}

export function isUserRole(value: unknown): value is UserRole {
  return value === "ceo" || value === "warehouse_manager";
}

export function getRoleFromToken(accessToken: string): UserRole {
  const { role } = decodeJwtPayload(accessToken);

  if (!isUserRole(role)) {
    throw new AuthError(
      "unsupported",
      "Your account's role does not have access to this dashboard.",
    );
  }

  return role;
}

export function getTokenExpiry(accessToken: string): number {
  const { exp } = decodeJwtPayload(accessToken);

  if (typeof exp !== "number") {
    throw new AuthError(
      "unauthorized",
      "Authentication token does not contain an expiry.",
    );
  }

  return exp * 1000;
}

function toSession(tokens: AuthTokens): AuthSession {
  // Both throw for a token we can't use, so a bad token never
  // reaches the dashboard.
  getTokenExpiry(tokens.access_token);

  return {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
    token_type: tokens.token_type,
    role: getRoleFromToken(tokens.access_token),
  };
}

export function saveAuthSession(tokens: AuthTokens): AuthSession {
  const session = toSession(tokens);

  sessionStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));

  return session;
}

export function getAuthSession(): AuthSession | null {
  const stored = sessionStorage.getItem(AUTH_SESSION_KEY);

  if (!stored) {
    return null;
  }

  try {
    const parsed = JSON.parse(stored) as Partial<AuthTokens>;

    if (
      typeof parsed.access_token !== "string" ||
      typeof parsed.refresh_token !== "string"
    ) {
      throw new Error("Malformed session");
    }

    // The role is always re-read from the token, never trusted
    // from what was stored next to it.
    return toSession({
      access_token: parsed.access_token,
      refresh_token: parsed.refresh_token,
      token_type: parsed.token_type ?? "bearer",
    });
  } catch {
    sessionStorage.removeItem(AUTH_SESSION_KEY);
    return null;
  }
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(AUTH_SESSION_KEY);
}

export async function refreshAuthSession(): Promise<AuthSession> {
  const session = getAuthSession();

  if (!session) {
    throw new AuthError("unauthorized", "No authentication session.");
  }

  const tokens = await refreshAccessToken(session.refresh_token);

  return saveAuthSession(tokens);
}