"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Brain, Play, Clock, BarChart3, BookMarked, BookOpen,
  ChevronRight, TrendingUp, History, FileText,
  Trash2, Sparkles, RotateCcw, ListTodo, Wand2,
  GraduationCap, Target, Library,
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import Link from "next/link";

import PracticePanel from "@/components/practice/panels/PracticePanel";
import ExamPanel from "@/components/practice/panels/ExamPanel";
import QuestionStem from "@/components/practice/components/QuestionStem";
import { StatCard } from "@/components/ui/StatCard";
import { practiceService, type DueQuestion, type V7Bank, type V7SessionListItem, type V7Overview, type ReviewStats, type UnfinishedSession, type ErrorBookStats } from "@/lib/api/practice-api";

type Tab = "start" | "practice" | "exam";

interface PracticeDashboardData {
  total_questions?: number;
  accuracy?: number;
  study_minutes?: number;
  due_review_count?: number;
}

interface WeakSkill {
  skill_id: string;
  label: string;
  mastery: number;
  attempts: number;
  trend: string;
  load?: number;
}

export default function PracticeHomePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const skillParam = searchParams.get("skill");
  const tabParam = searchParams.get("tab");
  const bankParam = searchParams.get("bank_id");

  const [tab, setTab] = useState<Tab>(tabParam === "exam" ? "exam" : tabParam === "practice" ? "practice" : "start");
  const [data, setData] = useState<PracticeDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentSessions, setRecentSessions] = useState<V7SessionListItem[]>([]);
  const [unfinished, setUnfinished] = useState<UnfinishedSession[]>([]);
  const [dueReviews, setDueReviews] = useState<DueQuestion[]>([]);
  const [banks, setBanks] = useState<V7Bank[]>([]);
  const [selectedBankId, setSelectedBankId] = useState<string>(bankParam || "");
  const [weakSkills, setWeakSkills] = useState<WeakSkill[]>([]);
  const [errorBookStats, setErrorBookStats] = useState<ErrorBookStats | null>(null);

  // URL 双向同步
  useEffect(() => {
    if (tabParam === "exam") setTab("exam");
    else if (tabParam === "practice" || skillParam) setTab("practice");
  }, [tabParam, skillParam]);

  const switchTab = (t: Tab, extra?: Record<string, string>) => {
    setTab(t);
    const params = new URLSearchParams(searchParams.toString());
    if (t === "practice") params.set("tab", "practice");
    else if (t === "exam") params.set("tab", "exam");
    else params.delete("tab");
    if (extra) {
      Object.entries(extra).forEach(([k, v]) => params.set(k, v));
    }
    router.replace(`/practice?${params.toString()}`, { scroll: false });
  };

  useEffect(() => {
    Promise.all([
      practiceService.getOverview().catch(() => null),
      practiceService.getSessionHistory(5).catch(() => []),
      practiceService.getReviewStats().catch(() => null),
      practiceService.getUnfinishedSessions().catch(() => ({ items: [] })),
      practiceService.getDueQuestions({ limit: 5 }).catch(() => []),
      practiceService.listBanks().catch(() => []),
    ]).then(([ov, sess, rev, unf, dueR, bk]) => {
      setData({ ...(ov || {}), ...(rev || {}) });
      setRecentSessions(Array.isArray(sess) ? sess : []);
      setUnfinished(Array.isArray(unf) ? unf : unf?.items || []);
      setDueReviews(Array.isArray(dueR) ? dueR : []);
      setBanks(Array.isArray(bk) ? bk : []);
      setLoading(false);
    });

    // 加载薄弱点 & 错题统计
    practiceService.getWeakSkills().then(setWeakSkills).catch(() => {});
    practiceService.getErrorBookStats().then(setErrorBookStats).catch(() => {});
  }, []);

  const handleDelete = async (id: string) => {
    await practiceService.cancelSession(id);
    setRecentSessions(p => p.filter(s => s.session_id !== id));
    setUnfinished(p => p.filter(s => s.session_id !== id));
    setDueReviews(p => p.filter((r) => {
      const qid = r.question?.id || "";
      return qid !== id;
    }));
  };

  const handleStartExam = (bankId: string) => {
    setSelectedBankId(bankId);
    switchTab("exam", { bank_id: bankId });
  };

  // ── 考试模式 ──
  if (tab === "exam") {
    return (
      <div className="min-h-screen bg-page">
        <div className="sticky top-0 z-30 bg-page/90 backdrop-blur-sm border-b border/50">
          <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
            <button onClick={() => switchTab("start")}
              className="text-xs text-muted hover:text transition-colors">
              ← 返回
            </button>
            <span className="text-[11px] text-muted">|</span>
            <span className="text-xs font-medium text">模拟考试</span>
          </div>
        </div>
        <div className="max-w-3xl mx-auto" style={{ height: "calc(100vh - 48px - var(--bottom-nav-height, 0px))" }}>
          <ExamPanel
            bankId={selectedBankId}
            bankName={banks.find(b => b.id === selectedBankId)?.name || ""}
            nodeId={skillParam || undefined}
            onClose={() => switchTab("start")}
          />
        </div>
      </div>
    );
  }

  // ── 练习模式 ──
  if (tab === "practice") {
    return (
      <div className="min-h-screen bg-page">
        <div className="sticky top-0 z-30 bg-page/90 backdrop-blur-sm border-b border/50">
          <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
            <button onClick={() => switchTab("start")}
              className="text-xs text-muted hover:text transition-colors">
              ← 返回
            </button>
            <span className="text-[11px] text-muted">|</span>
            <span className="text-xs font-medium text">智能练习</span>
          </div>
        </div>
        <div className="max-w-3xl mx-auto" style={{ height: "calc(100vh - 48px - var(--bottom-nav-height, 0px))" }}>
          <PracticePanel
            bankId={selectedBankId || undefined}
            nodeId={skillParam || undefined}
            nodeLabel={skillParam ? skillParam.replace(/_/g, " ") : undefined}
            onClose={() => switchTab("start")}
          />
        </div>
      </div>
    );
  }

  // ── 首页 ──
  return (
    <div className="min-h-screen bg-page">
      {/* 头部 */}
      <div className="sticky top-0 z-10 bg-page/80 backdrop-blur-sm border-b border/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center">
              <Brain size={16} className="text-accent" />
            </div>
            <span className="text-sm font-semibold text">练习</span>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-5 space-y-5">
        {loading ? (
          <PageSkeleton />
        ) : (
          <>
            {/* ── 双入口：自适应练习 + 模拟考试 ── */}
            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => switchTab("practice")}
                className="flex items-center justify-between p-4 rounded-xl bg-accent text-white hover:opacity-90 transition-opacity">
                <div className="flex items-center gap-3">
                  <Play size={18} />
                  <div className="text-left">
                    <p className="text-sm font-semibold">自适应练习</p>
                    <p className="text-[10px] text-white/70">薄弱优先</p>
                  </div>
                </div>
                <ChevronRight size={16} className="text-white/50" />
              </button>

              <button onClick={() => handleStartExam(banks[0]?.id || "")}
                className="flex items-center justify-between p-4 rounded-xl bg-warning text-white hover:opacity-90 transition-opacity">
                <div className="flex items-center gap-3">
                  <GraduationCap size={18} />
                  <div className="text-left">
                    <p className="text-sm font-semibold">模拟考试</p>
                    <p className="text-[10px] text-white/70">限时测验</p>
                  </div>
                </div>
                <ChevronRight size={16} className="text-white/50" />
              </button>
            </div>

            {/* ── 统计行 ── */}
            {data && (
              <div className="grid grid-cols-4 gap-2.5">
                <StatCard variant="minimal" icon={<Brain size={13} />} label="总题数" value={String(data.total_questions || 0)} />
                <StatCard variant="minimal" icon={<TrendingUp size={13} />} label="正确率" value={`${Math.round((data.accuracy || 0))}%`} />
                <StatCard variant="minimal" icon={<Clock size={13} />} label="练习" value={`${Math.round((data.study_minutes || 0) / 60)}h`} />
                <StatCard variant="minimal" icon={<BookMarked size={13} />} label="待复习" value={String(data.due_review_count || 0)} />
              </div>
            )}

            {/* ── 快速入口 - 4列 ── */}
            <div className="grid grid-cols-2 gap-2">
              <QuickLink href="/practice/errors" icon={<FileText size={14} />} label="错题本" color="text-warning" />
              <QuickLink href="/practice/history" icon={<History size={14} />} label="练习历史" color="text-info" />
              <QuickLink href="/practice/banks" icon={<Library size={14} />} label="题库浏览" color="text-accent" />
              <QuickLink href="/practice/generate" icon={<Wand2 size={14} />} label="AI 出题" color="text-success" />
            </div>

            {/* ── 薄弱点分析 ── */}
            {(weakSkills.length > 0 || errorBookStats) && (
              <section>
                <h3 className="text-xs font-medium text-muted mb-2.5 flex items-center gap-1.5">
                  <Target size={12} /> 薄弱点分析
                </h3>
                <div className="space-y-2">
                  {/* 错题总览小卡片 */}
                  {errorBookStats && (
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-danger/5 border border-danger/15 mb-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-danger/10">
                        <FileText size={13} className="text-danger" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text">
                          错题本 · {errorBookStats.still_weak ?? 0} 题仍薄弱
                        </p>
                        <p className="text-[10px] text-muted">
                          共 {errorBookStats.unique_wrong_questions ?? 0} 道错题 · {errorBookStats.total_wrong_attempts ?? 0} 次失误
                          {errorBookStats.mastered_from_errors > 0 && ` · 已攻破 ${errorBookStats.mastered_from_errors} 题`}
                        </p>
                      </div>
                      <Link href="/practice/errors"
                        className="px-3 py-1.5 rounded-lg bg-danger text-white text-[10px] font-medium hover:bg-danger flex-shrink-0">
                        查看
                      </Link>
                    </div>
                  )}

                  {/* 薄弱知识点列表 */}
                  {weakSkills.length > 0 && (
                    <div className="space-y-1.5">
                      {weakSkills.slice(0, 5).map((skill) => {
                        const mastery = skill.mastery ?? 0;
                        const color = mastery < 30 ? "text-danger" : mastery < 50 ? "text-warning" : "text-warning";
                        const bg = mastery < 30 ? "bg-danger/5 border-danger/15" : mastery < 50 ? "bg-warning/5 border-warning/15" : "bg-warning/5 border-warning/15";
                        const barColor = mastery < 30 ? "bg-danger/80" : mastery < 50 ? "bg-warning/80" : "bg-warning/80";
                        return (
                          <div key={skill.skill_id}
                            className={`flex items-center gap-3 p-3 rounded-xl border ${bg}`}>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between mb-1">
                                <p className="text-xs font-medium text truncate">
                                  {skill.label}
                                </p>
                                <span className={`text-[10px] font-bold ml-2 ${color}`}>{mastery}%</span>
                              </div>
                              <div className="w-full h-1.5 bg-divider/50 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${barColor} transition-all`}
                                  style={{ width: `${mastery}%` }} />
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-[9px] text-muted">
                                  {skill.attempts ?? 0} 次练习
                                </span>
                                {skill.trend === "up" && <span className="text-[9px] text-success">↑ 上升</span>}
                                {skill.trend === "down" && <span className="text-[9px] text-danger">↓ 下降</span>}
                                {skill.load !== undefined && (
                                  <span className="text-[9px] text-muted">
                                    · 掌握负载: {skill.load}
                                  </span>
                                )}
                              </div>
                            </div>
                            <button onClick={() => switchTab("practice")}
                              className="px-3 py-1.5 rounded-lg bg-accent text-white text-[10px] font-medium hover:opacity-90 flex-shrink-0">
                              去练习
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* ── 复习队列 ── */}
            {dueReviews.length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-muted mb-2.5 flex items-center gap-1.5">
                  <RotateCcw size={12} /> 待复习 <span className="text-[10px] text-warning">({dueReviews.length}题)</span>
                </h3>
                <div className="space-y-1.5">
                  {dueReviews.map((r) => {
                    const q = r.question;
                    const qid = q.id;
                    const stem = q.stem || "";
                    const wrongCount = r.wrong_count || 0;
                    const isColdStart = !!r.is_cold_start;
                    // 冷启动推荐（无答题历史）显示"新题 · 推荐优先练习"；
                    // 否则根据 due/days_until_next_review 渲染
                    const dueLabel = isColdStart
                      ? "新题 · 推荐优先练习"
                      : r.due
                        ? "已到期"
                        : `${Math.ceil(r.days_until_next_review || 0)}天后到期`;
                    return (
                    <div key={qid}
                      className={`flex items-center gap-3 p-3 rounded-xl border ${
                        isColdStart
                          ? "bg-info/5 border-info/15"
                          : "bg-warning/5 border-warning/15"
                      }`}>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        isColdStart ? "bg-info/10" : "bg-warning/10"
                      }`}>
                        <RotateCcw size={13} className={isColdStart ? "text-info" : "text-warning"} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-medium text line-clamp-2">
                          <QuestionStem stem={stem} />
                        </div>
                        <p className="text-[10px] text-muted">
                          {isColdStart
                            ? "尚未练习过"
                            : `做错${wrongCount}次 · ${dueLabel}`}
                        </p>
                      </div>
                      <Link href={`/practice/review/${qid}`}
                        className={`px-3 py-1.5 rounded-lg text-white text-[10px] font-medium flex-shrink-0 ${
                          isColdStart
                            ? "bg-info hover:bg-info"
                            : "bg-warning hover:bg-warning"
                        }`}>
                        {isColdStart ? "开始" : "复习"}
                      </Link>
                    </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* ── 未完成 ── */}
            {unfinished.length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-warning mb-2.5 flex items-center gap-1.5">
                  <ListTodo size={12} /> 未完成
                </h3>
                <div className="space-y-1.5">
                  {unfinished.map((s) => (
                    <div key={s.session_id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-warning/5 border border-warning/15">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-warning/10">
                        <RotateCcw size={13} className="text-warning" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text truncate">
                          {s.mode === "exam" ? "模拟考试" : s.mode === "review" ? "复习" : "自适应练习"}
                          <span className="ml-1.5 text-[10px] text-muted">
                            {s.total_count}题 · {s.answered_count ?? 0}已答
                          </span>
                        </p>
                      </div>
                      <Link href={`/practice/sessions/${s.session_id}`}
                        className="px-3 py-1.5 rounded-lg bg-warning text-white text-[10px] font-medium hover:bg-warning flex-shrink-0">
                        继续
                      </Link>
                      <button onClick={() => handleDelete(s.session_id)}
                        className="p-1 rounded text-muted hover:text-danger">
                        <Trash2 size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── 最近练习 ── */}
            {recentSessions.length > 0 ? (
              <section>
                <div className="flex items-center justify-between mb-2.5">
                  <h3 className="text-xs font-medium text-muted">最近练习</h3>
                  <Link href="/practice/history" className="text-[10px] text-accent hover:underline">
                    全部 →
                  </Link>
                </div>
                <div className="space-y-1.5">
                  {recentSessions.slice(0, 3).map((s) => {
                    const score = s.score ?? 0;
                    const color = score >= 80 ? "text-success" : score >= 60 ? "text-warning" : "text-danger";
                    const bg = score >= 80 ? "bg-success/10" : score >= 60 ? "bg-warning/10" : "bg-danger/10";
                    return (
                      <div key={s.session_id}
                        onClick={() => router.push(`/practice/history/${s.session_id}`)}
                        className="flex items-center gap-3 p-3 rounded-xl bg-surface border border/50 cursor-pointer hover:border-accent/30 transition-all group">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${bg}`}>
                          {s.mode === "exam" ? <GraduationCap size={14} className={color} /> : <Brain size={14} className={color} />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text truncate">
                            {s.bank_name || (s.mode === "exam" ? "模拟考试" : s.mode === "review" ? "复习" : "自适应")}
                          </p>
                          <p className="text-[10px] text-muted">
                            {s.total_count}题 · {s.correct_count}/{s.wrong_count}
                            {s.duration_seconds ? ` · ${Math.round(s.duration_seconds / 60)}分钟` : ""}
                          </p>
                        </div>
                        <span className={`text-xs font-bold ${color}`}>{score}{score ? "分" : ""}</span>
                        <button onClick={(e) => { e.stopPropagation(); handleDelete(s.session_id); }}
                          className="p-1 rounded opacity-0 group-hover:opacity-100 text-muted hover:text-danger transition-all">
                          <Trash2 size={11} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </section>
            ) : (
              <div className="text-center py-12">
                <Sparkles size={22} className="mx-auto text-muted mb-2" />
                <p className="text-sm text-muted">还没有练习记录</p>
                <p className="text-xs text-muted mt-1">点击上方按钮开始首次练习或考试</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}



function QuickLink({ href, icon, label, color }: { href: string; icon: React.ReactNode; label: string; color: string }) {
  return (
    <Link href={href}
      className="flex items-center gap-2 p-3 rounded-xl bg-surface border border/50 hover:border-accent/30 transition-all">
      <span className={color}>{icon}</span>
      <span className="text-xs font-medium text">{label}</span>
    </Link>
  );
}
