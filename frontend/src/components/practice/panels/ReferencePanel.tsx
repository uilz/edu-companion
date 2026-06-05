"use client";

import { useState, useEffect } from "react";
import { Youtube, Search, Loader2, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { searchReferences, type ReferenceResult } from "@/lib/api/practice-api";

interface Props {
  query?: string;
  nodeId?: string;
  questionId?: string;
  /** 紧凑模式，用于练习面板内嵌 */
  compact?: boolean;
}

export default function ReferencePanel({ query, nodeId, questionId, compact }: Props) {
  const [results, setResults] = useState<ReferenceResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  // 自动搜索
  useEffect(() => {
    const searchQuery = query || (nodeId ? "" : "");
    if (!searchQuery && !nodeId && !questionId) return;

    setLoading(true);
    setError("");

    const fetchRefs = async () => {
      try {
        let data;
        if (query) {
          data = await searchReferences(query);
        } else {
          return; // 需要通过 query 搜索
        }
        setResults(data.results || []);
        if (data.error) setError(data.error);
      } catch {
        setError("搜索失败");
      }
      setLoading(false);
    };

    fetchRefs();
  }, [query, nodeId, questionId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2">
        <Loader2 size={12} className="animate-spin text-[var(--color-text-muted)]" />
        <span className="text-[10px] text-[var(--color-text-muted)]">搜索讲解视频…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-2">
        <p className="text-[10px] text-[var(--color-error)]">{error}</p>
      </div>
    );
  }

  if (results.length === 0) return null;

  const visible = compact && !expanded ? results.slice(0, 2) : results;

  return (
    <div className={compact ? "" : "mt-3"}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors mb-1.5"
      >
        <Youtube size={10} className="text-red-400" />
        B站讲解视频 ({results.length})
        {compact && (expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />)}
      </button>
      <div className="space-y-1.5">
        {visible.map((v) => (
          <a
            key={v.bvid}
            href={v.link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex gap-2 p-1.5 rounded-lg hover:bg-[var(--color-surface)] transition-colors group"
          >
            {v.cover && (
              <img src={v.cover} alt="" className="w-14 h-9 rounded object-cover flex-shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-[var(--color-text)] line-clamp-1 group-hover:text-[var(--color-accent)] transition-colors">
                {v.title}
              </p>
              <div className="flex items-center gap-2 text-[9px] text-[var(--color-text-muted)] mt-0.5">
                <span>{v.author}</span>
                <span>{v.played}播放</span>
                {v.duration && <span>{v.duration}</span>}
              </div>
            </div>
            <ExternalLink size={10} className="flex-shrink-0 mt-0.5 text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>
        ))}
      </div>
    </div>
  );
}
