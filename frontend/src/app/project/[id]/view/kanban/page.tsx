"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

// 看板视图重定向 (Task #89)
export default function KanbanViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}?view=kanban`);
  }, [router, projectId]);
  return null;
}
