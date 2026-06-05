"use client";

import { useState, useEffect } from "react";
import { Lightbulb, X, Check, Loader2, MessageSquare } from "lucide-react";

interface Proposal {
  id: string;
  emoji: string;
  title: string;
  description: string;
  action_type: string;
  payload: Record<string, any>;
  priority: number;
  created_at: number;
}

export default function SecretaryProposals({ sessionId }: { sessionId?: string }) {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch("/api/v7/practice/secretary/proposals?limit=3")
      .then((r) => r.json())
      .then((data) => {
        setProposals(Array.isArray(data?.proposals) ? data.proposals : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [sessionId]);

  const handleDismiss = async (id: string) => {
    try {
      await fetch(`/api/v7/practice/secretary/proposals/${id}/dismiss`, { method: "POST" });
      setDismissed((prev) => new Set(prev).add(id));
    } catch {}
  };

  const handleAccept = async (id: string) => {
    try {
      await fetch(`/api/v7/practice/secretary/proposals/${id}/accept`, { method: "POST" });
      setDismissed((prev) => new Set(prev).add(id));
    } catch {}
  };

  const visible = proposals.filter((p) => !dismissed.has(p.id));
  if (loading || visible.length === 0) return null;

  return (
    <div className="mb-4 space-y-2">
      <p className="text-[11px] text-[var(--color-text-muted)] font-medium flex items-center gap-1.5 mb-2">
        <Lightbulb size={12} className="text-amber-500" />
        学习建议
      </p>
      {visible.map((p) => (
        <div key={p.id}
          className={`p-3 rounded-lg border transition-all ${
            p.priority <= 2
              ? "border-amber-500/30 bg-amber-500/5"
              : "border-[var(--color-accent)]/20 bg-[var(--color-accent)]/[0.02]"
          }`}>
          <div className="flex items-start gap-2">
            <span className="text-sm flex-shrink-0">{p.emoji}</span>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-medium text-[var(--color-text)]">{p.title}</p>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5 leading-relaxed">{p.description}</p>
              {/* Action buttons for reflection prompts */}
              <div className="flex items-center gap-2 mt-2">
                <button onClick={() => handleAccept(p.id)}
                  className="flex items-center gap-1 px-2 py-1 rounded text-[9px] bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-colors">
                  <Check size={10} />知道了
                </button>
                <button onClick={() => handleDismiss(p.id)}
                  className="flex items-center gap-1 px-2 py-1 rounded text-[9px] text-[var(--color-text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors">
                  <X size={10} />忽略
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
