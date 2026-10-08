export type UserRole = "ceo" | "warehouse_manager";

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface LoginErrorResponse {
  detail?: string;
}

interface JwtPayload {
  exp?: number;
  role?: string;
}

const AUTH_BASE_URL =
  import.meta.env.VITE_AUTH_BASE_URL;

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as LoginErrorResponse;

    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Ignore invalid error response bodies.
  }

  return `Authentication request failed (${response.status})`;
}

export async function login(
  username: string,
  password: string,
): Promise<AuthTokens> {
  const body = new URLSearchParams({
    username,
    password,
  });

  let response: Response;

  try {
    response = await fetch(`${AUTH_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
  } catch {
    throw new Error("Authentication service is unavailable.");
  }

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return (await response.json()) as AuthTokens;
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<AuthTokens> {
  let response: Response;

  try {
    response = await fetch(`${AUTH_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    });
  } catch {
    throw new Error("Authentication service is unavailable.");
  }

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return (await response.json()) as AuthTokens;
}

export async function logout(refreshToken: string): Promise<void> {
  try {
    await fetch(`${AUTH_BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    });
  } catch {
    // The local session will still be cleared.
  }
}

export function getRoleFromToken(accessToken: string): UserRole {
  const parts = accessToken.split(".");

  if (parts.length !== 3) {
    throw new Error("Invalid authentication token.");
  }

  try {
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as JwtPayload;

    if (payload.role === "ceo" || payload.role === "warehouse_manager") {
      return payload.role;
    }
  } catch {
    throw new Error("Invalid authentication token.");
  }

  throw new Error("Authentication token does not contain a supported role.");
}

export function getTokenExpiry(accessToken: string): number {
  const parts = accessToken.split(".");

  if (parts.length !== 3) {
    throw new Error("Invalid authentication token.");
  }

  try {
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
    ) as JwtPayload;

    if (typeof payload.exp === "number") {
      return payload.exp * 1000;
    }
  } catch {
    // Fall through to the error below.
  }

  throw new Error("Authentication token does not contain an expiry.");
}

const AUTH_SESSION_KEY = "dashboard_auth";

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: UserRole;
}

export function saveAuthSession(tokens: AuthTokens): AuthSession {
  const session: AuthSession = {
    ...tokens,
    role: getRoleFromToken(tokens.access_token),
  };

  sessionStorage.setItem(
    AUTH_SESSION_KEY,
    JSON.stringify(session),
  );

  return session;
}

export function getAuthSession(): AuthSession | null {
  const stored = sessionStorage.getItem(AUTH_SESSION_KEY);

  if (!stored) {
    return null;
  }

  try {
    const session = JSON.parse(stored) as AuthSession;

    if (
      typeof session.access_token !== "string" ||
      typeof session.refresh_token !== "string" ||
      (session.role !== "ceo" &&
        session.role !== "warehouse_manager")
    ) {
      sessionStorage.removeItem(AUTH_SESSION_KEY);
      return null;
    }

    return session;
  } catch {
    sessionStorage.removeItem(AUTH_SESSION_KEY);
    return null;
  }
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(AUTH_SESSION_KEY);
}

export function updateAuthSession(tokens: AuthTokens): AuthSession {
  return saveAuthSession(tokens);
}

export async function refreshAuthSession(): Promise<AuthSession> {
  const session = getAuthSession();

  if (!session) {
    throw new Error("No authentication session.");
  }

  const tokens = await refreshAccessToken(session.refresh_token);

  return updateAuthSession(tokens);
}
