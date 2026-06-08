"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Brain, Play, Clock, BarChart3, BookMarked, BookOpen,
  Loader2, ChevronRight, TrendingUp, History, FileText,
  Trash2, Sparkles, RotateCcw, ListTodo, Wand2,
  GraduationCap, Target, Library,
} from "lucide-react";
import Link from "next/link";

import PracticePanel from "@/components/practice/panels/PracticePanel";
import ExamPanel from "@/components/practice/panels/ExamPanel";

type Tab = "start" | "practice" | "exam";

export default function PracticeHomePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const skillParam = searchParams.get("skill");
  const tabParam = searchParams.get("tab");
  const bankParam = searchParams.get("bank_id");

  const [tab, setTab] = useState<Tab>(tabParam === "exam" ? "exam" : tabParam === "practice" ? "practice" : "start");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [recentSessions, setRecentSessions] = useState<any[]>([]);
  const [unfinished, setUnfinished] = useState<any[]>([]);
  const [dueReviews, setDueReviews] = useState<any[]>([]);
  const [banks, setBanks] = useState<any[]>([]);
  const [selectedBankId, setSelectedBankId] = useState<string>(bankParam || "");

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
      fetch("/api/v7/practice/stats/overview").then(r => r.json()).catch(() => null),
      fetch("/api/v7/practice/stats/sessions?limit=5").then(r => r.json()).catch(() => ({ items: [] })),
      fetch("/api/v7/practice/review/stats").then(r => r.json()).catch(() => null),
      fetch("/api/v7/practice/sessions/unfinished").then(r => r.json()).catch(() => ({ items: [] })),
      fetch("/api/v7/practice/review/due?limit=5").then(r => r.json()).catch(() => []),
      fetch("/api/v7/practice/banks").then(r => r.json()).catch(() => []),
    ]).then(([ov, sess, rev, unf, dueR, bk]) => {
      setData({ ...(ov || {}), ...(rev || {}) });
      setRecentSessions(Array.isArray(sess) ? sess : sess?.items || []);
      setUnfinished(Array.isArray(unf) ? unf : unf?.items || []);
      setDueReviews(Array.isArray(dueR) ? dueR : dueR?.items || []);
      setBanks(Array.isArray(bk) ? bk : []);
      setLoading(false);
    });
  }, []);

  const handleDelete = async (id: string) => {
    await fetch(`/api/v7/practice/sessions/${id}`, { method: "DELETE" });
    setRecentSessions(p => p.filter(s => s.session_id !== id));
  };

  const handleStartExam = (bankId: string) => {
    setSelectedBankId(bankId);
    switchTab("exam", { bank_id: bankId });
  };

  // ── 考试模式 ──
  if (tab === "exam") {
    return (
      <div className="min-h-screen bg-[var(--color-bg)]">
        <div className="sticky top-0 z-30 bg-[var(--color-bg)]/90 backdrop-blur-sm border-b border-[var(--color-border)]/50">
          <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
            <button onClick={() => switchTab("start")}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
              ← 返回
            </button>
            <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
            <span className="text-xs font-medium text-[var(--color-text)]">模拟考试</span>
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
      <div className="min-h-screen bg-[var(--color-bg)]">
        <div className="sticky top-0 z-30 bg-[var(--color-bg)]/90 backdrop-blur-sm border-b border-[var(--color-border)]/50">
          <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
            <button onClick={() => switchTab("start")}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
              ← 返回
            </button>
            <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
            <span className="text-xs font-medium text-[var(--color-text)]">智能练习</span>
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
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* 头部 */}
      <div className="sticky top-0 z-10 bg-[var(--color-bg)]/80 backdrop-blur-sm border-b border-[var(--color-border)]/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
              <Brain size={16} className="text-[var(--color-accent)]" />
            </div>
            <span className="text-sm font-semibold text-[var(--color-text)]">练习</span>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-5 space-y-5">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : (
          <>
            {/* ── 双入口：自适应练习 + 模拟考试 ── */}
            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => switchTab("practice")}
                className="flex items-center justify-between p-4 rounded-xl bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity">
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
                className="flex items-center justify-between p-4 rounded-xl bg-orange-500 text-white hover:opacity-90 transition-opacity">
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
                <StatCard icon={<Brain size={13} />} label="总题数" value={String(data.total_questions || 0)} />
                <StatCard icon={<TrendingUp size={13} />} label="正确率" value={`${Math.round((data.accuracy || 0))}%`} />
                <StatCard icon={<Clock size={13} />} label="练习" value={`${Math.round((data.study_minutes || 0) / 60)}h`} />
                <StatCard icon={<BookMarked size={13} />} label="待复习" value={String(data.due_review_count || 0)} />
              </div>
            )}

            {/* ── 快速入口 - 4列 ── */}
            <div className="grid grid-cols-2 gap-2">
              <QuickLink href="/practice/errors" icon={<FileText size={14} />} label="错题本" color="text-orange-500" />
              <QuickLink href="/practice/history" icon={<History size={14} />} label="练习历史" color="text-blue-500" />
              <QuickLink href="/practice/banks" icon={<Library size={14} />} label="题库浏览" color="text-purple-500" />
              <QuickLink href="/practice/generate" icon={<Wand2 size={14} />} label="AI 出题" color="text-emerald-500" />
            </div>

            {/* ── 复习队列 ── */}
            {dueReviews.length > 0 && (
              <section>
                <h3 className="text-xs font-medium text-[var(--color-text-muted)] mb-2.5 flex items-center gap-1.5">
                  <RotateCcw size={12} /> 待复习 <span className="text-[10px] text-orange-500">({dueReviews.length}题)</span>
                </h3>
                <div className="space-y-1.5">
                  {dueReviews.map((r: any) => {
                    const q = r.question || r;
                    const qid = q.id || r.question_id;
                    const stem = q.stem || q.question_text || "";
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
                          ? "bg-blue-500/5 border-blue-500/15"
                          : "bg-orange-500/5 border-orange-500/15"
                      }`}>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        isColdStart ? "bg-blue-500/10" : "bg-orange-500/10"
                      }`}>
                        <RotateCcw size={13} className={isColdStart ? "text-blue-500" : "text-orange-500"} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-[var(--color-text)] truncate">
                          {stem.slice(0, 60)}
                        </p>
                        <p className="text-[10px] text-[var(--color-text-muted)]">
                          {isColdStart
                            ? "尚未练习过"
                            : `做错${wrongCount}次 · ${dueLabel}`}
                        </p>
                      </div>
                      <Link href={`/practice/review/${qid}`}
                        className={`px-3 py-1.5 rounded-lg text-white text-[10px] font-medium flex-shrink-0 ${
                          isColdStart
                            ? "bg-blue-500 hover:bg-blue-600"
                            : "bg-orange-500 hover:bg-orange-600"
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
                <h3 className="text-xs font-medium text-amber-500 mb-2.5 flex items-center gap-1.5">
                  <ListTodo size={12} /> 未完成
                </h3>
                <div className="space-y-1.5">
                  {unfinished.map((s: any) => (
                    <div key={s.session_id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-amber-500/5 border border-amber-500/15">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-500/10">
                        <RotateCcw size={13} className="text-amber-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-[var(--color-text)] truncate">
                          {s.mode === "exam" ? "模拟考试" : s.mode === "review" ? "复习" : "自适应练习"}
                          <span className="ml-1.5 text-[10px] text-[var(--color-text-muted)]">
                            {s.total_count}题 · {s.answered_count ?? 0}已答
                          </span>
                        </p>
                      </div>
                      <Link href={`/practice/sessions/${s.session_id}`}
                        className="px-3 py-1.5 rounded-lg bg-amber-500 text-white text-[10px] font-medium hover:bg-amber-600 flex-shrink-0">
                        继续
                      </Link>
                      <button onClick={() => handleDelete(s.session_id)}
                        className="p-1 rounded text-[var(--color-text-muted)] hover:text-red-500">
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
                  <h3 className="text-xs font-medium text-[var(--color-text-muted)]">最近练习</h3>
                  <Link href="/practice/history" className="text-[10px] text-[var(--color-accent)] hover:underline">
                    全部 →
                  </Link>
                </div>
                <div className="space-y-1.5">
                  {recentSessions.slice(0, 3).map((s: any) => {
                    const score = s.score ?? 0;
                    const color = score >= 80 ? "text-green-500" : score >= 60 ? "text-amber-500" : "text-red-500";
                    const bg = score >= 80 ? "bg-green-500/10" : score >= 60 ? "bg-amber-500/10" : "bg-red-500/10";
                    return (
                      <div key={s.session_id}
                        onClick={() => router.push(`/practice/history/${s.session_id}`)}
                        className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 cursor-pointer hover:border-[var(--color-accent)]/30 transition-all group">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${bg}`}>
                          {s.mode === "exam" ? <GraduationCap size={14} className={color} /> : <Brain size={14} className={color} />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-[var(--color-text)] truncate">
                            {s.bank_name || (s.mode === "exam" ? "模拟考试" : s.mode === "review" ? "复习" : "自适应")}
                          </p>
                          <p className="text-[10px] text-[var(--color-text-muted)]">
                            {s.total_count}题 · {s.correct_count}/{s.wrong_count}
                            {s.duration_seconds ? ` · ${Math.round(s.duration_seconds / 60)}分钟` : ""}
                          </p>
                        </div>
                        <span className={`text-xs font-bold ${color}`}>{score}{score ? "分" : ""}</span>
                        <button onClick={(e) => { e.stopPropagation(); handleDelete(s.session_id); }}
                          className="p-1 rounded opacity-0 group-hover:opacity-100 text-[var(--color-text-muted)] hover:text-red-500 transition-all">
                          <Trash2 size={11} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </section>
            ) : (
              <div className="text-center py-12">
                <Sparkles size={22} className="mx-auto text-[var(--color-text-muted)] mb-2" />
                <p className="text-sm text-[var(--color-text-muted)]">还没有练习记录</p>
                <p className="text-xs text-[var(--color-text-muted)] mt-1">点击上方按钮开始首次练习或考试</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
      <span className="text-[var(--color-text-muted)]">{icon}</span>
      <span className="text-lg font-bold text-[var(--color-text)]">{value}</span>
      <span className="text-[9px] text-[var(--color-text-muted)]">{label}</span>
    </div>
  );
}

function QuickLink({ href, icon, label, color }: { href: string; icon: React.ReactNode; label: string; color: string }) {
  return (
    <Link href={href}
      className="flex items-center gap-2 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 transition-all">
      <span className={color}>{icon}</span>
      <span className="text-xs font-medium text-[var(--color-text)]">{label}</span>
    </Link>
  );
}
