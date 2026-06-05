"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GitGraph, X } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Recommendation {
  type: string;
  message: string;
  action: string;
  partition_id: string;
  nodes?: { id: string; label: string }[];
}

/**
 * KnowledgeTreeRecommendBanner
 * 在对话系统中轮询推荐信息，当有新建节点/编辑意图时推荐用户去知识树系统
 */
export default function KnowledgeTreeRecommendBanner({
  partitionId,
}: {
  partitionId: string | null;
}) {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!partitionId) return;
    const interval = setInterval(() => {
      fetch(`${API_BASE}/api/knowledge/graph/recommendation?source=conversation`)
        .then((r) => r.json())
        .then((d) => {
          const filtered = (d.recommendations || []).filter(
            (r: Recommendation) => !dismissed.has(r.partition_id + r.type)
          );
          setRecs(filtered);
        })
        .catch(() => {});
    }, 30000); // 每30秒检查一次

    // 初始加载
    fetch(`${API_BASE}/api/knowledge/graph/recommendation?source=conversation`)
      .then((r) => r.json())
      .then((d) => setRecs(d.recommendations || []))
      .catch(() => {});

    return () => clearInterval(interval);
  }, [partitionId, dismissed]);

  if (recs.length === 0) return null;

  return (
    <div className="space-y-1.5 px-4 pt-2">
      {recs.map((rec, i) => (
        <div
          key={i}
          className="flex items-center gap-2 px-3 py-2 rounded-md bg-violet-50 dark:bg-violet-950/20 border border-violet-200 dark:border-violet-800/30 text-xs text-violet-700 dark:text-violet-400"
        >
          <GitGraph size={14} className="flex-shrink-0" />
          <span className="flex-1">{rec.message}</span>
          <Link
            href="/resources?tab=knowledge-tree"
            className="px-2 py-0.5 rounded bg-violet-200 dark:bg-violet-800/40 hover:bg-violet-300 dark:hover:bg-violet-700/40 transition-colors font-medium flex-shrink-0"
          >
            去知识树
          </Link>
          <button
            onClick={() => setDismissed((prev) => new Set(Array.from(prev).concat([rec.partition_id + rec.type])))}
            className="p-0.5 rounded hover:bg-violet-200/50 dark:hover:bg-violet-800/20 transition-colors flex-shrink-0"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}