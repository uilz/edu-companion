"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";

// 不需要认证的页面
const PUBLIC_PATHS = ["/login", "/register"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    // 公开页面不需要守卫
    if (PUBLIC_PATHS.some((p) => pathname?.startsWith(p))) return;

    // 未认证用户重定向到登录页
    // 未登录时直接跳转登录页，不再自动创建 default_user
    // 但如果 ensure-default 失败，则需要跳转登录
    if (!user) {
      router.replace("/login");
    }
  }, [user, loading, pathname, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-[var(--color-text-secondary)] text-sm">加载中...</div>
      </div>
    );
  }

  // 未认证 + 非公开页面 → 不渲染 children，等 useEffect 跳转
  if (!user && !(PUBLIC_PATHS.some((p) => pathname?.startsWith(p)))) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-[var(--color-text-secondary)] text-sm">正在跳转登录...</div>
      </div>
    );
  }

  return <>{children}</>;
}
