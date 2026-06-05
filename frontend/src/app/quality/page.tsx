"use client";

/**
 * 题库质量分析页面 —— 基于 IRT 模型分析每道题目的质量指标，
 * 包括难度、区分度、猜测率等，并支持淘汰差题操作。
 */
import { useState, useEffect, useCallback } from "react";
import {
  Shield, AlertTriangle, CheckCircle, XCircle, Loader2,
  ChevronDown, ChevronUp, Trash2, Zap, BarChart3,
} from "lucide-react";
import { API_BASE } from "@/lib/api/api";

/**
 * 质量分析摘要 —— 包含题目总数、各等级数量、平均分及最差题目列表
 */
interface QualitySummaryData {
  total_questions: number;   // 题目总数
  analyzed: number;          // 已分析的题目数
  excellent: number;         // 优秀
  good: number;              // 良好
  marginal: number;          // 一般
  poor: number;              // 差（待淘汰）
  flagged: number;           // 已标记
  retired: number;           // 已淘汰
  avg_quality: number;       // 平均质量分（0~1）
  worst_questions: QuestionPreview[];  // 质量最差的题目列表
}

/** 题目预览（列表展示用） */
interface QuestionPreview {
  question_id: string;       // 题目 ID
  text: string;              // 题目文本
  quality_score: number;     // 质量评分（0~1）
  quality_grade: string;     // 质量等级：excellent/good/marginal/poor
  correct_rate: number;      // 正确率
  total_attempts: number;    // 答题总次数
  flags: string[];           // 质量标志列表（如 too_easy, low_disc 等）
  status_action: string;     // 建议操作：retire/flag/keep
}

/** 题目详情 —— 完整的 IRT 分析结果 */
interface QuestionDetail {
  question_id: string;       // 题目 ID
  text: string;              // 题目文本
  skill_id: string;          // 关联技能 ID
  subject: string;           // 科目
  total_attempts: number;    // 总答题次数
  correct_count: number;     // 正确次数
  correct_rate: number;      // 正确率
  avg_time_seconds: number;  // 平均答题时长（秒）
  difficulty: number;        // IRT 难度参数（0=易, 1=难）
  discrimination: number;    // 区分度参数（>0.3 为良好）
  guess_rate: number;        // 猜测率参数（<0.2 为正常）
  quality_score: number;     // 综合质量评分（0~1）
  quality_grade: string;     // 质量等级
  flags: string[];           // 问题标志列表
  distractors: Distractor[]; // 干扰项分析
  time_fast_ratio: number;   // 快速作答比例
  time_slow_ratio: number;   // 慢速作答比例
  current_status: string;    // 当前状态：active/flagged/retired
  status_action: string;     // 建议操作
}

/** 干扰项分析数据 */
interface Distractor {
  letter: string;            // 选项字母（A/B/C/D）
  text: string;              // 选项文本
  count: number;             // 选择次数
  rate: number;              // 选择率
  quality: string;           // 干扰项质量：excellent/good/marginal/dead
  is_correct: boolean;       // 是否为正确答案
}

/** 质量等级对应的颜色样式（Tailwind 类名） */
const GRADE_COLORS: Record<string, string> = {
  excellent: "text-[#10b981] bg-[#10b981]/10",   // 优秀 - 绿色
  good: "text-[#3b82f6] bg-[#3b82f6]/10",        // 良好 - 蓝色
  marginal: "text-[#f59e0b] bg-[#f59e0b]/10",    // 一般 - 黄色
  poor: "text-[#ef4444] bg-[#ef4444]/10",         // 差   - 红色
};

/** 质量标志的中文标签映射 */
const FLAG_LABELS: Record<string, string> = {
  too_easy: "太简单", too_hard: "太难", low_disc: "区分度低",
  ambiguous: "有歧义", dead_distractor: "无效干扰项", high_guess: "猜测率高",
};

/**
 * 题库质量分析页面主组件
 * 展示题目的质量分布、最差题目列表、以及选中题目的详细分析面板。
 */
