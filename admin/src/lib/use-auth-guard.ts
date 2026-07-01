"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "./auth-store";

/**
 * 页面级鉴权守卫 — 未登录自动跳转 /login
 */
export function useAuthGuard() {
  const router = useRouter();
  const { user, sync } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    sync();
  }, [sync]);

  useEffect(() => {
    if (!mounted) return;
    if (!user) {
      router.replace("/login");
    }
  }, [mounted, user, router]);

  return { ready: mounted && !!user, user };
}
