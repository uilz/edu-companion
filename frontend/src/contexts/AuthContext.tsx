"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  AuthUser,
  login as authLogin,
  loginByEmail as authLoginByEmail,
  register as authRegister,
  clearAuth as authLogout,
  fetchCurrentUser,
  getAccessToken,
} from "../lib/api/auth";
import { initFetchInterceptor } from "../lib/api/fetch-interceptor";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginByEmail: (email: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string, email?: string) => Promise<void>;
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
        // 有 token 才尝试拉当前用户；拿不到就视为未登录
        await refresh();
      }
      // 无论有无 token，最终都进入"已加载"状态
      // 没有 token → user=null → AuthGuard 跳 /login
      // 有 token 但失效 → refresh 会 setUser(null) → 同样跳 /login
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

  const register = async (username: string, password: string, displayName?: string, email?: string) => {
    const result = await authRegister(username, password, displayName, email);
    setUser(result.user);
  };

  const logout = () => {
    // 清掉 token 和 user，不再自动建任何账号
    authLogout();
    setUser(null);
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
