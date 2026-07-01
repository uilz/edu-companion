"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";

export default function Home() {
  const router = useRouter();
  const { user, sync, can } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    sync();
    setMounted(true);
  }, [sync]);

  useEffect(() => {
    if (!mounted) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (can("super_admin")) router.replace("/users");
    else if (can("data_admin")) router.replace("/data");
    else if (can("analyst")) router.replace("/analytics");
  }, [mounted, user, router, can]);

  if (!user) {
    return (
      <div className="flex items-center justify-center py-20 text-ink-muted text-caption">
        加载中…
      </div>
    );
  }

  return (
    <div className="py-20 text-center text-ink-muted text-body">
      当前角色 {user.role} 无任何管理权限
    </div>
  );
}
