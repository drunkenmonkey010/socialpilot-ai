const TOKEN_KEY = "socialpilot_access_token";
const USERNAME_KEY = "socialpilot_username";

export function saveAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(TOKEN_KEY);
}

export function getUsername(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USERNAME_KEY);
}

export function saveUsername(username: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USERNAME_KEY, username.trim().replace(/^@+/, ""));
}

export function clearUsername(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USERNAME_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}
