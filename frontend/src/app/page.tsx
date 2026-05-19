"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  BookOpen,
  Brain,
  Target,
  TrendingUp,
  MessageCircle,
  Loader2,
  Dumbbell,
  Trophy,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import Card from "@/components/ui/Card";
import UnifiedSearch from "@/components/search/UnifiedSearch";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProgressSummary {
  total_questions: number;
  correct_answers: number;
  accuracy_rate: number;
  study_minutes: number;
  mastered_skills: string[];
  struggling_skills: string[];
  recommendations: string[];
}

interface Achievement {
  id: string;
  name: string;
  icon: string;
  unlocked: boolean;
  tier: string;
}

const QUICK_ACTIONS = [
  { emoji: "💬", title: "智能对话", desc: "随时提问", href: "/chat" },
  { emoji: "✏️", title: "开始练习", desc: "刷题检测", href: "/practice" },
  { emoji: "📊", title: "学情分析", desc: "进度追踪", href: "/analytics" },
  { emoji: "🧠", title: "知识图谱", desc: "补充薄弱", href: "/graph" },
];

export default function HomePage() {
  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 6) return "夜深了，注意休息 🌙";
    if (h < 12) return "早上好 ☀️";
    if (h < 18) return "下午好 🌤️";
    return "晚上好 🌙";
  }, []);

  // Data states
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [progressRes, achieveRes] = await Promise.all([
          fetch(`${API_BASE}/api/progress/summary?user_id=default_user`),
          fetch(`${API_BASE}/api/achievements/default_user`),
        ]);

        if (progressRes.ok) setProgress(await progressRes.json());
        if (achieveRes.ok) {
          const aData = await achieveRes.json();
          setAchievements(aData.achievements || []);
        }
      } catch (e) {
        console.error("Failed to load dashboard data:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Derived stats
  const accuracy = progress?.accuracy_rate
    ? `${(progress.accuracy_rate * 100).toFixed(1)}%`
    : "—";
  const masteredCount = progress?.mastered_skills?.length || 0;
  const strugglingCount = progress?.struggling_skills?.length || 0;
  const unlockedAchievements = achievements.filter((a) => a.unlocked).length;

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-16">
        {/* Header */}
        <header className="mb-10 sm:mb-16">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-[var(--color-text)] mb-3">
            {greeting}
          </h1>
          <p className="text-base sm:text-lg text-[var(--color-text-muted)]">
            {loading ? (
              <Loader2 size={16} className="animate-spin inline" />
            ) : (
              <>
                已练习{" "}
                <span className="text-[var(--color-text)] font-semibold">
                  {progress?.total_questions || 0}
                </span>{" "}
                题 · 正确率{" "}
                <span className="text-[var(--color-accent)] font-semibold">
                  {accuracy}
                </span>
              </>
            )}
          </p>
        </header>

        {/* P1: Unified Search */}
        <div className="mb-10">
          <UnifiedSearch />
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
          {QUICK_ACTIONS.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 hover:border-[var(--color-accent)] transition-colors group"
            >
              <div className="text-xl mb-1.5">{action.emoji}</div>
              <div className="text-xs font-semibold text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors">
                {action.title}
              </div>
              <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                {action.desc}
              </div>
            </Link>
          ))}
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-10">
          {[
            {
              icon: <Dumbbell size={18} />,
              label: "完成题目",
              value: loading ? "—" : `${progress?.total_questions || 0} 道`,
              color: "text-blue-400",
            },
            {
              icon: <Target size={18} />,
              label: "正确率",
              value: loading ? "—" : accuracy,
              color: "text-green-400",
            },
            {
              icon: <Brain size={18} />,
              label: "已掌握",
              value: loading ? "—" : `${masteredCount} 个`,
              color: "text-purple-400",
            },
            {
              icon: <Trophy size={18} />,
              label: "成就",
              value: loading ? "—" : `${unlockedAchievements} 个`,
              color: "text-yellow-400",
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 sm:p-5"
            >
              <div className={`mb-2 ${stat.color}`}>{stat.icon}</div>
              <div className="text-xl sm:text-2xl font-bold text-[var(--color-text)]">
                {stat.value}
              </div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Weak areas */}
          <div>
            <Card title="需要加强">
              {loading ? (
                <div className="py-4 text-center">
                  <Loader2 size={14} className="animate-spin mx-auto" />
                </div>
              ) : strugglingCount > 0 ? (
                <div className="space-y-2">
                  {progress?.struggling_skills.slice(0, 5).map((skill) => (
                    <div
                      key={skill}
                      className="flex items-center gap-2 px-3 py-2 bg-[var(--color-surface)] text-xs"
                    >
                      <AlertCircle
                        size={13}
                        className="text-orange-400 flex-shrink-0"
                      />
                      <span className="text-[var(--color-text-secondary)]">
                        {skill.replace(/_/g, " ")}
                      </span>
                    </div>
                  ))}
                  <Link
                    href="/practice"
                    className="block text-center text-xs text-[var(--color-accent)] hover:underline mt-2"
                  >
                    针对性练习 →
                  </Link>
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                  <Sparkles size={16} className="mx-auto mb-1 text-yellow-400" />
                  暂无薄弱项，继续保持！
                </div>
              )}
            </Card>
          </div>

          {/* Recommendations */}
          <div>
            <Card title="学习建议">
              {loading ? (
                <div className="py-4 text-center">
                  <Loader2 size={14} className="animate-spin mx-auto" />
                </div>
              ) : progress?.recommendations?.length ? (
                <div className="space-y-2">
                  {progress.recommendations.slice(0, 3).map((rec, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 px-3 py-2 text-xs"
                    >
                      <Sparkles
                        size={13}
                        className="text-[var(--color-accent)] flex-shrink-0 mt-0.5"
                      />
                      <span className="text-[var(--color-text-secondary)]">
                        {rec}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                  <MessageCircle
                    size={16}
                    className="mx-auto mb-1 text-blue-400"
                  />
                  开始对话获取个性化建议
                </div>
              )}
            </Card>
          </div>

          {/* Achievements */}
          {achievements.length > 0 && (
            <div className="lg:col-span-2">
              <Card title={`成就 (${unlockedAchievements}/${achievements.length})`}>
                <div className="flex flex-wrap gap-2">
                  {achievements.slice(0, 8).map((a) => (
                    <div
                      key={a.id}
                      className={`flex items-center gap-1.5 px-3 py-1.5 border text-xs transition-all ${
                        a.unlocked
                          ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5"
                          : "border-[var(--color-border)] opacity-40"
                      }`}
                    >
                      <span className="text-sm">{a.icon}</span>
                      <span
                        className={
                          a.unlocked
                            ? "text-[var(--color-text)]"
                            : "text-[var(--color-text-muted)]"
                        }
                      >
                        {a.name}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
