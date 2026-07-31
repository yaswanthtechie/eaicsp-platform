import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { saveTokens } from "../auth/tokenStorage";

const Login = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState("");
  const [rememberMe, setRememberMe] = useState(false);  
  const [password, setPassword] = useState("");

  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");

  const validate = () => {
    let valid = true;

    setEmailError("");
    setPasswordError("");

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (!emailRegex.test(email)) {
      setEmailError("Enter a valid email");
      valid = false;
    }

    if (password.trim() === "") {
      setPasswordError("Password is required");
      valid = false;
    }

    return valid;
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    saveTokens(
  "dummy-access-token",
  "dummy-refresh-token",
  rememberMe
);

const nextPage = searchParams.get("next") || "/orders";
navigate(nextPage);
  };

  return (
    <div className="login-page">
      <h1>Supplier Portal</h1>

      <form onSubmit={handleLogin}>

        <label>Email</label>

        <input
          type="email"
          placeholder="Enter Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        {emailError && (
          <p className="error">{emailError}</p>
        )}

        <label>Password</label>

        <input
          type="password"
          placeholder="Enter Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {passwordError && (
          <p className="error">{passwordError}</p>
        )}
        <div className="remember-me">
  <label>
    <input
      type="checkbox"
      checked={rememberMe}
      onChange={(e) => setRememberMe(e.target.checked)}
    />
    Remember Me
  </label>
</div>

        <button type="submit">
          Login
        </button>

      </form>

      <p className="note">
        Any valid email and password will work.
      </p>

    </div>
  );
};

export default Login;