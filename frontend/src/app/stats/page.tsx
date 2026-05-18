"use client";

import { useState, useEffect } from "react";
import { BarChart3, Target, Clock, TrendingUp, Loader2, Brain, MessageCircle } from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PracticeStats {
  user_id: string;
  total_questions: number;
  total_correct: number;
  accuracy: number;
  study_minutes: number;
  weak_skills: [string, number][];
  strong_skills: [string, number][];
}

interface SkillState {
  skill_id: string;
  bkt_p_known: number;
  bkt_attempt_count: number;
  conversation_mastery_score: number;
  unified_mastery: number;
  overall_confidence: number;
  evidence_count: number;
  is_mastered: boolean;
  is_learning: boolean;
  is_novice: boolean;
}

interface KnowledgeStateData {
  skills: Record<string, SkillState>;
}

export default function StatsPage() {
  const [stats, setStats] = useState<PracticeStats | null>(null);
  const [knowledge, setKnowledge] = useState<SkillState[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/practice/stats`).then((r) => r.json()),
      fetch(`${API_BASE}/api/practice/knowledge/state`).then((r) => r.json()).catch(() => null),
    ])
      .then(([statsData, knowledgeData]) => {
        setStats(statsData.overview || statsData);
        if (knowledgeData?.skills) {
          const skills = Object.values(knowledgeData.skills) as SkillState[];
          // Sort: mastered first, then learning, then novice
          skills.sort((a, b) => b.unified_mastery - a.unified_mastery);
          setKnowledge(skills);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
        </div>
      </main>
    );
  }

  const accuracyPercent = stats?.accuracy != null ? (stats.accuracy * 100).toFixed(1) : null;
  const hours = stats?.study_minutes ? Math.floor(stats.study_minutes / 60) : 0;
  const minutes = stats?.study_minutes ? stats.study_minutes % 60 : 0;

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <h1 className="text-2xl font-bold text-[var(--color-text)] mb-6 tracking-tight">
          学习统计
        </h1>

        {/* Overview cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            {
              icon: <BarChart3 size={20} />, label: "总答题", value: `${stats?.total_questions ?? 0}`,
              sub: stats?.total_correct != null ? `正确 ${stats.total_correct}` : "",
            },
            {
              icon: <TrendingUp size={20} />, label: "正确率",
              value: `${accuracyPercent ?? "?"}%`,
              sub: accuracyPercent != null && parseInt(accuracyPercent) >= 80 ? "优秀"
                : accuracyPercent != null && parseInt(accuracyPercent) >= 60 ? "良好" : "需努力",
            },
            {
              icon: <Clock size={20} />, label: "学习时长",
              value: hours > 0 ? `${hours}h${minutes}m` : `${minutes}m`,
              sub: "累计时间",
            },
            {
              icon: <Brain size={20} />, label: "知识画像",
              value: `${knowledge.length}`,
              sub: "追踪技能",
            },
          ].map((card, i) => (
            <Card key={i}>
              <div className="text-[var(--color-accent)] mb-2">{card.icon}</div>
              <div className="text-2xl font-bold text-[var(--color-text)]">{card.value}</div>
              <div className="text-xs text-[var(--color-text-muted)]">{card.label} · {card.sub}</div>
            </Card>
          ))}
        </div>

        {/* Weak skills */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">
            🔴 薄弱知识点
          </h2>
          {stats?.weak_skills && stats.weak_skills.length > 0 ? (
            <div className="space-y-2">
              {stats.weak_skills.map(([skill, accuracy]) => (
                <div key={skill} className="flex items-center justify-between p-3 bg-[var(--color-surface)]">
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div className="h-full bg-[var(--color-error)] transition-all"
                        style={{ width: `${(accuracy * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">{(accuracy * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">暂无薄弱点数据</p>
          )}
        </div>

        {/* Strong skills */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">
            🟢 掌握好的知识点
          </h2>
          {stats?.strong_skills && stats.strong_skills.length > 0 ? (
            <div className="space-y-2">
              {stats.strong_skills.map(([skill, accuracy]) => (
                <div key={skill} className="flex items-center justify-between p-3 bg-[var(--color-surface)]">
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div className="h-full bg-[var(--color-success)] transition-all"
                        style={{ width: `${(accuracy * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">{(accuracy * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">多练几次就有了！</p>
          )}
        </div>

        {/* ── Knowledge State (SharedKnowledgeState) ── */}
        {knowledge.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4 flex items-center gap-2">
              <MessageCircle size={16} className="text-[var(--color-accent)]" />
              知识画像 · 练习+对话融合
            </h2>
            <div className="space-y-2">
              {knowledge.map((sk) => {
                const masteryPercent = (sk.unified_mastery * 100).toFixed(0);
                const barColor = sk.is_mastered ? "bg-[#10b981]"
                  : sk.is_learning ? "bg-[#3b82f6]" : "bg-[var(--color-text-muted)]";
                const status = sk.is_mastered ? "已掌握"
                  : sk.is_learning ? "学习中" : "初学";

                return (
                  <div key={sk.skill_id} className="p-3 bg-[var(--color-surface)]">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-medium text-[var(--color-text)] truncate flex-1">
                        {sk.skill_id}
                      </span>
                      <div className="flex items-center gap-2 flex-shrink-0 text-[10px]">
                        <span className={`px-1.5 py-0.5 ${
                          sk.is_mastered ? "text-[#10b981] bg-[#10b981]/10"
                          : sk.is_learning ? "text-[#3b82f6] bg-[#3b82f6]/10"
                          : "text-[var(--color-text-muted)] bg-[var(--color-border)]"
                        }`}>
                          {status}
                        </span>
                        <span className="text-[var(--color-text-muted)]">统一: {masteryPercent}%</span>
                      </div>
                    </div>
                    <div className="w-full h-1.5 bg-[var(--color-border)] mb-1.5">
                      <div
                        className={`h-full ${barColor} transition-all`}
                        style={{ width: `${masteryPercent}%` }}
                      />
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-[var(--color-text-muted)]">
                      <span title="BKT练习数据">📝 练习: {(sk.bkt_p_known * 100).toFixed(0)}% · {sk.bkt_attempt_count}次</span>
                      {sk.evidence_count > 0 && (
                        <span title="对话推断">
                          💬 对话证据: {sk.evidence_count}条
                          {sk.conversation_mastery_score > 0 && ` · +${(sk.conversation_mastery_score * 100).toFixed(0)}%`}
                        </span>
                      )}
                      <span title="综合置信度">🎯 置信度: {(sk.overall_confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {knowledge.length === 0 && (
          <div className="text-center py-8 border border-[var(--color-border)]">
            <Brain size={28} className="text-[var(--color-text-muted)] mx-auto mb-3" />
            <p className="text-sm text-[var(--color-text-muted)]">
              知识画像将在练习和对话后自动生成
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
