"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  AuthUser,
  login as authLogin,
  loginByEmail as authLoginByEmail,
  register as authRegister,
  clearAuth as authLogout,
  fetchCurrentUser,
  ensureDefaultUser,
  getAccessToken,
} from "../lib/api/auth";
import { initFetchInterceptor } from "../lib/api/fetch-interceptor";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginByEmail: (email: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const u = await fetchCurrentUser();
      setUser(u);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    initFetchInterceptor();
    (async () => {
      const token = getAccessToken();
      if (token) {
        await refresh();
      } else {
        // 无 token 时自动创建/登录默认用户（迁移兼容）
        try {
          await ensureDefaultUser();
          await refresh();
        } catch {
          setUser(null);
        }
      }
      setLoading(false);
    })();
  }, [refresh]);

  const login = async (username: string, password: string) => {
    const result = await authLogin(username, password);
    setUser(result.user);
  };

  const loginByEmail = async (email: string, password: string) => {
    const result = await authLoginByEmail(email, password);
    setUser(result.user);
  };

  const register = async (username: string, password: string, displayName?: string) => {
    const result = await authRegister(username, password, displayName);
    setUser(result.user);
  };

  const logout = () => {
    authLogout();
    setUser(null);
    // 重新自动登录默认用户
    ensureDefaultUser().then(() => refresh()).catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, loginByEmail, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
