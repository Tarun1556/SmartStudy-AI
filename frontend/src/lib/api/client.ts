import axios, { AxiosInstance } from "axios";

const BASE_URL =
  (import.meta as any).env?.VITE_API_BASE_URL ||
  "http://localhost:8000";

const TOKEN_KEY = "studyai_token";
const DEMO_MODE_KEY = "studyai_demo";

export const getToken = (): string | null => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setToken = (token: string) => {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {}
};

export const clearToken = () => {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(DEMO_MODE_KEY);
  } catch {}
};

export const setDemoMode = (v: boolean) => {
  try {
    localStorage.setItem(DEMO_MODE_KEY, v ? "1" : "0");
  } catch {}
};

export const getDemoMode = (): boolean => {
  try {
    return localStorage.getItem(DEMO_MODE_KEY) === "1";
  } catch {
    return false;
  }
};

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: false,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const PUBLIC_PATHS = ["/", "/login", "/register"];

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const isAuthCheck = err?.config?.url?.includes("/api/auth/me");
    if (err?.response?.status === 401 && !isAuthCheck) {
      // A 401 from /api/auth/me is an expected, handled outcome (it just means
      // "not logged in yet") on every app mount, including on public pages like
      // /register — it must not trigger a forced redirect away from them. Only
      // a 401 from an actual authenticated action (an expired/invalid token
      // rejected mid-session) should force the user back to /login.
      clearToken();
      if (!PUBLIC_PATHS.includes(window.location.pathname)) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export default api;
