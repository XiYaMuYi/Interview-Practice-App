/**
 * Axios instance with auth token interceptor.
 * All API calls should use this instead of raw axios.
 */
import axios from "axios";
import { getAccessToken, refreshAccessToken, clearAuth } from "@/lib/auth";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || ""; // Use env var on Vercel, empty string for local rewrites

const api = axios.create({
  baseURL: apiBaseUrl,
});

// ── Request interceptor: attach Bearer token ──
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response interceptor: retry once on 401 after token refresh ──
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retried) {
      originalRequest._retried = true;
      const newToken = await refreshAccessToken();
      if (newToken && originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      }
      // Refresh failed → clear auth
      clearAuth();
      // Optionally redirect to login
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Re-export axios.isAxiosError for error handling in components
export { isAxiosError } from "axios";

export default api;
