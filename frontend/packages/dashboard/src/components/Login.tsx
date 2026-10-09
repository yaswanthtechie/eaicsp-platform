import { useState, type FormEvent } from "react";
import { login, saveAuthSession } from "../api/auth";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { colors, radius, space } from "../tokens";

interface LoginProps {
  onLogin: () => void;
  errorMessage?: string;
}

export default function Login({ onLogin, errorMessage }: LoginProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(errorMessage ?? "");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      const tokens = await login(username, password);
      saveAuthSession(tokens);
      onLogin();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Login failed. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: colors.bg,
        padding: space.lg,
      }}
    >
      <Card
        style={{
          width: "100%",
          maxWidth: 400,
          borderRadius: radius.lg,
        }}
      >
        <CardHeader>
          <CardTitle>Executive Dashboard</CardTitle>
        </CardHeader>

        <CardContent>
          <form
            onSubmit={handleSubmit}
            style={{
              display: "grid",
              gap: space.md,
            }}
          >
            <Input
              type="email"
              placeholder="Email"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />

            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />

            {error && (
              <p
                role="alert"
                style={{
                  margin: 0,
                  color: colors.danger,
                }}
              >
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={loading}
            >
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}