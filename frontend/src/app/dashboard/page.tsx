// ============================================================
// /dashboard 路径页面 (任务 #120)
//
// 设计决策：统一首页入口
//   - /dashboard 重定向到 /
//   - 避免与秘书仪表盘首页重复
// ============================================================

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return null;
}
