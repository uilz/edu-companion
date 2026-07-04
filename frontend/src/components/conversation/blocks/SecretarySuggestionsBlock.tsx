"use client";

import { useState } from "react";
import { Bell, Check, Clock, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { authedFetch } from "@/lib/api/api";

interface SecretaryProposal {
  id: string;
  emoji: string;
  title: string;
  description: string;
  action_type: string;
  priority: number;
}

interface SecretarySuggestionsBlockProps {
  content: Record<string, unknown>;
}

export default function SecretarySuggestionsBlock({
  content,
}: SecretarySuggestionsBlockProps) {
  const proposals = (content.proposals as SecretaryProposal[]) || [];
  const reportSummary = content.report_summary as
    | { weak_count?: number; cognitive_load?: number; summary?: string }
    | undefined;

  if (proposals.length === 0) return null;

  return (
    <div className="border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 mt-2 overflow-hidden active:scale-[0.97] transition-transform">
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--color-accent)]/10 flex items-center gap-2">
        <Bell size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          秘书建议
        </span>
        {reportSummary && (
          <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
            {reportSummary.weak_count != null &&
              `${reportSummary.weak_count}个薄弱点`}
            {reportSummary.cognitive_load != null &&
              reportSummary.cognitive_load > 0.6 &&
              " · 负荷偏高"}
          </span>
        )}
      </div>

      {/* Proposals */}
      <div className="divide-y divide-[var(--color-border)]">
        {proposals.map((p, i) => (
          <ProposalCard key={i} proposal={p} />
        ))}
      </div>

      {/* Footer hint */}
      <div className="px-3 py-1.5 text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface)]">
        你可以选择一项执行，或继续当前学习
      </div>
    </div>
  );
}

function ProposalCard({ proposal }: { proposal: SecretaryProposal }) {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [loading, setLoading] = useState(false);

  if (dismissed || accepted) return null;

  const handleAccept = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await authedFetch(`/api/secretary/proposals/${proposal.id}/accept?user_id=${user.id}`,
        { method: "POST" }
      );
      if (res.ok) {
        setAccepted(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await authedFetch(`/api/secretary/proposals/${proposal.id}/dismiss?user_id=${user.id}`,
        { method: "POST" }
      );
      if (res.ok) {
        setDismissed(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const priorityColors: Record<number, string> = {
    5: "border-l-red-500",
    4: "border-l-orange-400",
    3: "border-l-yellow-400",
    2: "border-l-blue-400",
    1: "border-l-gray-400",
  };

  return (
    <div
      className={`px-3 py-2.5 border-l-2 hover:bg-[var(--color-accent)]/5 transition-colors ${
        priorityColors[proposal.priority] || "border-l-gray-400"
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-sm flex-shrink-0">{proposal.emoji}</span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-[var(--color-text)]">
            {proposal.title}
          </div>
          <div className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
            {proposal.description}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-1.5 mt-2 ml-6">
        <button
          onClick={handleAccept}
          disabled={loading}
          className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-[var(--color-accent)] text-white rounded hover:opacity-90 active:scale-[0.97] transition-opacity disabled:opacity-50"
        >
          <Check size={10} />
          执行
        </button>
        <button
          onClick={handleDismiss}
          disabled={loading}
          className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:border-[var(--color-text-muted)] active:scale-[0.97] transition-all disabled:opacity-50"
        >
          <X size={10} />
          忽略
        </button>
      </div>
    </div>
  );
}
