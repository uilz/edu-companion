"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import {
  Brain, Trophy, BarChart3, RotateCcw, BookOpen, Play,
  Sparkles, Clock, Loader2, ChevronRight, Target, TrendingUp,
  BookMarked, FileText, Star,
} from "lucide-react";
import Link from "next/link";

import PracticePanel from "@/components/practice/PracticePanel";

type Tab = "start" | "practice" | "stats";

export default function PracticeHomePage() {
  const searchParams = useSearchParams();
  const skillParam = searchParams.get("skill");

  const [tab, setTab] = useState<Tab>(skillParam ? "practice" : "start");
  const [overview, setOverview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [recentSessions, setRecentSessions] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      fetch("/api/v7/practice/stats/overview").then((r) => r.json()).catch(() => null),
      fetch("/api/v7/practice/stats/sessions?limit=5").then((r) => r.json()).catch(() => []),
      fetch("/api/v7/practice/review/stats").then((r) => r.json()).catch(() => null),
    ]).then(([ov, sessions, review]) => {
      setOverview({ ...ov, ...review });
      setRecentSessions(Array.isArray(sessions) ? sessions : sessions?.items || []);
      setLoading(false);
    });
  }, []);

  if (tab === "practice") {
    return (
      <div className="min-h-screen bg-[var(--color-bg)]">
        {/* Top bar */}
        <div className="sticky top-0 z-30 bg-[var(--color-bg)]/90 backdrop-blur-sm border-b border-[var(--color-border)]/50">
          <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
            <button onClick={() => setTab("start")}
              className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
              ← 返回
            </button>
            <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
            <span className="text-[12px] font-medium text-[var(--color-text)]">智能练习</span>
          </div>
        </div>
        <div className="max-w-3xl mx-auto" style={{ height: "calc(100vh - 48px - var(--bottom-nav-height, 0px))" }}>
          <PracticePanel
            nodeId={skillParam || undefined}
            nodeLabel={skillParam ? skillParam.replace(/_/g, " ") : undefined}
            onClose={() => setTab("start")}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 max-w-3xl mx-auto">
      {/* Hero */}
      <div className="text-center mb-8">
        <div className="w-14 h-14 rounded-2xl bg-[var(--color-accent)]/10 flex items-center justify-center mx-auto mb-3">
          <Brain size={28} className="text-[var(--color-accent)]" />
        </div>
        <h1 className="text-xl font-bold text-[var(--color-text)]">智能练习</h1>
        <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
          自适应出题 · 间隔重复 · 错题本 · 知识图谱联动
        </p>
      </div>

      {/* Quick start */}
      <button onClick={() => setTab("practice")}
        className="w-full flex items-center justify-between p-4 rounded-xl bg-[var(--color-accent)] text-white mb-6 hover:opacity-90 transition-opacity">
        <div className="flex items-center gap-3">
          <Play size={20} />
          <div className="text-left">
            <p className="text-sm font-semibold">开始练习</p>
            <p className="text-[10px] text-white/70">自适应模式 · 薄弱优先</p>
          </div>
        </div>
        <ChevronRight size={18} className="text-white/60" />
      </button>

      {/* Stats cards */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
        </div>
      ) : (
        <>
          {/* 练习概览 */}
          {overview && (
            <div className="grid grid-cols-4 gap-3 mb-6">
              <StatCard icon={<Brain size={14} />} label="总题数" value={String(overview.total_questions || 0)} />
              <StatCard icon={<Target size={14} />} label="正确率" value={`${Math.round((overview.accuracy || 0) * 100)}%`} />
              <StatCard icon={<Clock size={14} />} label="学习时长" value={`${Math.round((overview.study_minutes || 0) / 60)}h`} />
              <StatCard icon={<BookMarked size={14} />} label="待复习" value={String(overview.due_now || overview.due_review_count || 0)} />
            </div>
          )}

          {/* 薄弱知识点 */}
          {overview?.weak_count > 0 && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/5 border border-red-500/20">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={14} className="text-red-500" />
                <span className="text-[11px] font-medium text-red-600">薄弱知识点</span>
                <span className="ml-auto text-[10px] text-red-500/70">{overview.weak_count} 个</span>
              </div>
              <p className="text-[10px] text-[var(--color-text-muted)]">建议优先练习薄弱知识点，巩固掌握度</p>
            </div>
          )}

          {/* Quick links */}
          <div className="grid grid-cols-4 gap-2 mb-6">
            <Link href="/exam" className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-red-500/5 border border-red-500/20 hover:border-red-500/40 transition-all">
              <FileText size={16} className="text-red-500" />
              <span className="text-[10px] font-medium text-red-600">模拟考试</span>
            </Link>
            <Link href="/errors" className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 transition-all">
              <FileText size={16} className="text-orange-500" />
              <span className="text-[10px] font-medium text-[var(--color-text)]">错题本</span>
            </Link>
            <Link href="/achievements" className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 transition-all">
              <Trophy size={16} className="text-yellow-500" />
              <span className="text-[10px] font-medium text-[var(--color-text)]">成就墙</span>
            </Link>
            <Link href="/stats" className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 transition-all">
              <BarChart3 size={16} className="text-blue-500" />
              <span className="text-[10px] font-medium text-[var(--color-text)]">统计</span>
            </Link>
          </div>

          {/* Recent sessions */}
          {recentSessions.length > 0 && (
            <div>
              <h3 className="text-[11px] font-medium text-[var(--color-text-muted)] mb-3 uppercase tracking-wider">最近练习</h3>
              <div className="space-y-2">
                {recentSessions.map((s: any) => (
                  <div key={s.session_id}
                    className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                      (s.score || 0) >= 80 ? "bg-green-500/10" :
                      (s.score || 0) >= 60 ? "bg-yellow-500/10" : "bg-red-500/10"
                    }`}>
                      <Brain size={14} className={
                        (s.score || 0) >= 80 ? "text-green-500" :
                        (s.score || 0) >= 60 ? "text-yellow-500" : "text-red-500"
                      } />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-[var(--color-text)]">
                        {s.mode === "review" ? "复习模式" : s.mode === "challenge" ? "挑战模式" : "自适应模式"}
                        <span className="ml-2 text-[10px] text-[var(--color-text-muted)]">
                          {s.total_count} 题 · {s.correct_count}/{s.wrong_count}
                        </span>
                      </p>
                      <p className="text-[10px] text-[var(--color-text-muted)]">
                        {s.score != null ? `${s.score}分 · ` : ""}
                        {s.duration_seconds ? `${Math.round(s.duration_seconds / 60)}分钟` : ""}
                        · {s.created_at?.slice(0, 10)}
                      </p>
                    </div>
                    <span className={`text-[11px] font-bold ${
                      (s.score || 0) >= 80 ? "text-green-500" :
                      (s.score || 0) >= 60 ? "text-yellow-500" : "text-red-500"
                    }`}>{s.score ?? "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!recentSessions.length && !loading && (
            <div className="text-center py-12">
              <Sparkles size={24} className="mx-auto text-[var(--color-text-muted)] mb-3" />
              <p className="text-[13px] text-[var(--color-text-muted)]">还没有练习记录</p>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-1">点击上方按钮开始首次练习</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-1 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
      <span className="text-[var(--color-text-muted)]">{icon}</span>
      <span className="text-lg font-bold text-[var(--color-text)]">{value}</span>
      <span className="text-[9px] text-[var(--color-text-muted)]">{label}</span>
    </div>
  );
}
