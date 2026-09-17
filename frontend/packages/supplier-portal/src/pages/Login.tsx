import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { saveTokens } from "../auth/tokenStorage";
import { login } from "../api/auth";

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Email is required")
    .email("Enter a valid email"),

  password: z
    .string()
    .min(1, "Password is required"),

  rememberMe: z.boolean(),
});

type LoginFormData =
  z.infer<typeof loginSchema>;

const Login = () => {
  const navigate = useNavigate();

  const [searchParams] =
    useSearchParams();

  const {
    register,
    handleSubmit,
    setError,
    formState: {
      errors,
      isSubmitting,
    },
  } = useForm<LoginFormData>({
    resolver:
      zodResolver(loginSchema),

    defaultValues: {
      email: "",
      password: "",
      rememberMe: false,
    },
  });

  const onSubmit = async (
    data: LoginFormData,
  ) => {
    try {
      const response =
        await login(
          data.email,
          data.password,
        );

      saveTokens(
        response.access_token,
        response.refresh_token,
        data.rememberMe,
      );

      const nextParam =
        searchParams.get("next");

      const isInternal = (
        next: string | null,
      ): boolean => {
        if (!next) {
          return false;
        }

        const url = new URL(
          next,
          window.location.origin,
        );

        return (
          url.origin ===
          window.location.origin
        );
      };

      const nextPage =
        isInternal(nextParam) &&
        nextParam
          ? nextParam
          : "/orders";

      navigate(nextPage);
    } catch {
      setError("password", {
        type: "server",
        message:
          "Invalid email or password",
      });
    }
  };

  return (
    <div className="login-page">
      <h1>
        Supplier Portal
      </h1>

      <form
        onSubmit={handleSubmit(
          onSubmit,
        )}
      >
        <label htmlFor="email">
          Email
        </label>

        <input
          id="email"
          type="email"
          placeholder="Enter Email"
          {...register("email")}
          aria-invalid={Boolean(
            errors.email,
          )}
        />

        {errors.email && (
          <p
            className="error"
            role="alert"
          >
            {errors.email.message}
          </p>
        )}

        <label htmlFor="password">
          Password
        </label>

        <input
          id="password"
          type="password"
          placeholder="Enter Password"
          {...register("password")}
          aria-invalid={Boolean(
            errors.password,
          )}
        />

        {errors.password && (
          <p
            className="error"
            role="alert"
          >
            {errors.password.message}
          </p>
        )}

        <div className="remember-me">
          <input
            type="checkbox"
            id="rememberMe"
            {...register(
              "rememberMe",
            )}
          />

          <label htmlFor="rememberMe">
            Remember Me
          </label>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting
            ? "Logging in..."
            : "Login"}
        </button>
      </form>

      <p className="note">
        Any valid email and password
        will work.
      </p>
    </div>
  );
};

export default Login;