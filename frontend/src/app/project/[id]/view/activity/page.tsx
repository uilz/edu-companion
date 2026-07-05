"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

// 活动流视图重定向 (Task #89: Timeline 重写为 Activity)
export default function ActivityViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}?view=activity`);
  }, [router, projectId]);
  return null;
}
