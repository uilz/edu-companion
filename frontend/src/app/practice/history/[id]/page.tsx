"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Clock, Check, X, ChevronLeft, ChevronRight,
  Trash2, RotateCcw, FileText,
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api/api";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import QuestionStem from "@/components/practice/components/QuestionStem";

export default function SessionReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [currentQ, setCurrentQ] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    api<any>(`/api/practice/sessions/${id}/result`)
      .then(data => {
        if (Array.isArray(data.detail)) setResult(data);
        else setError(data.message || "无法加载结果");
      })
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, [id]);

  const handleDelete = async () => {
    if (!confirm("确认删除此练习记录？")) return;
    await api(`/api/practice/sessions/${id}`, { method: "DELETE" });
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
    return <PageSkeleton />;
  }

  if (error) {
    return (
      <div className="min-h-screen bg-page px-4 py-6 max-w-3xl mx-auto">
        <button onClick={() => router.back()}
          className="text-[11px] text-muted hover:text mb-4 flex items-center gap-1">
          <ChevronLeft size={12} /> 返回
        </button>
        <div className="text-center py-12">
          <p className="text-[13px] text-muted">{error}</p>
        </div>
      </div>
    );
  }

  const q = result.detail?.[currentQ];

  return (
    <div className="min-h-screen bg-page">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-page/90 backdrop-blur-sm border-b border/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12 gap-3">
          <button onClick={() => router.back()}
            className="text-[11px] text-muted hover:text transition-colors flex items-center gap-1">
            <ChevronLeft size={12} /> 返回
          </button>
          <span className="text-[11px] text-muted">|</span>
          <span className="text-[12px] font-medium text">练习回顾</span>
          <button onClick={handleDelete}
            className="ml-auto p-1.5 rounded-lg text-muted hover:text-danger hover:bg-danger/10 transition-colors"
            title="删除记录">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-4 space-y-4">
        {/* ── 摘要区 ── */}
        <div className="p-4 rounded-xl bg-surface border border/50">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h2 className="text-[15px] font-bold text">
                {result.bank_name || "练习回顾"}
              </h2>
              <p className="text-[10px] text-muted mt-0.5">
                {result.mode === "exam" ? "模拟考试" : result.mode === "review" ? "复习" : "自适应练习"}
                {result.bank_id && <> · {result.bank_name}</>}
              </p>
            </div>
            <div className="text-center">
              <p className={`text-2xl font-bold ${result.score >= 80 ? "text-success" : result.score >= 60 ? "text-warning" : "text-danger"}`}>
                {result.score ?? "—"}
              </p>
              <p className="text-[9px] text-muted">分</p>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3">
            <div className="text-center">
              <p className="text-[18px] font-bold text">{result.total}</p>
              <p className="text-[9px] text-muted">总题数</p>
            </div>
            <div className="text-center">
              <p className="text-[18px] font-bold text-success">{result.correct}</p>
              <p className="text-[9px] text-muted">正确</p>
            </div>
            <div className="text-center">
              <p className="text-[18px] font-bold text-danger">{result.wrong}</p>
              <p className="text-[9px] text-muted">错误</p>
            </div>
            <div className="text-center">
              <p className="text-[18px] font-bold text">{fmtDuration(result.duration_seconds)}</p>
              <p className="text-[9px] text-muted">用时</p>
            </div>
          </div>

          <div className="flex items-center gap-2 mt-3 text-[10px] text-muted">
            <Clock size={10} />
            <span>{fmtDate(result.started_at)} — {fmtDate(result.finished_at)}</span>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 mt-3">
            {result.bank_id && (
              <button onClick={handleRetry}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-accent/10 text-accent text-[10px] font-medium hover:bg-accent/20 transition-colors">
                <RotateCcw size={12} />
                重新练习
              </button>
            )}
            <button onClick={() => router.push("/practice/errors")}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-warning/10 text-warning text-[10px] font-medium hover:bg-warning/20 transition-colors">
              <FileText size={12} />
              查看错题
            </button>
          </div>
        </div>

        {/* ── 进度条 ── */}
        <div className="w-full h-1.5 rounded-full bg-divider/30 overflow-hidden">
          <div className="h-full rounded-full transition-all duration-300 flex">
            <div className="h-full bg-success" style={{ width: `${(result.correct / Math.max(result.total, 1)) * 100}%` }} />
            <div className="h-full bg-danger" style={{ width: `${(result.wrong / Math.max(result.total, 1)) * 100}%` }} />
          </div>
        </div>

        {/* ── 题目列表 ── */}
        <div className="space-y-2">
          {result.detail.map((d: any, i: number) => (
            <button key={i} onClick={() => setCurrentQ(i)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${
                currentQ === i
                  ? "bg-accent/5 border-accent/30"
                  : "bg-surface border/50 hover:border-accent/20"
              }`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                d.is_correct === true ? "bg-success/10" :
                d.is_correct === false ? "bg-danger/10" : "bg-page"
              }`}>
                {d.is_correct === true ? <Check size={14} className="text-success" /> :
                 d.is_correct === false ? <X size={14} className="text-danger" /> :
                 <span className="text-[10px] text-muted">{d.index + 1}</span>}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[11px] text line-clamp-1">
                  <QuestionStem stem={d.stem || `题目 ${d.index + 1}`} />
                </div>
                <p className="text-[9px] text-muted mt-0.5">
                  {d.difficulty ? `难度 ${d.difficulty}` : ""}
                  {d.time_spent ? ` · ${d.time_spent}秒` : ""}
                  {d.question_type ? ` · ${d.question_type}` : ""}
                </p>
              </div>
              <ChevronRight size={12} className="text-muted" />
            </button>
          ))}
        </div>

        {/* ── 当前题目详情 ── */}
        {q && (
          <div className="p-4 rounded-xl bg-surface border border/50 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[13px] font-bold text">
                第 {q.index + 1} 题
              </h3>
              <div className="flex items-center gap-2">
                {currentQ > 0 && (
                  <button onClick={() => setCurrentQ(currentQ - 1)}
                    className="p-1.5 rounded-lg bg-page text-muted hover:text">
                    <ChevronLeft size={14} />
                  </button>
                )}
                {currentQ < result.detail.length - 1 && (
                  <button onClick={() => setCurrentQ(currentQ + 1)}
                    className="p-1.5 rounded-lg bg-page text-muted hover:text">
                    <ChevronRight size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* 题干 */}
          <div className="text-[12px] text leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
            <QuestionStem stem={q.stem} />
          </div>

            {/* 选项（选择题） */}
            {q.options?.length > 0 && (
              <div className="space-y-1.5">
                {q.options.map((opt: any, oi: number) => {
                  const isUserAnswer = q.user_answer?.includes(opt.letter);
                  const isCorrectAnswer = q.correct_answer?.includes(opt.letter);
                  return (
                    <div key={oi} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] ${
                      isUserAnswer && isCorrectAnswer ? "bg-success/10 text-success" :
                      isUserAnswer && !isCorrectAnswer ? "bg-danger/10 text-danger" :
                      !isUserAnswer && isCorrectAnswer ? "bg-success/5 text-success" :
                      "bg-page text"
                    }`}>
                      <span className="font-bold w-5">{opt.letter}</span>
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                        {opt.text}
                      </ReactMarkdown>
                      {isUserAnswer && <span className="ml-auto text-[9px]">你的选择</span>}
                      {isCorrectAnswer && !isUserAnswer && <Check size={10} className="ml-auto text-success" />}
                    </div>
                  );
                })}
              </div>
            )}

            {/* 答案和解析 */}
            <div className="pt-2 border-t border/30 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-muted">你的答案：</span>
                <span className={`text-[11px] font-medium ${q.is_correct ? "text-success" : "text-danger"}`}>
                  {q.user_answer ? (Array.isArray(q.user_answer) ? q.user_answer.join(", ") : String(q.user_answer)) : "未作答"}
                </span>
                {q.is_correct ? <Check size={12} className="text-success" /> : <X size={12} className="text-danger" />}
              </div>
              {!q.is_correct && q.correct_answer && (
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted">正确答案：</span>
                  <span className="text-[11px] font-medium text-success">
                    {Array.isArray(q.correct_answer) ? q.correct_answer.join(", ") : String(q.correct_answer)}
                  </span>
                </div>
              )}
              <div className="flex items-center gap-2 text-[10px] text-muted">
                <Clock size={10} />
                <span>用时 {q.time_spent}秒</span>
                {q.hints_used > 0 && <span>· 提示 {q.hints_used}次</span>}
                <span>· 难度 {q.difficulty}</span>
              </div>
              {q.explanation && (
                <div className="mt-2 p-3 rounded-lg bg-info/5 border border-info/10">
                  <p className="text-[10px] text-info font-medium mb-1">解析</p>
                  <div className="text-[11px] text leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
                    <QuestionStem stem={q.explanation} />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
