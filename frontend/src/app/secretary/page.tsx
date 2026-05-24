"use client";

import { Bell, Check, X, Clock, AlertTriangle, TrendingUp, Settings } from "lucide-react";
import { useState, useEffect } from "react";

interface ProposalItem {
  id: string;
  emoji: string;
  title: string;
  description: string;
  action_type: string;
  priority: number;
  status: string;
  created_at?: string;
}

interface SnapshotData {
  cognitive_load: number;
  weak_count: number;
  stagnant_count: number;
  streak_days: number;
  summary: string;
}

export default function SecretaryPage() {
  const [activeTab, setActiveTab] = useState<"pending" | "history">("pending");
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [snapRes, propRes] = await Promise.all([
        fetch(`/api/secretary/snapshot?user_id=default_user`),
        fetch(`/api/secretary/proposals/pending?user_id=default_user`),
      ]);
      if (snapRes.ok) setSnapshot(await snapRes.json());
      if (propRes.ok) {
        const data = await propRes.json();
        setProposals(data);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (id: string) => {
    await fetch(`/api/secretary/proposals/${id}/accept?user_id=default_user`, {
      method: "POST",
    });
    setProposals((prev) => prev.filter((p) => p.id !== id));
  };

  const handleDismiss = async (id: string) => {
    await fetch(`/api/secretary/proposals/${id}/dismiss?user_id=default_user`, {
      method: "POST",
    });
    setProposals((prev) => prev.filter((p) => p.id !== id));
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`/api/secretary/generate-llm-proposals?user_id=default_user`, {
        method: "POST",
      });
      if (res.ok) {
        const newProps = await res.json();
        setProposals((prev) => [...newProps, ...prev]);
      }
    } finally {
      setGenerating(false);
    }
  };

  const loadHistory = async () => {
    try {
      const res = await fetch(`/api/secretary/proposals/history?user_id=default_user&days=7`);
      if (res.ok) {
        const data = await res.json();
        // Convert history format to ProposalItem[]
        return data.map((h: any) => ({
          id: h.id,
          ...h.proposal,
          status: h.status,
          created_at: h.created_at,
        }));
      }
    } catch { }
    return [];
  };

  const loadPending = async () => {
    try {
      const res = await fetch(`/api/secretary/proposals/pending?user_id=default_user`);
      if (res.ok) {
        const data = await res.json();
        setProposals(data);
      }
    } catch { }
  };

  // ── 冷启动提示 ──
  const isColdStart = snapshot && snapshot.weak_count === 0 && snapshot.summary.includes("数据不足");

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* ── 页面标题 ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">秘书系统</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">智能学习助理，随时为你服务</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {generating ? "生成中…" : "生成建议"}
          <Bell size={12} />
        </button>
        <a
          href="/secretary/settings"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-surface)] text-[var(--color-text-muted)] rounded-md border border-[var(--color-border)] hover:text-[var(--color-text)] transition-colors"
        >
          <Settings size={12} />
          设置
        </a>
      </div>

      {/* ── 状态卡片 ── */}
      {loading ? (
        <div className="p-6 text-center text-sm text-[var(--color-text-muted)]">加载中…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "薄弱点", value: snapshot?.weak_count ?? 0, icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/5" },
              { label: "停滞项", value: snapshot?.stagnant_count ?? 0, icon: Clock, color: "text-yellow-400", bg: "bg-yellow-500/5" },
              { label: "学习天数", value: snapshot?.streak_days ?? 0, icon: TrendingUp, color: "text-green-400", bg: "bg-green-500/5" },
              { label: "认知负荷", value: snapshot?.cognitive_load != null ? `${Math.round(snapshot.cognitive_load * 100)}%` : "—", icon: Bell, color: "text-blue-400", bg: "bg-blue-500/5" },
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className={`p-3 rounded-lg ${stat.bg}`}>
                  <Icon size={14} className={stat.color} />
                  <div className="text-lg font-bold text-[var(--color-text)] mt-1">{stat.value}</div>
                  <div className="text-[10px] text-[var(--color-text-muted)]">{stat.label}</div>
                </div>
              );
            })}
          </div>

          {/* ── 冷启动提示 ── */}
          {isColdStart && (
            <div className="p-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5">
              <p className="text-sm text-yellow-400">📊 学习数据不足，建议先进行一些练习，秘书系统才能提供个性化建议</p>
            </div>
          )}
        </>
      )}

      {/* ── 待处理提案列表 ── */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-2">
          <Bell size={14} />
          待处理建议
          {proposals.length > 0 && (
            <span className="text-[10px] bg-[var(--color-accent)] text-white px-1.5 py-0.5 rounded-full">
              {proposals.length}
            </span>
          )}
        </h2>

        {proposals.length === 0 ? (
          <div className="p-4 rounded-lg border border-dashed border-[var(--color-border)] text-center text-sm text-[var(--color-text-muted)]">
            暂无待处理的建议
          </div>
        ) : (
          <div className="space-y-2">
            {proposals.map((p) => (
              <div
                key={p.id}
                className={`p-3 rounded-lg border border-[var(--color-border)] border-l-4 ${
                  p.priority >= 4 ? "border-l-red-500" : p.priority >= 3 ? "border-l-yellow-400" : "border-l-blue-400"
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-base">{p.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-[var(--color-text)]">{p.title}</div>
                    <div className="text-xs text-[var(--color-text-muted)] mt-0.5">{p.description}</div>
                  </div>
                </div>
                <div className="flex gap-1.5 mt-2 ml-7">
                  <button
                    onClick={() => handleAccept(p.id)}
                    className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-green-500 text-white rounded hover:bg-green-600 transition-colors"
                  >
                    <Check size={10} />采纳
                  </button>
                  <button
                    onClick={() => handleDismiss(p.id)}
                    className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:border-[var(--color-text-muted)] transition-colors"
                  >
                    <X size={10} />忽略
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
