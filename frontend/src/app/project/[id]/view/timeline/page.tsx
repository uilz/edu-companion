"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

export default function TimelineViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}?view=timeline`);
  }, [router, projectId]);
  return null;
}
