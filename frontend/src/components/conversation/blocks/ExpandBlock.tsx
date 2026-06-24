"use client";

import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Lightbulb, BookOpen, AlertTriangle, Sparkles } from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";

interface ExpandResult {
  deeper_explanation?: string;
  prerequisites?: string[];
  advanced_topics?: string[];
  real_world_examples?: string[];
  common_misconceptions?: string[];
  fun_fact?: string;
}

interface Props {
  skillName: string;
  explanation?: string;
}

export default function ExpandBlock({ skillName, explanation }: Props) {
  const [data, setData] = useState<ExpandResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!expanded || data) return;
    setLoading(true);
    authedFetch(`/api/expand/knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_name: skillName, explanation: explanation || "" }),
    })
      .then((r) => r.json())
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [expanded, data, skillName, explanation]);

  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium
                   bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)]
                   transition-colors"
      >
        <Sparkles size={14} className="text-[var(--color-warning)]" />
        <span>知识拓展：{skillName}</span>
        <span className="ml-auto">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>

      {expanded && (
        <div className="p-3 space-y-3 text-sm">
          {loading && (
            <div className="flex items-center gap-2 text-[var(--color-text-muted)]">
              <div className="animate-spin w-4 h-4 border-2 border-current border-t-transparent rounded-full" />
              正在生成知识拓展...
            </div>
          )}
          {error && <div className="text-[var(--color-error)]">❌ {error}</div>}
          {data && (
            <>
              {data.deeper_explanation && (
                <Section icon={<Lightbulb size={14} />} title="深入解释" color="text-[var(--color-info)]">
                  {data.deeper_explanation}
                </Section>
              )}
              {data.prerequisites && data.prerequisites.length > 0 && (
                <Section icon={<BookOpen size={14} />} title="前置知识" color="text-[var(--color-success)]">
                  <ul className="list-disc list-inside space-y-1">
                    {data.prerequisites.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </Section>
              )}
              {data.advanced_topics && data.advanced_topics.length > 0 && (
                <Section icon={<ChevronUp size={14} />} title="进阶方向" color="text-[var(--color-accent)]">
                  <ul className="list-disc list-inside space-y-1">
                    {data.advanced_topics.map((t, i) => <li key={i}>{t}</li>)}
                  </ul>
                </Section>
              )}
              {data.real_world_examples && data.real_world_examples.length > 0 && (
                <Section icon={<Sparkles size={14} />} title="实际应用" color="text-[var(--color-warning)]">
                  <ul className="list-disc list-inside space-y-1">
                    {data.real_world_examples.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </Section>
              )}
              {data.common_misconceptions && data.common_misconceptions.length > 0 && (
                <Section icon={<AlertTriangle size={14} />} title="常见误区" color="text-[var(--color-error)]">
                  <ul className="list-disc list-inside space-y-1">
                    {data.common_misconceptions.map((m, i) => <li key={i}>{m}</li>)}
                  </ul>
                </Section>
              )}
              {data.fun_fact && (
                <div className="bg-[var(--color-warning)]/5 rounded p-2 text-xs">
                  💡 {data.fun_fact}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ icon, title, color, children }: {
  icon: React.ReactNode; title: string; color: string; children: React.ReactNode;
}) {
  return (
    <div>
      <div className={`flex items-center gap-1.5 font-medium ${color} mb-1`}>
        {icon} {title}
      </div>
      <div className="pl-5 text-[var(--color-text-secondary)]">{children}</div>
    </div>
  );
}
