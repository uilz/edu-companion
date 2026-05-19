"use client";

import { useState, useEffect, useCallback } from "react";
import { Dumbbell, Loader2, Sparkles, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";

interface PracticeSuggestion {
  skill_id: string;
  skill_name: string;
  bloom_level: string;
  difficulty: number;
}

interface SuggestionsResponse {
  suggestions: PracticeSuggestion[];
  confused: boolean;
  hint: string;
}

const BLOOM_LABELS: Record<string, string> = {
  remember: "记忆",
  understand: "理解",
  apply: "应用",
  analyze: "分析",
  evaluate: "评价",
};

interface PracticeSuggestionsProps {
  branchId: string | null;
}

export default function PracticeSuggestions({ branchId }: PracticeSuggestionsProps) {
  const [data, setData] = useState<SuggestionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const loadSuggestions = useCallback(async () => {
    if (!branchId) {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(
        `/api/conversations/branches/${encodeURIComponent(branchId)}/practice-suggestions`
      );
      if (res.ok) {
        setData(await res.json());
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [branchId]);

  useEffect(() => {
    loadSuggestions();
  }, [loadSuggestions]);

  if (!branchId || (!loading && (!data || data.suggestions.length === 0))) {
    return null;
  }

  return (
    <div className="border-t border-[var(--color-border)]">
      <div className="px-3 py-2 text-[11px] font-medium text-[var(--color-text-muted)] flex items-center gap-1.5">
        <Sparkles size={12} className="text-yellow-400" />
        推荐练习
      </div>

      {loading ? (
        <div className="px-3 pb-2">
          <Loader2 size={12} className="animate-spin text-[var(--color-text-muted)]" />
        </div>
      ) : data?.suggestions ? (
        <div className="px-2 pb-2 space-y-1">
          {data.suggestions.map((s) => (
            <button
              key={s.skill_id}
              onClick={() =>
                router.push(
                  `/practice?skill=${encodeURIComponent(s.skill_id)}&branch_id=${encodeURIComponent(branchId)}`
                )
              }
              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-left hover:bg-[var(--color-surface)] transition-colors group"
            >
              <Dumbbell size={12} className="text-[var(--color-accent)] flex-shrink-0" />
              <span className="flex-1 truncate text-[var(--color-text-secondary)] group-hover:text-[var(--color-text)]">
                {s.skill_name}
              </span>
              <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0">
                {BLOOM_LABELS[s.bloom_level] || s.bloom_level}
              </span>
              <ArrowRight
                size={10}
                className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 flex-shrink-0"
              />
            </button>
          ))}
        </div>
      ) : null}

      {data?.confused && (
        <div className="px-3 pb-2 text-[10px] text-orange-400">
          💡 检测到困惑，建议从基础题开始
        </div>
      )}
    </div>
  );
}
