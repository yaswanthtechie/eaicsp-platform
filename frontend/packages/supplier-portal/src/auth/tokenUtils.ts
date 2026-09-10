import { jwtDecode } from "jwt-decode";

type JwtPayload = {
  exp: number;
};

export function isTokenExpiringSoon(
  token: string,
  minutesBeforeExpiry = 1
): boolean {
  try {
    const decoded = jwtDecode<JwtPayload>(token);

    const currentTime = Date.now() / 1000;

    return decoded.exp - currentTime <= minutesBeforeExpiry * 60;
  } catch {
    return true;
  }
}