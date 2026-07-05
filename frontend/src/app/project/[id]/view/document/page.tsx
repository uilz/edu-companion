"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

// 手稿视图重定向 (Task #89)
export default function DocumentViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}?view=document`);
  }, [router, projectId]);
  return null;
}
