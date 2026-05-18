"use client";

import { useState, useEffect } from "react";
import { BarChart3, Target, Clock, TrendingUp, Loader2, BookOpen } from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PracticeStats {
  total_questions: number;
  total_correct: number;
  accuracy: number;
  study_minutes: number;
  weak_skills: [string, number][];
  strong_skills: [string, number][];
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState<PracticeStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/practice/stats`)
      .then((r) => r.json())
      .then((data) => {
        setStats(data);
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

  if (!stats || stats.total_questions === 0) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <BarChart3 size={40} className="mx-auto mb-4 text-[var(--color-text-muted)]" />
          <h1 className="text-3xl font-bold text-[var(--color-text)] mb-2">学情分析</h1>
          <p className="text-[var(--color-text-muted)] mb-6">还没有练习数据</p>
          <Link
            href="/practice"
            className="px-6 py-2.5 bg-[var(--color-accent)] text-[var(--color-text)] text-sm hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            去练习
          </Link>
        </div>
      </main>
    );
  }

  const acc = (stats.accuracy * 100).toFixed(0);
  const h = Math.floor(stats.study_minutes / 60);
  const m = Math.round(stats.study_minutes % 60);

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="flex items-center justify-between mb-12">
          <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text)]">
            <BarChart3 size={28} className="inline mr-3 text-[var(--color-accent)]" />
            学情分析
          </h1>
          <Link
            href="/errors"
            className="flex items-center gap-1.5 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <BookOpen size={14} />
            错题本
          </Link>
        </div>

        {/* Overview */}
        <div className="grid grid-cols-3 gap-4 mb-12">
          {[
            { icon: <Target size={20} />, label: "总题数", val: stats.total_questions, sub: `正确 ${stats.total_correct}` },
            { icon: <TrendingUp size={20} />, label: "正确率", val: `${acc}%`, sub: +acc >= 80 ? "优秀" : +acc >= 60 ? "良好" : "需努力" },
            { icon: <Clock size={20} />, label: "学习时长", val: h > 0 ? `${h}h${m}m` : `${m}m`, sub: "累计时间" },
          ].map((c, i) => (
            <Card key={i}>
              <div className="text-[var(--color-accent)] mb-2">{c.icon}</div>
              <div className="text-2xl font-bold text-[var(--color-text)]">{c.val}</div>
              <div className="text-xs text-[var(--color-text-muted)]">{c.label} · {c.sub}</div>
            </Card>
          ))}
        </div>

        {/* Weak */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">🔴 薄弱知识点</h2>
          {stats.weak_skills?.length ? (
            <div className="space-y-2">
              {stats.weak_skills.map(([skill, ac]) => (
                <div key={skill} className="flex items-center justify-between p-3 bg-[var(--color-surface)]">
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div className="h-full bg-[var(--color-error)]" style={{ width: `${(ac * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">{(ac * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-[var(--color-text-muted)]">暂无数据</p>}
        </div>

        {/* Strong */}
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">🟢 掌握好的知识点</h2>
          {stats.strong_skills?.length ? (
            <div className="space-y-2">
              {stats.strong_skills.map(([skill, ac]) => (
                <div key={skill} className="flex items-center justify-between p-3 bg-[var(--color-surface)]">
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div className="h-full bg-[var(--color-success)]" style={{ width: `${(ac * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">{(ac * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-[var(--color-text-muted)]">多练几次就有了！</p>}
        </div>
      </div>
    </main>
  );
}
