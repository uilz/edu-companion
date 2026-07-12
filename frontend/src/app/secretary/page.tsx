// ============================================================
// /secretary 路径页面 (任务 #120)
//
// 设计决策：统一首页入口
//   - /secretary 重定向到 /
//   - 保留文件以兼容旧书签/导航
// ============================================================

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SecretaryPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return null;
}