export default function QualityPage() {
  // ── 状态管理 ──
  const [summary, setSummary] = useState<QualitySummaryData | null>(null);  // 摘要数据
  const [detail, setDetail] = useState<QuestionDetail | null>(null);        // 当前选中的题目详情
  const [loading, setLoading] = useState(true);       // 页面初次加载中
  const [detailLoading, setDetailLoading] = useState(false);  // 详情加载中
  const [applying, setApplying] = useState(false);    // 淘汰操作进行中
  const [applyResult, setApplyResult] = useState(""); // 淘汰操作的结果消息
  const [error, setError] = useState("");             // 错误信息

  /** 从后端加载质量分析摘要数据 */
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

  // 页面初始化时加载摘要
  useEffect(() => { loadSummary(); }, [loadSummary]);

  /** 加载指定题目的详细 IRT 分析数据 */
  const loadDetail = async (qid: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/practice/quality/detail/${qid}`);
      if (res.ok) setDetail(await res.json());
    } finally {
      setDetailLoading(false);
    }
  };

  /** 执行差题淘汰操作（POST 请求） */
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

  // 页面加载中 —— 显示加载动画
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
        {/* ── 页面标题栏 ── */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight">
              题库质量
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              基于 IRT 模型分析题目质量
            </p>
          </div>
          {/* 淘汰差题按钮：仅在有差题时才可点击 */}
          <button
            onClick={handleApply}
            disabled={applying || !summary || summary.poor === 0}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[#ef4444] text-white hover:opacity-90 disabled:opacity-30 transition-opacity"
          >
            {applying ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            淘汰差题
          </button>
        </div>

        {/* 操作结果消息提示 */}
        {applyResult && (
          <div className="mb-6 px-4 py-2.5 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)]">
            {applyResult}
          </div>
        )}

        {!summary ? (
          <EmptyState />
        ) : (
          <>
            {/* ── 质量分布条形图 ── */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider">
                  质量分布 · 综合评分 {(summary.avg_quality * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {summary.analyzed}/{summary.total_questions} 已分析
                </span>
              </div>
              {/* 横向条状图：按优秀/良好/一般/差 四段比例展示 */}
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
              {/* 图例 */}
              <div className="flex gap-4 mt-2 text-[10px] text-[var(--color-text-muted)]">
                <span>🟢 优秀 {summary.excellent}</span>
                <span>🔵 良好 {summary.good}</span>
                <span>🟡 一般 {summary.marginal}</span>
                <span>🔴 待淘汰 {summary.poor}</span>
                {summary.flagged > 0 && <span>🚩 已标记 {summary.flagged}</span>}
              </div>
            </div>

            {/* ── 双栏布局：左栏展示问题题目列表，右栏展示详细分析 ── */}
            <div className="grid lg:grid-cols-5 gap-6">
              {/* 左栏：质量最差的题目列表 */}
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

              {/* 右栏：题目的详细 IRT 分析面板 */}
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

// ── 题目详情面板 ──

/**
 * 题目详情面板组件
 * 展示选中题目的完整 IRT 分析结果，包括 IRT 指标、统计数据、
 * 质量标志、干扰项分析和建议操作。
 */
function QuestionDetailPanel({ detail }: { detail: QuestionDetail }) {
  return (
    <div className="border border-[var(--color-border)]">
      {/* 题目头部：ID、等级评分、题目文本、科目与技能 */}
      <div className="px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
            {detail.question_id}
          </span>
          <span className={`text-[10px] font-semibold px-2 py-0.5 ${GRADE_COLORS[detail.quality_grade] || ""}`}>
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

      {/* IRT 指标：难度、区分度、猜测率、质量分 */}
      <div className="px-4 py-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Metric label="难度" value={detail.difficulty.toFixed(2)} hint="0=易 1=难" />
        <Metric label="区分度" value={detail.discrimination.toFixed(2)} hint=">0.3=好" />
        <Metric label="猜测率" value={detail.guess_rate.toFixed(2)} hint="<0.2=正常" />
        <Metric label="质量分" value={detail.quality_score.toFixed(2)} hint=">0.7=优秀" />
      </div>

      {/* 基本统计：答题次数、正确率、平均时长、当前状态 */}
      <div className="px-4 py-2 border-t border-[var(--color-border)] grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] text-[var(--color-text-muted)]">
        <span>答题 {detail.total_attempts}次</span>
        <span>正确率 {(detail.correct_rate * 100).toFixed(0)}%</span>
        <span>平均 {detail.avg_time_seconds.toFixed(0)}秒</span>
        <span>状态: {detail.current_status}</span>
      </div>

      {/* 问题标志列表 */}
      {detail.flags.length > 0 && (
        <div className="px-4 py-2 border-t border-[var(--color-border)] flex flex-wrap gap-1.5">
          {detail.flags.map((f) => (
            <span key={f} className="text-[10px] px-1.5 py-0.5 bg-[#ef4444]/10 text-[#ef4444]">
              {FLAG_LABELS[f] || f}
            </span>
          ))}
        </div>
      )}

      {/* 干扰项分析 */}
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
                <span className={`font-semibold w-5 text-center ${d.is_correct ? "text-[#10b981]" : "text-[var(--color-text-muted)]"}`}>
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

      {/* 建议操作 */}
      {detail.status_action && (
        <div className="px-4 py-2.5 border-t border-[var(--color-border)] text-[10px] text-[var(--color-text-muted)]">
          建议: {detail.status_action === "retire" ? "🔴 建议淘汰" : detail.status_action === "flag" ? "🟡 建议标记" : "🟢 保持"}
        </div>
      )}
    </div>
  );
}

/**
 * 指标展示组件
 * 显示单个 IRT 指标的数值、标签和参考值提示。
 */
function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <div className="text-[10px] text-[var(--color-text-muted)] uppercase mb-0.5">{label}</div>
      <div className="text-lg font-semibold text-[var(--color-text)]">{value}</div>
      <div className="text-[10px] text-[var(--color-text-muted)]">{hint}</div>
    </div>
  );
}

/** 无数据时的空状态提示组件 */
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
