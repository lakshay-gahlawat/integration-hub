import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiRequest, clearStoredTokens, setStoredTokens } from "../api/client";
import type { AuthResponse, User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const hasToken = !!localStorage.getItem("ih_access_token");
    if (!hasToken) {
      setLoading(false);
      return;
    }
    apiRequest<User>("/auth/me")
      .then(setUser)
      .catch(() => clearStoredTokens())
      .finally(() => setLoading(false));
  }, []);

  const applyAuthResponse = (data: AuthResponse) => {
    setStoredTokens(data.access_token, data.refresh_token);
    setUser(data.user);
  };

  const login = async (email: string, password: string) => {
    const data = await apiRequest<AuthResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      skipAuth: true,
    });
    applyAuthResponse(data);
  };

  const register = async (email: string, password: string, fullName: string) => {
    const data = await apiRequest<AuthResponse>("/auth/register", {
      method: "POST",
      body: { email, password, full_name: fullName },
      skipAuth: true,
    });
    applyAuthResponse(data);
  };

  const logout = () => {
    // Best-effort revocation -- clearing local storage happens regardless
    // of whether this call succeeds, so a logout is never blocked on
    // network conditions. See /auth/logout for what it actually revokes.
    const refreshToken = localStorage.getItem("ih_refresh_token");
    if (refreshToken) {
      apiRequest("/auth/logout", {
        method: "POST",
        body: { refresh_token: refreshToken },
        skipAuth: true,
      }).catch(() => {
        /* token may already be invalid/expired -- nothing to do */
      });
    }
    clearStoredTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
