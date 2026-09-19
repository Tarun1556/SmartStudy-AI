import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { setToken, clearToken, setDemoMode, getDemoMode } from "@/lib/api/client";
import type { User } from "@/types";

interface AuthContextValue {
  user: User | null;
  isDemo: boolean;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  enterDemo: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [isDemo, setIsDemoState] = React.useState<boolean>(getDemoMode());

  const { data: user, isLoading, refetch } = useQuery<User | null>({
    queryKey: ["auth-me"],
    queryFn: async () => {
      try {
        const res = await api.get("/api/auth/me");
        return res.data as User;
      } catch (e: any) {
        if (e?.response?.status === 401) return null;
        throw e;
      }
    },
    retry: false,
    // No initialData: providing one (e.g. `null`) makes TanStack Query report
    // isLoading=false on the very first render, before the real /api/auth/me
    // check has even fired. RequireAuth relies on isLoading to wait for that
    // check — with initialData set, it would see isAuthenticated=false instantly
    // and redirect to /login on every hard refresh, even with a valid token.
  });

  const loginMut = useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const res = await api.post("/api/auth/login", { email, password });
      return res.data as { access_token: string };
    },
  });

  const registerMut = useMutation({
    mutationFn: async ({ email, password, full_name }: any) => {
      const res = await api.post("/api/auth/register", { email, password, full_name });
      return res.data as { access_token: string };
    },
  });

  const demoMut = useMutation({
    mutationFn: async () => {
      const res = await api.get("/api/demo/token");
      return res.data as { access_token: string };
    },
  });

  const login = async (email: string, password: string) => {
    const data = await loginMut.mutateAsync({ email, password });
    setToken(data.access_token);
    setDemoMode(false);
    setIsDemoState(false);
    queryClient.clear();
    await refetch();
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const data = await registerMut.mutateAsync({ email, password, full_name: fullName });
    setToken(data.access_token);
    setDemoMode(false);
    setIsDemoState(false);
    queryClient.clear();
    await refetch();
  };

  const logout = () => {
    clearToken();
    setDemoMode(false);
    setIsDemoState(false);
    queryClient.clear();
    queryClient.setQueryData(["auth-me"], null as any);
  };

  const enterDemo = async () => {
    const data = await demoMut.mutateAsync();
    setToken(data.access_token);
    setDemoMode(true);
    setIsDemoState(true);
    queryClient.clear();
    await refetch();
  };

  const value: AuthContextValue = {
    user: user || null,
    isDemo,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    enterDemo,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
