"use client";

import { useState, useEffect } from "react";
import { BookOpen, ExternalLink, Loader2, X, Youtube } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

interface Props {
  questionId: string;
  query: string;
  visible: boolean;
  onClose: () => void;
}

interface Reference {
  title: string;
  link?: string;
  url?: string;
  description?: string;
  snippet?: string;
  source: string;
}

export default function ReferencePanel({ questionId, query, visible, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [references, setReferences] = useState<Reference[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!visible || loaded || !questionId) return;
    setLoading(true);

    // 优先通过题目 ID 搜索
    authedFetch(`/api/practice/references/for-question?question_id=${encodeURIComponent(questionId)}`)
      .then(r => r.json())
      .then(data => {
        const items = data?.results || data?.items || [];
        setReferences(Array.isArray(items) ? items : []);
        setLoaded(true);
      })
      .catch(() => {
        // fallback: 使用题干前30字直接搜索
        if (query) {
          return authedFetch(`/api/practice/references/search?q=${encodeURIComponent(query.slice(0, 30))}`)
            .then(r => r.json())
            .then(data => {
              const items = data?.results || data?.items || [];
              setReferences(Array.isArray(items) ? items : []);
            })
            .catch(() => setReferences([]));
        }
        setReferences([]);
      })
      .catch(() => {})
      .finally(() => { setLoaded(true); setLoading(false); });
  }, [visible, questionId, query, loaded]);

  if (!visible) return null;

  return (
    <div className="mt-3 rounded-xl border border-blue-500/20 bg-blue-500/5 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-blue-500/10">
        <div className="flex items-center gap-1.5">
          <BookOpen size={13} className="text-blue-500" />
          <span className="text-xs font-medium text-blue-500">参考资料</span>
        </div>
        <button onClick={onClose}
          className="p-0.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <X size={13} />
        </button>
      </div>
      <div className="px-4 py-3">
        {loading ? (
          <div className="flex items-center gap-2 py-3">
            <Loader2 size={13} className="animate-spin text-[var(--color-text-muted)]" />
            <span className="text-xs text-[var(--color-text-muted)]">正在搜索参考资料...</span>
          </div>
        ) : references.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">暂无相关参考资料</p>
        ) : (
          <div className="space-y-2">
            {references.map((ref, i) => (
              <a key={i} href={ref.link || ref.url} target="_blank" rel="noopener noreferrer"
                className="flex items-start gap-2 p-2 rounded-lg hover:bg-blue-500/5 transition-colors group">
                <div className="w-4 h-4 rounded flex items-center justify-center bg-red-500/10 flex-shrink-0 mt-0.5">
                  <Youtube size={10} className="text-red-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-[var(--color-text)] truncate group-hover:text-blue-500 transition-colors">
                    {ref.title}
                  </p>
                  {(ref.description || ref.snippet) && (
                    <p className="text-[10px] text-[var(--color-text-muted)] line-clamp-2 mt-0.5">
                      {ref.description || ref.snippet}
                    </p>
                  )}
                </div>
                <ExternalLink size={11} className="text-[var(--color-text-muted)] flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
