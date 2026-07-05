"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

// 大纲视图重定向 (Task #89) — 统一使用 ?view= 形式
export default function OutlineViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}?view=outline`);
  }, [router, projectId]);
  return null;
}
