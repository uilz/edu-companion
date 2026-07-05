"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

// 大纲视图 — 重定向到项目详情页（默认就是 outline）
export default function OutlineViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}`);
  }, [router, projectId]);
  return null;
}
