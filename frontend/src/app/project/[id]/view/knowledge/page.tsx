"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect } from "react";

export default function KnowledgeViewPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params?.id as string;
  useEffect(() => {
    router.replace(`/project/${projectId}?view=knowledge`);
  }, [router, projectId]);
  return null;
}
