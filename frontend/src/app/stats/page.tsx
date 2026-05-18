"use client";

import { useState, useEffect } from "react";
import { BarChart3, Target, Clock, TrendingUp, Loader2 } from "lucide-react";
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

export default function StatsPage() {
  const [stats, setStats] = useState<PracticeStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/practice/stats`)
      .then((r) => r.json())
      .then((data) => {
        // API wraps stats in overview field
        setStats(data.overview || data);
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

  if (!stats || stats.total_questions == null || stats.total_questions === 0) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <BarChart3 size={40} className="mx-auto mb-4 text-[var(--color-text-muted)]" />
          <h1 className="text-3xl font-bold text-[var(--color-text)] mb-2">学习统计</h1>
          <p className="text-[var(--color-text-muted)]">还没有练习数据，去练习页开始做题吧！</p>
        </div>
      </main>
    );
  }

  const accuracyPercent = ((stats.accuracy ?? 0) * 100).toFixed(0);
  const hours = Math.floor((stats.study_minutes ?? 0) / 60);
  const minutes = Math.round((stats.study_minutes ?? 0) % 60);
  const totalQuestions = stats.total_questions ?? 0;
  const totalCorrect = stats.total_correct ?? 0;

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Header */}
        <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text)] mb-12">
          <BarChart3 size={28} className="inline mr-3 text-[var(--color-accent)]" />
          学习统计
        </h1>

        {/* Overview cards */}
        <div className="grid grid-cols-3 gap-4 mb-12">
          {[
            {
              icon: <Target size={20} />,
              label: "总题数",
              value: totalQuestions.toString(),
              sub: `正确 ${totalCorrect}`,
            },
            {
              icon: <TrendingUp size={20} />,
              label: "正确率",
              value: `${accuracyPercent}%`,
              sub:
                accuracyPercent &&
                parseInt(accuracyPercent) >= 80
                  ? "优秀"
                  : parseInt(accuracyPercent) >= 60
                  ? "良好"
                  : "需努力",
            },
            {
              icon: <Clock size={20} />,
              label: "学习时长",
              value: hours > 0 ? `${hours}h${minutes}m` : `${minutes}m`,
              sub: "累计时间",
            },
          ].map((card, i) => (
            <Card key={i}>
              <div className="text-[var(--color-accent)] mb-2">{card.icon}</div>
              <div className="text-2xl font-bold text-[var(--color-text)]">
                {card.value}
              </div>
              <div className="text-xs text-[var(--color-text-muted)]">
                {card.label} · {card.sub}
              </div>
            </Card>
          ))}
        </div>

        {/* Weak skills */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">
            🔴 薄弱知识点
          </h2>
          {stats.weak_skills && stats.weak_skills.length > 0 ? (
            <div className="space-y-2">
              {stats.weak_skills.map(([skill, accuracy]) => (
                <div
                  key={skill}
                  className="flex items-center justify-between p-3 bg-[var(--color-surface)]"
                >
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div
                        className="h-full bg-[var(--color-error)] transition-all"
                        style={{ width: `${(accuracy * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {(accuracy * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">暂无薄弱点数据</p>
          )}
        </div>

        {/* Strong skills */}
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">
            🟢 掌握好的知识点
          </h2>
          {stats.strong_skills && stats.strong_skills.length > 0 ? (
            <div className="space-y-2">
              {stats.strong_skills.map(([skill, accuracy]) => (
                <div
                  key={skill}
                  className="flex items-center justify-between p-3 bg-[var(--color-surface)]"
                >
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div
                        className="h-full bg-[var(--color-success)] transition-all"
                        style={{ width: `${(accuracy * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {(accuracy * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">
              多练几次就有了！
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
