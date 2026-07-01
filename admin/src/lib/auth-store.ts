/**
 * Admin 认证状态管理 — Zustand store
 */
import { create } from "zustand";
import { getCurrentUser, clearSession, hasRole } from "./api";
import type { AdminUser, AdminRole } from "./types";

interface AuthState {
  user: AdminUser | null;
  /** 从 localStorage 同步用户状态 */
  sync: () => void;
  /** 登出 */
  logout: () => void;
  /** 检查当前用户是否满足最低角色 */
  can: (min: AdminRole) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,

  sync: () => {
    set({ user: getCurrentUser() });
  },

  logout: () => {
    clearSession();
    set({ user: null });
  },

  can: (min: AdminRole) => {
    return hasRole(get().user?.role, min);
  },
}));
