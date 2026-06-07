"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Clock, Check, X, ChevronLeft, ChevronRight,
  Trash2, Loader2, RotateCcw, FileText,
} from "lucide-react";

const API = "/api/v7/practice";

export default function SessionReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [currentQ, setCurrentQ] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/sessions/${id}/result`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (Array.isArray(data.detail)) setResult(data);
        else setError(data.message || "无法加载结果");
      })
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleDelete = async () => {
    if (!confirm("确认删除此练习记录？")) return;
    await fetch(`${API}/sessions/${id}`, { method: "DELETE" });
    router.push("/practice/history");
  };

  const handleRetry = () => {
    if (result?.bank_id) {
      router.push(`/practice?bank_id=${result.bank_id}`);
    }
  };

  const fmtDuration = (sec: number | null) => {
    if (!sec) return "—";
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m > 0 ? `${m}分${s}秒` : `${s}秒`;
  };

  const fmtDate = (iso: string | null) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] px-4 py-6 max-w-3xl mx-auto">
        <button onClick={() => router.back()}
          className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] mb-4 flex items-center gap-1">
          <ChevronLeft size={12} /> 返回
        </button>
        <div className="text-center py-12">
          <p className="text-[13px] text-[var(--color-text-muted)]">{error}</p>
        </div>
      </div>
    );
  }

  const q = result.detail?.[currentQ];

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-[var(--color-bg)]/90 backdrop-blur-sm border-b border-[var(--color-border)]/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
          <button onClick={() => router.back()}
            className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors flex items-center gap-1">
            <ChevronLeft size={12} /> 返回
          </button>
          <span className="text-[11px] text-[var(--color-text-muted)]">|</span>
          <span className="text-[12px] font-medium text-[var(--color-text)]">练习回顾</span>
          <button onClick={handleDelete}
            className="ml-auto p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
            title="删除记录">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-4 space-y-4">
        {/* ── 摘要区 ── */}
        <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h2 className="text-[15px] font-bold text-[var(--color-text)]">
                {result.bank_name || "练习回顾"}
              </h2>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                {result.mode === "exam" ? "模拟考试" : result.mode === "review" ? "复习" : "自适应练习"}
                {result.bank_id && <> · {result.bank_name}</>}
              </p>
            </div>
            <div className="text-center">
              <p className={`text-2xl font-bold ${result.score >= 80 ? "text-green-500" : result.score >= 60 ? "text-yellow-500" : "text-red-500"}`}>
                {result.score ?? "—"}
              </p>
              <p className="text-[9px] text-[var(--color-text-muted)]">分</p>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3">
            <div className="text-center">
              <p className="text-[18px] font-bold text-[var(--color-text)]">{result.total}</p>
              <p className="text-[9px] text-[var(--color-text-muted)]">总题数</p>
            </div>
            <div className="text-center">
              <p className="text-[18px] font-bold text-green-500">{result.correct}</p>
              <p className="text-[9px] text-[var(--color-text-muted)]">正确</p>
            </div>
            <div className="text-center">
              <p className="text-[18px] font-bold text-red-500">{result.wrong}</p>
              <p className="text-[9px] text-[var(--color-text-muted)]">错误</p>
            </div>
            <div className="text-center">
              <p className="text-[18px] font-bold text-[var(--color-text)]">{fmtDuration(result.duration_seconds)}</p>
              <p className="text-[9px] text-[var(--color-text-muted)]">用时</p>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-3 text-[10px] text-[var(--color-text-muted)]">
            <Clock size={10} />
            <span>{fmtDate(result.started_at)} — {fmtDate(result.finished_at)}</span>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 mt-3">
            {result.bank_id && (
              <button onClick={handleRetry}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] text-[10px] font-medium hover:bg-[var(--color-accent)]/20 transition-colors">
                <RotateCcw size={12} />
                重新练习
              </button>
            )}
            <button onClick={() => router.push("/errors")}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-orange-500/10 text-orange-600 text-[10px] font-medium hover:bg-orange-500/20 transition-colors">
              <FileText size={12} />
              查看错题
            </button>
          </div>
        </div>

        {/* ── 进度条 ── */}
        <div className="w-full h-1.5 rounded-full bg-[var(--color-border)]/30 overflow-hidden">
          <div className="h-full rounded-full transition-all duration-300 flex">
            <div className="h-full bg-green-500" style={{ width: `${(result.correct / Math.max(result.total, 1)) * 100}%` }} />
            <div className="h-full bg-red-500" style={{ width: `${(result.wrong / Math.max(result.total, 1)) * 100}%` }} />
          </div>
        </div>

        {/* ── 题目列表 ── */}
        <div className="space-y-2">
          {result.detail.map((d: any, i: number) => (
            <button key={i} onClick={() => setCurrentQ(i)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
                currentQ === i
                  ? "bg-[var(--color-accent)]/5 border-[var(--color-accent)]/30"
                  : "bg-[var(--color-surface)] border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/20"
              }`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                d.is_correct === true ? "bg-green-500/10" :
                d.is_correct === false ? "bg-red-500/10" : "bg-[var(--color-bg)]"
              }`}>
                {d.is_correct === true ? <Check size={14} className="text-green-500" /> :
                 d.is_correct === false ? <X size={14} className="text-red-500" /> :
                 <span className="text-[10px] text-[var(--color-text-muted)]">{d.index + 1}</span>}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] text-[var(--color-text)] truncate">
                  {d.stem || `题目 ${d.index + 1}`}
                </p>
                <p className="text-[9px] text-[var(--color-text-muted)] mt-0.5">
                  {d.difficulty ? `难度 ${d.difficulty}` : ""}
                  {d.time_spent ? ` · ${d.time_spent}秒` : ""}
                  {d.question_type ? ` · ${d.question_type}` : ""}
                </p>
              </div>
              <ChevronRight size={12} className="text-[var(--color-text-muted)]" />
            </button>
          ))}
        </div>

        {/* ── 当前题目详情 ── */}
        {q && (
          <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[13px] font-bold text-[var(--color-text)]">
                第 {q.index + 1} 题
              </h3>
              <div className="flex items-center gap-2">
                {currentQ > 0 && (
                  <button onClick={() => setCurrentQ(currentQ - 1)}
                    className="p-1.5 rounded-lg bg-[var(--color-bg)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                    <ChevronLeft size={14} />
                  </button>
                )}
                {currentQ < result.detail.length - 1 && (
                  <button onClick={() => setCurrentQ(currentQ + 1)}
                    className="p-1.5 rounded-lg bg-[var(--color-bg)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                    <ChevronRight size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* 题干 */}
            <p className="text-[12px] text-[var(--color-text)] leading-relaxed whitespace-pre-wrap">
              {q.stem}
            </p>

            {/* 选项（选择题） */}
            {q.options?.length > 0 && (
              <div className="space-y-1.5">
                {q.options.map((opt: any, oi: number) => {
                  const isUserAnswer = q.user_answer?.includes(opt.letter);
                  const isCorrectAnswer = q.correct_answer?.includes(opt.letter);
                  return (
                    <div key={oi} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] ${
                      isUserAnswer && isCorrectAnswer ? "bg-green-500/10 text-green-700" :
                      isUserAnswer && !isCorrectAnswer ? "bg-red-500/10 text-red-700" :
                      !isUserAnswer && isCorrectAnswer ? "bg-green-500/5 text-green-600" :
                      "bg-[var(--color-bg)] text-[var(--color-text)]"
                    }`}>
                      <span className="font-bold w-5">{opt.letter}</span>
                      <span>{opt.text}</span>
                      {isUserAnswer && <span className="ml-auto text-[9px]">你的选择</span>}
                      {isCorrectAnswer && !isUserAnswer && <Check size={10} className="ml-auto text-green-500" />}
                    </div>
                  );
                })}
              </div>
            )}

            {/* 答案和解析 */}
            <div className="pt-2 border-t border-[var(--color-border)]/30 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--color-text-muted)]">你的答案：</span>
                <span className={`text-[11px] font-medium ${q.is_correct ? "text-green-500" : "text-red-500"}`}>
                  {q.user_answer ? (Array.isArray(q.user_answer) ? q.user_answer.join(", ") : String(q.user_answer)) : "未作答"}
                </span>
                {q.is_correct ? <Check size={12} className="text-green-500" /> : <X size={12} className="text-red-500" />}
              </div>
              {!q.is_correct && q.correct_answer && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[var(--color-text-muted)]">正确答案：</span>
                  <span className="text-[11px] font-medium text-green-500">
                    {Array.isArray(q.correct_answer) ? q.correct_answer.join(", ") : String(q.correct_answer)}
                  </span>
                </div>
              )}
              <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
                <Clock size={10} />
                <span>用时 {q.time_spent}秒</span>
                {q.hints_used > 0 && <span>· 提示 {q.hints_used}次</span>}
                <span>· 难度 {q.difficulty}</span>
              </div>
              {q.explanation && (
                <div className="mt-2 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10">
                  <p className="text-[10px] text-blue-600 font-medium mb-1">解析</p>
                  <p className="text-[11px] text-[var(--color-text)] leading-relaxed">{q.explanation}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
