"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, getCurrentUser, hasRole } from "@/lib/api";

/**
 * 首页：检查登录态 → 跳到有权限的默认页
 */
export default function Home() {
  const router = useRouter();
  const [hint, setHint] = useState("加载中…");

  useEffect(() => {
    const u = getCurrentUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    // 按权限挑一个默认页
    if (hasRole(u.role, "super_admin")) router.replace("/users");
    else if (hasRole(u.role, "data_admin")) router.replace("/data");
    else if (hasRole(u.role, "analyst")) router.replace("/analytics");
    else {
      setHint(`当前角色 ${u.role} 无任何管理权限`);
    }
  }, [router]);

  return (
    <div className="page">
      <p className="muted">{hint}</p>
    </div>
  );
}
