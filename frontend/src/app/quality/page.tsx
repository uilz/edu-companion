"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Shield, AlertTriangle, CheckCircle, XCircle, Loader2,
  ChevronDown, ChevronUp, Trash2, Zap, BarChart3,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ──
interface QualitySummaryData {
  total_questions: number;
  analyzed: number;
  excellent: number;
  good: number;
  marginal: number;
  poor: number;
  flagged: number;
  retired: number;
  avg_quality: number;
  worst_questions: QuestionPreview[];
}

interface QuestionPreview {
  question_id: string;
  text: string;
  quality_score: number;
  quality_grade: string;
  correct_rate: number;
  total_attempts: number;
  flags: string[];
  status_action: string;
}

interface QuestionDetail {
  question_id: string;
  text: string;
  skill_id: string;
  subject: string;
  total_attempts: number;
  correct_count: number;
  correct_rate: number;
  avg_time_seconds: number;
  difficulty: number;
  discrimination: number;
  guess_rate: number;
  quality_score: number;
  quality_grade: string;
  flags: string[];
  distractors: Distractor[];
  time_fast_ratio: number;
  time_slow_ratio: number;
  current_status: string;
  status_action: string;
}

interface Distractor {
  letter: string;
  text: string;
  count: number;
  rate: number;
  quality: string;
  is_correct: boolean;
}

const GRADE_COLORS: Record<string, string> = {
  excellent: "text-[#10b981] bg-[#10b981]/10",
  good: "text-[#3b82f6] bg-[#3b82f6]/10",
  marginal: "text-[#f59e0b] bg-[#f59e0b]/10",
  poor: "text-[#ef4444] bg-[#ef4444]/10",
};

const FLAG_LABELS: Record<string, string> = {
  too_easy: "太简单", too_hard: "太难", low_disc: "区分度低",
  ambiguous: "有歧义", dead_distractor: "无效干扰项", high_guess: "猜测率高",
};

