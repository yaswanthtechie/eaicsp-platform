const API_BASE_URL =
  import.meta.env.VITE_AUTH_URL || "http://localhost:8005";

export const login = async (
  username: string,
  password: string
) => {
  const formData = new URLSearchParams();

  formData.append("username", username);
  formData.append("password", password);

  const response = await fetch(
    `${API_BASE_URL}/api/v1/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error("Invalid credentials");
  }

  return response.json();
};

export const refreshToken = async (
  refreshToken: string
) => {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/auth/refresh`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    }
  );

  if (!response.ok) {
    throw new Error("Failed to refresh token");
  }

  return response.json();
};

export const revokeRefreshToken = async (
  refreshToken: string
) => {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/auth/logout`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refresh_token: refreshToken,
      }),
    }
  );

  if (!response.ok) {
    throw new Error("Failed to revoke refresh token");
  }
};