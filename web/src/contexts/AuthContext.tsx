/**
 * Auth context — provides login state, user info, and auth actions to the app.
 */
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  getAccessToken,
  isAuthenticated as _isAuthenticated,
  getCachedUser,
  clearAuth,
  storeUserInfo,
  login as apiLogin,
  register as apiRegister,
  fetchUserInfo,
  refreshAccessToken,
  fetchAuthConfig,
  type UserInfo,
  type AuthConfig,
  type RegisterPendingResponse,
} from "@/lib/auth";

// ─── Types ───────────────────────────────────────────────────────────

export type RegisterResult =
  | { type: "pending"; user_id: string; username: string; message: string }
  | { type: "success"; user: UserInfo };

interface AuthState {
  user: UserInfo | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  authConfig: AuthConfig | null;
  reviewStatus: string | null;
}

interface AuthActions {
  login: (username: string, password: string) => Promise<UserInfo>;
  register: (
    username: string,
    password: string,
    email?: string
  ) => Promise<RegisterResult>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

type AuthContextValue = AuthState & AuthActions;

// ─── Context ─────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

// ─── Provider ────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [reviewStatus, setReviewStatus] = useState<string | null>(null);

  // Bootstrap: check stored token and load user info
  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      // Check auth config first
      try {
        const config = await fetchAuthConfig();
        if (cancelled) return;
        setAuthConfig(config);

        // If auth is not enabled, skip auth entirely
        if (!config.auth_enabled) {
          setIsLoading(false);
          return;
        }
      } catch {
        // If we can't reach the config endpoint, assume public mode
        if (cancelled) return;
        setAuthConfig({ auth_enabled: false, public_mode: true });
        setIsLoading(false);
        return;
      }

      // Try to load user from stored token
      const token = getAccessToken();
      if (token) {
        try {
          const info = await fetchUserInfo(token);
          if (!cancelled) {
            setUser(info);
            storeUserInfo(info);
            setReviewStatus(info.review_status);
          }
        } catch {
          // Token expired — try refresh
          const newToken = await refreshAccessToken();
          if (newToken && !cancelled) {
            try {
              const info = await fetchUserInfo(newToken);
              setUser(info);
              storeUserInfo(info);
              setReviewStatus(info.review_status);
            } catch {
              // Refresh failed — clear auth
              clearAuth();
              setUser(null);
              setReviewStatus(null);
            }
          } else if (!cancelled) {
            clearAuth();
            setUser(null);
            setReviewStatus(null);
          }
        }
      } else {
        // No stored token — use cached user if available (stale but better than nothing)
        setUser(getCachedUser());
      }

      if (!cancelled) setIsLoading(false);
    };

    init();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      const info = await apiLogin(username, password);
      setUser(info);
      setReviewStatus(info.review_status);
      return info;
    },
    []
  );

  const register = useCallback(
    async (username: string, password: string, email?: string) => {
      const result = await apiRegister(username, password, email);
      if ("review_status" in result && result.review_status === "pending") {
        const pending = result as RegisterPendingResponse;
        return {
          type: "pending" as const,
          user_id: pending.user_id,
          username: pending.username,
          message: pending.message,
        };
      }
      const user = result as UserInfo;
      setUser(user);
      setReviewStatus(user.review_status);
      return { type: "success" as const, user };
    },
    []
  );

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    setReviewStatus(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const token = getAccessToken();
    if (token) {
      try {
        const info = await fetchUserInfo(token);
        setUser(info);
        storeUserInfo(info);
        setReviewStatus(info.review_status);
      } catch {
        // silently ignore — user will see cached data
      }
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: _isAuthenticated(),
      authConfig,
      reviewStatus,
      login,
      register,
      logout,
      refreshUser,
    }),
    [user, isLoading, authConfig, reviewStatus, login, register, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