export default function QualityPage() {
  const [summary, setSummary] = useState<QualitySummaryData | null>(null);
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState("");
  const [error, setError] = useState("");

  const loadSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/practice/quality`);
      if (res.ok) setSummary(await res.json());
    } catch (e) {
      setError("加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  const loadDetail = async (qid: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/practice/quality/${qid}`);
      if (res.ok) setDetail(await res.json());
    } finally {
      setDetailLoading(false);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    try {
      const res = await fetch(`${API_BASE}/api/practice/quality/apply?dry_run=false`, {
        method: "POST",
      });
      const data = await res.json();
      setApplyResult(data.message || "操作完成");
      await loadSummary();
    } catch {
      setApplyResult("操作失败");
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[var(--color-text)] tracking-tight">
              题库质量
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              基于 IRT 模型分析题目质量
            </p>
          </div>
          <button
            onClick={handleApply}
            disabled={applying || !summary || summary.poor === 0}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[#ef4444] text-white hover:opacity-90 disabled:opacity-30 transition-opacity"
          >
            {applying ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            淘汰差题
          </button>
        </div>

        {applyResult && (
          <div className="mb-6 px-4 py-2.5 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]">
            {applyResult}
          </div>
        )}

        {!summary ? (
          <EmptyState />
        ) : (
          <>
            {/* ── Distribution bar ── */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">
                  质量分布 · 综合评分 {(summary.avg_quality * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {summary.analyzed}/{summary.total_questions} 已分析
                </span>
              </div>
              <div className="h-3 flex overflow-hidden">
                {summary.excellent > 0 && (
                  <div
                    className="bg-[#10b981]"
                    style={{ width: `${(summary.excellent / Math.max(summary.analyzed, 1)) * 100}%` }}
                    title={`优秀: ${summary.excellent}`}
                  />
                )}
                {summary.good > 0 && (
                  <div
                    className="bg-[#3b82f6]"
                    style={{ width: `${(summary.good / Math.max(summary.analyzed, 1)) * 100}%` }}
                    title={`良好: ${summary.good}`}
                  />
                )}
                {summary.marginal > 0 && (
                  <div
                    className="bg-[#f59e0b]"
                    style={{ width: `${(summary.marginal / Math.max(summary.analyzed, 1)) * 100}%` }}
                    title={`一般: ${summary.marginal}`}
                  />
                )}
                {summary.poor > 0 && (
                  <div
                    className="bg-[#ef4444]"
                    style={{ width: `${(summary.poor / Math.max(summary.analyzed, 1)) * 100}%` }}
                    title={`差: ${summary.poor}`}
                  />
                )}
              </div>
              <div className="flex gap-4 mt-2 text-[10px] text-[var(--color-text-muted)]">
                <span>🟢 优秀 {summary.excellent}</span>
                <span>🔵 良好 {summary.good}</span>
                <span>🟡 一般 {summary.marginal}</span>
                <span>🔴 待淘汰 {summary.poor}</span>
                {summary.flagged > 0 && <span>🚩 已标记 {summary.flagged}</span>}
              </div>
            </div>

            {/* ── Two-column layout ── */}
            <div className="grid lg:grid-cols-5 gap-6">
              {/* Left: Worst questions */}
              <div className="lg:col-span-2">
                <h2 className="text-sm font-semibold text-[var(--color-text)] uppercase tracking-wider mb-4 flex items-center gap-2">
                  <AlertTriangle size={14} className="text-[#ef4444]" />
                  问题题目
                </h2>
                <div className="space-y-2">
                  {summary.worst_questions.map((q) => (
                    <button
                      key={q.question_id}
                      onClick={() => loadDetail(q.question_id)}
                      className={`w-full text-left px-3 py-2.5 border transition-colors ${
                        detail?.question_id === q.question_id
                          ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5"
                          : "border-[var(--color-border)] hover:border-[var(--color-border-hover)]"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-mono text-[var(--color-text-muted)] truncate max-w-[70%]">
                          {q.question_id.slice(0, 16)}
                        </span>
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 ${GRADE_COLORS[q.quality_grade] || ""}`}>
                          {q.quality_score.toFixed(2)}
                        </span>
                      </div>
                      <p className="text-xs text-[var(--color-text)] line-clamp-2">
                        {q.text || "(无文本)"}
                      </p>
                      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-[var(--color-text-muted)]">
                        <span>答题 {q.total_attempts}次</span>
                        <span>正确率 {(q.correct_rate * 100).toFixed(0)}%</span>
                        {q.flags.map((f) => (
                          <span key={f} className="text-[#ef4444]">{FLAG_LABELS[f] || f}</span>
                        ))}
                      </div>
                    </button>
                  ))}
                  {summary.worst_questions.length === 0 && (
                    <p className="text-xs text-[var(--color-text-muted)] py-4">
                      🎉 没有需要关注的问题题目
                    </p>
                  )}
                </div>
              </div>

              {/* Right: Detail panel */}
              <div className="lg:col-span-3">
                {detailLoading ? (
                  <div className="flex items-center justify-center py-16">
                    <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
                  </div>
                ) : detail ? (
                  <QuestionDetailPanel detail={detail} />
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center border border-[var(--color-border)]">
                    <BarChart3 size={32} className="text-[var(--color-text-muted)] mb-3" />
                    <p className="text-sm text-[var(--color-text-muted)]">点击左侧题目查看详细分析</p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ── Detail Panel ──
function QuestionDetailPanel({ detail }: { detail: QuestionDetail }) {
  return (
    <div className="border border-[var(--color-border)]">
      <div className="px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
            {detail.question_id}
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 ${GRADE_COLORS[detail.quality_grade] || ""}`}>
            {detail.quality_grade.toUpperCase()} · {detail.quality_score.toFixed(2)}
          </span>
        </div>
        <p className="text-sm text-[var(--color-text)] leading-relaxed">{detail.text}</p>
        <div className="flex items-center gap-3 mt-2 text-[10px] text-[var(--color-text-muted)]">
          <span>{detail.subject}</span>
          <span>·</span>
          <span>{detail.skill_id}</span>
        </div>
      </div>

      {/* IRT metrics */}
      <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric label="难度" value={detail.difficulty.toFixed(2)} hint="0=易 1=难" />
        <Metric label="区分度" value={detail.discrimination.toFixed(2)} hint=">0.3=好" />
        <Metric label="猜测率" value={detail.guess_rate.toFixed(2)} hint="<0.2=正常" />
        <Metric label="质量分" value={detail.quality_score.toFixed(2)} hint=">0.7=优秀" />
      </div>

      {/* Stats */}
      <div className="px-4 py-2 border-t border-[var(--color-border)] grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] text-[var(--color-text-muted)]">
        <span>答题 {detail.total_attempts}次</span>
        <span>正确率 {(detail.correct_rate * 100).toFixed(0)}%</span>
        <span>平均 {detail.avg_time_seconds.toFixed(0)}秒</span>
        <span>状态: {detail.current_status}</span>
      </div>

      {/* Flags */}
      {detail.flags.length > 0 && (
        <div className="px-4 py-2 border-t border-[var(--color-border)] flex flex-wrap gap-1.5">
          {detail.flags.map((f) => (
            <span key={f} className="text-[10px] px-1.5 py-0.5 bg-[#ef4444]/10 text-[#ef4444]">
              {FLAG_LABELS[f] || f}
            </span>
          ))}
        </div>
      )}

      {/* Distractors */}
      {detail.distractors.length > 0 && (
        <div className="border-t border-[var(--color-border)]">
          <div className="px-4 py-2 text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
            干扰项分析
          </div>
          <div className="px-4 pb-3 space-y-1.5">
            {detail.distractors.map((d) => (
              <div
                key={d.letter}
                className={`flex items-center gap-3 px-2 py-1.5 text-xs ${
                  d.is_correct
                    ? "bg-[#10b981]/10 border-l-2 border-[#10b981]"
                    : ""
                }`}
              >
                <span className={`font-bold w-5 text-center ${d.is_correct ? "text-[#10b981]" : "text-[var(--color-text-muted)]"}`}>
                  {d.letter}
                </span>
                <span className="flex-1 truncate text-[var(--color-text)]">{d.text}</span>
                <span className="text-[var(--color-text-muted)]">{d.count}次</span>
                <span className="text-[var(--color-text-muted)]">{(d.rate * 100).toFixed(0)}%</span>
                <span className={`text-[10px] ${
                  d.quality === "dead" ? "text-[#ef4444]" : "text-[var(--color-text-muted)]"
                }`}>
                  {d.quality === "excellent" ? "优秀" : d.quality === "good" ? "良好" : d.quality === "marginal" ? "一般" : "无效"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action */}
      {detail.status_action && (
        <div className="px-4 py-2.5 border-t border-[var(--color-border)] text-[10px] text-[var(--color-text-muted)]">
          建议: {detail.status_action === "retire" ? "🔴 建议淘汰" : detail.status_action === "flag" ? "🟡 建议标记" : "🟢 保持"}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-0.5">{label}</div>
      <div className="text-lg font-bold text-[var(--color-text)]">{value}</div>
      <div className="text-[10px] text-[var(--color-text-muted)]">{hint}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-16">
      <div className="w-16 h-16 mx-auto mb-4 border border-[var(--color-border)] flex items-center justify-center">
        <Shield size={28} className="text-[var(--color-text-muted)]" />
      </div>
      <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">
        尚无质量数据
      </h2>
      <p className="text-sm text-[var(--color-text-muted)] max-w-sm mx-auto">
        每题需要至少 {5} 次答题记录才能进行分析。多做一些练习后回来查看。
      </p>
    </div>
  );
}
