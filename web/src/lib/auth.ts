/**
 * Auth utilities — token storage, API calls, and fetch wrapper.
 * Uses localStorage for persistence (sufficient for this project scope).
 */

// ─── Types ───────────────────────────────────────────────────────────

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // epoch ms
}

export interface UserInfo {
  user_id: string;
  username: string;
  email: string | null;
  is_active: boolean;
  role: string;              // "user" | "admin"
  review_status: string;     // "pending" | "approved" | "rejected" | "disabled"
  last_login_at: string | null;
}

export interface AuthConfig {
  auth_enabled: boolean;
  public_mode: boolean;
}

/** Response when registration requires admin review. */
export interface RegisterPendingResponse {
  user_id: string;
  username: string;
  review_status: "pending";
  message: string;
}

// ─── Token Storage ───────────────────────────────────────────────────

const TOKEN_KEY = "ipa_auth_tokens";
const USER_KEY = "ipa_user_info";

function getStoredTokens(): AuthTokens | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthTokens;
  } catch {
    return null;
  }
}

function setStoredTokens(tokens: AuthTokens): void {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

function clearStoredTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ─── Public API ──────────────────────────────────────────────────────

/** Get the current access token if valid (not expired). */
export function getAccessToken(): string | null {
  const tokens = getStoredTokens();
  if (!tokens) return null;
  // Give 30s buffer before actual expiry
  if (Date.now() >= tokens.expiresAt - 30_000) return null;
  return tokens.accessToken;
}

/** Check if the user is currently logged in. */
export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}

/** Get cached user info (may be stale). */
export function getCachedUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as UserInfo;
  } catch {
    return null;
  }
}

/** Clear all auth state. */
export function clearAuth(): void {
  clearStoredTokens();
}

/** Store tokens after login/register. */
export function storeAuthTokens(
  accessToken: string,
  refreshToken: string,
  expiresIn: number
): void {
  setStoredTokens({
    accessToken,
    refreshToken,
    expiresAt: Date.now() + expiresIn * 1000,
  });
}

/** Cache user info. */
export function storeUserInfo(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

// ─── API Calls ───────────────────────────────────────────────────────

async function apiCall<T>(
  path: string,
  body: Record<string, unknown>,
  method = "POST"
): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errBody = await res.json().catch(() => null);
    throw new Error(
      (errBody as any)?.detail || `Auth API error: ${res.status}`
    );
  }

  return res.json();
}

/** Login and store tokens. Returns user info. */
export async function login(
  username: string,
  password: string
): Promise<UserInfo> {
  const data = await apiCall<{
    access_token: string;
    refresh_token: string;
    expires_in: number;
  }>("/api/v1/auth/login", { username, password });

  storeAuthTokens(data.access_token, data.refresh_token, data.expires_in);

  // Fetch user info
  const user = await fetchUserInfo(data.access_token);
  storeUserInfo(user);
  return user;
}

/** Register a new account. Returns pending response if admin review is required. */
export async function register(
  username: string,
  password: string,
  email?: string
): Promise<UserInfo | RegisterPendingResponse> {
  const body: Record<string, string> = { username, password };
  if (email) body.email = email;

  const data = await apiCall<{
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
    username: string;
    user_id: string;
    review_status?: string;
    message?: string;
  }>("/api/v1/auth/register", body);

  // Pending path — no tokens, await admin review
  if (data.review_status === "pending") {
    return {
      user_id: data.user_id,
      username: data.username,
      review_status: "pending",
      message: data.message!,
    };
  }

  // Approved path — store tokens and return user info
  storeAuthTokens(data.access_token!, data.refresh_token!, data.expires_in!);
  const user: UserInfo = {
    user_id: data.user_id,
    username: data.username,
    email: email || null,
    is_active: true,
    role: "user",
    review_status: "approved",
    last_login_at: null,
  };
  storeUserInfo(user);
  return user;
}

/** Fetch current user info from backend. */
export async function fetchUserInfo(accessToken?: string): Promise<UserInfo> {
  const token = accessToken || getAccessToken();
  if (!token) throw new Error("No access token");

  const res = await fetch("/api/v1/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch user info: ${res.status}`);
  }

  return res.json();
}

/** Refresh the access token using the stored refresh token. */
export async function refreshAccessToken(): Promise<string | null> {
  const tokens = getStoredTokens();
  if (!tokens?.refreshToken) return null;

  try {
    const data = await apiCall<{
      access_token: string;
      expires_in: number;
    }>("/api/v1/auth/refresh", {
      refresh_token: tokens.refreshToken,
    });

    storeAuthTokens(data.access_token, tokens.refreshToken, data.expires_in);
    return data.access_token;
  } catch {
    clearAuth();
    return null;
  }
}

/** Check backend auth configuration. */
export async function fetchAuthConfig(): Promise<AuthConfig> {
  try {
    const res = await fetch("/api/v1/auth/config");
    if (!res.ok) return { auth_enabled: false, public_mode: true };
    return res.json();
  } catch {
    return { auth_enabled: false, public_mode: true };
  }
}

// ─── Admin API ───────────────────────────────────────────────────────

export interface AdminUserListItem {
  user_id: string;
  username: string;
  email: string | null;
  created_at: string;
  role: string;
  review_status: string;
}

export async function listPendingUsers(accessToken?: string): Promise<AdminUserListItem[]> {
  const token = accessToken || getAccessToken();
  if (!token) throw new Error("No access token");
  const res = await fetch("/api/v1/admin/users/pending", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to list pending users: ${res.status}`);
  return res.json();
}

export async function reviewUser(
  userId: string,
  action: "approved" | "rejected",
  accessToken?: string
): Promise<void> {
  const token = accessToken || getAccessToken();
  if (!token) throw new Error("No access token");
  const res = await fetch(`/api/v1/admin/users/${userId}/review`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`Failed to review user: ${res.status}`);
}

// ─── Auth-aware Fetch Wrapper ────────────────────────────────────────

/**
 * Fetch wrapper that automatically attaches the Bearer token.
 * If the request returns 401, attempts a token refresh and retries once.
 */
export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const token = getAccessToken();

  const headers = new Headers(init.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res = await fetch(input, { ...init, headers });

  // 401 → try refresh and retry once
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetch(input, { ...init, headers });
    }
  }

  return res;
}
