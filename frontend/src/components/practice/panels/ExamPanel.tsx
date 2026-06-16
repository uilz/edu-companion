"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import {
  Clock, AlertTriangle, Check, X, ChevronRight, ChevronLeft,
  FileText, Send, Loader2, Trophy, Brain, BookOpen,
  BarChart3, Grid3X3,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import {
  createExam, listBanks,
  getExamTime,
  submitAllExam,
  getExamAnswerSheet,
  submitExamAnswer,
  type ExamQuestion,
  type ExamResult,
  type ExamTimeInfo,
} from "@/lib/api/practice-api";
import QuestionStem from "@/components/practice/components/QuestionStem";

type Phase = "setup" | "answering" | "submitting" | "result";

const OPTION_TYPES = ["single", "multiple", "judge", "choice"];

interface Props {
  bankId: string;
  bankName?: string;
  nodeId?: string;
  nodeLabel?: string;
  onClose?: () => void;
}

export default function ExamPanel({ bankId, bankName, nodeId, nodeLabel, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("setup");
  const [duration, setDuration] = useState(30);
  const [count, setCount] = useState(20);
  const [session, setSession] = useState<any>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<string[]>([]);
  const [savedAnswers, setSavedAnswers] = useState<Record<string, string[]>>({});
  const [fillAnswer, setFillAnswer] = useState("");
  const [showAnswerSheet, setShowAnswerSheet] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [examResult, setExamResult] = useState<ExamResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [banks, setBanks] = useState<{ id: string; name: string }[]>([]);
  const [selectedBankId, setSelectedBankId] = useState(bankId || "");
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const startedRef = useRef(false);

  const currentQuestion = questions[currentIdx] ?? null;

  // 加载题库列表
  useEffect(() => {
    if (phase !== "setup") return;
    listBanks().then(items => {
      const raw = Array.isArray(items) ? items : (items as any)?.items || [];
      const list = raw.map((b: any) => ({ id: b.id, name: b.name }));
      setBanks(list);
      if (!selectedBankId && list.length > 0) setSelectedBankId(list[0].id);
    }).catch(() => {});
  }, [phase, selectedBankId]);

  // ── 创建考试 ──
  const handleStart = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const bid = selectedBankId || bankId;
      const exam = await createExam(bid, {
        count,
        duration_minutes: duration,
        cognitive_node_ids: nodeId ? [nodeId] : undefined,
      });
      setSession(exam);
      setQuestions(exam.questions || []);
      setPhase("answering");
      setCurrentIdx(0);
      setSelectedAnswers([]);
      setTimeLeft(duration * 60);
      startedRef.current = true;
    } catch (e: any) {
      setError(e?.message || "创建考试失败");
      setPhase("setup");
    } finally {
      setLoading(false);
    }
  }, [selectedBankId, bankId, count, duration, nodeId]);

  // ── 计时器 ──
  useEffect(() => {
    if (phase !== "answering" || !session) return;
    if (timerRef.current) clearInterval(timerRef.current);

    // 同步服务器时间
    const syncTime = async () => {
      try {
        const info = await getExamTime(session.session_id);
        if (info.remaining_seconds != null) setTimeLeft(info.remaining_seconds);
        if (!info.valid && info.auto_submitted) {
          // 超时自动交卷
          const result = await submitAllExam(session.session_id);
          setExamResult(result);
          setPhase("result");
        }
      } catch {}
    };
    syncTime();

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          // 时间到
          handleTimeUp();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [phase, session]);

  const handleTimeUp = useCallback(async () => {
    if (!session) return;
    try {
      const result = await submitAllExam(session.session_id);
      setExamResult(result);
      setPhase("result");
    } catch {}
  }, [session]);

  // ── 每30秒同步服务器时间 ──
  useEffect(() => {
    if (phase !== "answering") return;
    const interval = setInterval(async () => {
      try {
        const info = await getExamTime(session?.session_id);
        if (info.remaining_seconds != null) setTimeLeft(info.remaining_seconds);
        if (!info.valid && info.auto_submitted) {
          const result = await submitAllExam(session?.session_id);
          setExamResult(result);
          setPhase("result");
        }
      } catch {}
    }, 30000);
    return () => clearInterval(interval);
  }, [phase, session]);

  // ── 选择答案 ──
  const toggleAnswer = useCallback((letter: string) => {
    if (!currentQuestion) return;
    const qt = currentQuestion.question_type;
    if (qt === "single" || qt === "judge" || qt === "choice") {
      const newAns = [letter];
      setSelectedAnswers(newAns);
      setSavedAnswers((prev) => ({ ...prev, [currentQuestion.id]: newAns }));
    } else if (qt === "multiple") {
      setSelectedAnswers((prev) => {
        const next = prev.includes(letter)
          ? prev.filter((a) => a !== letter)
          : [...prev, letter];
        setSavedAnswers((prev2) => ({ ...prev2, [currentQuestion.id]: next }));
        return next;
      });
    }
  }, [currentQuestion]);

  // ── 保存填空/简答答案 ──
  const saveFillAnswer = useCallback((text: string) => {
    if (!currentQuestion) return;
    setFillAnswer(text);
    const trimmed = text.trim();
    if (trimmed) {
      setSavedAnswers((prev) => ({ ...prev, [currentQuestion.id]: [trimmed] }));
    } else {
      setSavedAnswers((prev) => {
        const next = { ...prev };
        delete next[currentQuestion.id];
        return next;
      });
    }
  }, [currentQuestion]);

  // ── 导航 ──
  const goToQuestion = useCallback((idx: number) => {
    // 保存当前题答案
    if (currentQuestion) {
      const isFillType = !OPTION_TYPES.includes(currentQuestion.question_type);
      if (isFillType && fillAnswer.trim()) {
        setSavedAnswers((prev) => ({ ...prev, [currentQuestion.id]: [fillAnswer.trim()] }));
      } else if (selectedAnswers.length > 0) {
        setSavedAnswers((prev) => ({ ...prev, [currentQuestion.id]: selectedAnswers }));
      }
    }
    setCurrentIdx(idx);
    const nextQ = questions[idx];
    const saved = savedAnswers[nextQ?.id] || [];
    setSelectedAnswers(saved);
    // 恢复填空答案
    const isFillType = nextQ && !OPTION_TYPES.includes(nextQ.question_type);
    setFillAnswer(isFillType && saved.length > 0 ? saved[0] : "");
  }, [currentQuestion, selectedAnswers, savedAnswers, questions, fillAnswer]);

  const handleNext = useCallback(() => {
    if (currentIdx < questions.length - 1) goToQuestion(currentIdx + 1);
  }, [currentIdx, questions.length, goToQuestion]);

  const handlePrev = useCallback(() => {
    if (currentIdx > 0) goToQuestion(currentIdx - 1);
  }, [currentIdx, goToQuestion]);

  // ── 提交考试 ──
  const handleSubmitAll = useCallback(async () => {
    if (!session) return;
    const confirmed = window.confirm(
      `确定交卷吗？\n已完成 ${Object.keys(savedAnswers).length} / ${questions.length} 题`
    );
    if (!confirmed) return;

    setPhase("submitting");
    try {
      // 先逐题提交答案（调用考试 submit 路由）
      for (const q of questions) {
        const userAns = savedAnswers[q.id];
        if (userAns && userAns.length > 0) {
          await submitExamAnswer(session.session_id, q.id, userAns, 0).catch(() => {});
        }
      }
      // 批量交卷
      const result = await submitAllExam(session.session_id);
      setExamResult(result);
      setPhase("result");
    } catch (e: any) {
      setError(e?.message || "交卷失败");
      setPhase("answering");
    }
  }, [session, questions, savedAnswers]);

  // ── 返回重选 ──
  const handleRetry = useCallback(() => {
    setPhase("setup");
    setSession(null);
    setQuestions([]);
    setCurrentIdx(0);
    setSelectedAnswers([]);
    setSavedAnswers({});
    setExamResult(null);
    setError("");
    startedRef.current = false;
  }, []);

  // ── 格式化时间 ──
  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const answeredCount = Object.keys(savedAnswers).length;
  const unansweredCount = questions.length - answeredCount;

  // ── Setup Screen ──
  if (phase === "setup") {
    return (
      <div className="flex flex-col items-center justify-center h-full px-6 py-8">
        <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
          <FileText size={20} className="text-red-500" />
        </div>
        <h3 className="text-base font-semibold text-[var(--color-text)] mb-1">
          {nodeLabel ? `「${nodeLabel}」考试` : bankName ? `${bankName} 考试` : "模拟考试"}
        </h3>
        <p className="text-[11px] text-[var(--color-text-muted)] text-center mb-6 leading-relaxed">
          计时答题 · 答题卡导航 · 自动交卷 · 成绩报告
        </p>

        {/* 题库选择 */}
        {banks.length > 1 && (
          <div className="w-full mb-4">
            <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">选择题库</p>
            <select value={selectedBankId} onChange={e => setSelectedBankId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-xs">
              {banks.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        )}

        {/* 时长选择 */}
        <div className="w-full mb-4">
          <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">考试时长</p>
          <div className="flex gap-2">
            {[15, 30, 45, 60, 90, 120].map((m) => (
              <button key={m} onClick={() => setDuration(m)}
                className={`flex-1 py-2 rounded-lg border text-center text-sm font-medium transition-all ${
                  duration === m
                    ? "border-red-500 bg-red-500/10 text-red-500"
                    : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)] hover:border-red-500/30"
                }`}>{m}min</button>
            ))}
          </div>
        </div>

        {/* 题数选择 */}
        <div className="w-full mb-4">
          <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">题目数量</p>
          <div className="flex gap-2">
            {[10, 20, 30, 50].map((n) => (
              <button key={n} onClick={() => setCount(n)}
                className={`flex-1 py-2 rounded-lg border text-center text-sm font-medium transition-all ${
                  count === n
                    ? "border-red-500 bg-red-500/10 text-red-500"
                    : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)] hover:border-red-500/30"
                }`}>{n}题</button>
            ))}
          </div>
        </div>

        {/* 提示 */}
        <div className="w-full mb-6 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <div className="flex items-start gap-2">
            <AlertTriangle size={12} className="text-amber-500 mt-0.5" />
            <p className="text-[10px] text-amber-600 leading-relaxed">
              考后不可重做，到时间自动交卷。未答题目记错。
            </p>
          </div>
        </div>

        <button onClick={handleStart} disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-red-500 text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50">
          {loading ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
          {loading ? "出题中..." : "开始考试"}
        </button>

        {error && <p className="mt-3 text-[10px] text-red-500">{error}</p>}
      </div>
    );
  }

  // ── 答题页面 ──
  if (phase === "answering") {
    const isLast = currentIdx >= questions.length - 1;

    return (
      <div className="flex flex-col h-full">
        {/* 顶部：计时 + 答题卡按钮 */}
        <div className="sticky top-0 z-10 bg-[var(--color-bg)] border-b border-[var(--color-border)]/50 px-4 py-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-[var(--color-text-muted)]">
                {currentIdx + 1} / {questions.length}
              </span>
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium ${
                timeLeft < 120 ? "bg-red-500/10 text-red-500 animate-pulse" :
                timeLeft < 300 ? "bg-amber-500/10 text-amber-500" :
                "bg-[var(--color-surface)] text-[var(--color-text)]"
              }`}>
                <Clock size={12} />
                {formatTime(timeLeft)}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setShowAnswerSheet(!showAnswerSheet)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] border transition-all ${
                  showAnswerSheet
                    ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30"
                }`}>
                <Grid3X3 size={12} />
                答题卡
                <span className="ml-1 text-[9px]">{answeredCount}/{questions.length}</span>
              </button>
              <button onClick={handleSubmitAll}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-medium bg-red-500 text-white hover:opacity-90 transition-opacity">
                <Send size={10} />交卷
              </button>
            </div>
          </div>
          {/* 进度条 */}
          <div className="w-full h-1 bg-[var(--color-border)]/30 rounded-full overflow-hidden mt-2">
            <div className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300"
              style={{ width: `${(answeredCount / Math.max(questions.length, 1)) * 100}%` }} />
          </div>
        </div>

        {/* 主区域：答题卡 + 题目 */}
        <div className="flex-1 flex overflow-hidden">
          {/* 答题卡侧栏 */}
          {showAnswerSheet && (
            <div className="w-48 flex-shrink-0 border-r border-[var(--color-border)]/30 bg-[var(--color-surface)]/50 overflow-y-auto p-2">
              <p className="text-[9px] text-[var(--color-text-muted)] mb-2 px-1 font-medium uppercase tracking-wider">答题卡</p>
              <div className="grid grid-cols-4 gap-1.5">
                {questions.map((q, i) => {
                  const ans = savedAnswers[q.id];
                  const isAnswered = ans && ans.length > 0;
                  const isActive = i === currentIdx;
                  return (
                    <button key={q.id} onClick={() => { goToQuestion(i); setShowAnswerSheet(false); }}
                      className={`w-full aspect-square flex items-center justify-center rounded-md text-[10px] font-medium transition-all ${
                        isActive
                          ? "ring-2 ring-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                          : isAnswered
                            ? "bg-green-500/10 text-green-600 border border-green-500/30"
                            : "bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30"
                      }`}>
                      {i + 1}
                    </button>
                  );
                })}
              </div>
              <div className="mt-3 px-1 space-y-1 text-[9px] text-[var(--color-text-muted)]">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-sm bg-green-500/30 border border-green-500/50" />
                  <span>已答 ({answeredCount})</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[var(--color-bg)] border border-[var(--color-border)]/50" />
                  <span>未答 ({unansweredCount})</span>
                </div>
              </div>
            </div>
          )}

          {/* 题目区域 */}
          <div className="flex-1 overflow-y-auto px-4 py-4">
            {currentQuestion && (
              <>
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-surface)] border border-[var(--color-border)]/50 text-[var(--color-text-muted)]">
                    {currentQuestion.question_type === "single" || currentQuestion.question_type === "choice" ? "单选题" :
                     currentQuestion.question_type === "multiple" ? "多选题" :
                     currentQuestion.question_type === "judge" ? "判断题" :
                     currentQuestion.question_type === "fill" ? "填空题" :
                     currentQuestion.question_type === "free_form" || currentQuestion.question_type === "essay" ? "简答题" : "选择题"}
                  </span>
                  <span className="text-[9px] text-[var(--color-text-muted)]">
                    难度 {"★".repeat(currentQuestion.difficulty).padEnd(5, "☆")}
                  </span>
                </div>

                <QuestionStem stem={currentQuestion.stem} className="text-base leading-relaxed mb-4" />

                {/* 选项类型 */}
                {OPTION_TYPES.includes(currentQuestion.question_type) && (
                <div className="space-y-2">
                  {currentQuestion.options?.map((opt) => {
                    const isSelected = selectedAnswers.includes(opt.letter);
                    const isMultiple = currentQuestion.question_type === "multiple";
                    return (
                      <button key={opt.letter} onClick={() => toggleAnswer(opt.letter)}
                        className={`w-full flex items-start gap-3 p-3 rounded-lg border text-left transition-all ${
                          isSelected
                            ? "border-red-500 bg-red-500/10"
                            : "border-[var(--color-border)]/60 bg-[var(--color-surface)] hover:border-red-500/30"
                        }`}>
                        <span className={`flex-shrink-0 w-6 h-6 flex items-center justify-center text-[11px] font-medium ${
                          isMultiple ? "rounded-md" : "rounded-full"
                        } ${
                          isSelected
                            ? "bg-red-500 text-white"
                            : "bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]"
                        }`}>{opt.letter}</span>
                        <span className="text-[13px] text-[var(--color-text)] leading-relaxed pt-0.5 [&_p]:m-0 [&_.katex]:text-sm">
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                      {opt.text}
                    </ReactMarkdown>
                  </span>
                      </button>
                    );
                  })}
                </div>
                )}

                {/* 填空/简答类型 */}
                {!OPTION_TYPES.includes(currentQuestion.question_type) && (
                <div>
                  <textarea
                    value={fillAnswer}
                    onChange={(e) => saveFillAnswer(e.target.value)}
                    placeholder={currentQuestion.question_type === "fill" ? "输入你的答案..." : "输入你的回答..."}
                    rows={currentQuestion.question_type === "fill" ? 2 : 4}
                    className="w-full px-4 py-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm resize-none focus:outline-none focus:border-red-500 transition-colors"
                  />
                </div>
                )}
              </>
            )}

            {/* 空状态 */}
            {!currentQuestion && (
              <div className="flex items-center justify-center h-full">
                <p className="text-xs text-[var(--color-text-muted)]">暂无题目</p>
              </div>
            )}
          </div>
        </div>

        {/* 底部导航 */}
        <div className="border-t border-[var(--color-border)]/30 px-4 py-2.5 flex items-center justify-between">
          <button onClick={handlePrev} disabled={currentIdx === 0}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30 disabled:opacity-30 transition-all">
            <ChevronLeft size={12} />上一题
          </button>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {currentIdx + 1} / {questions.length}
          </span>
          <button onClick={isLast ? handleSubmitAll : handleNext}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
              isLast
                ? "bg-red-500 text-white hover:opacity-90"
                : "border border-[var(--color-border)]/50 text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30"
            }`}>
            {isLast ? "交卷" : "下一题"}
            {!isLast && <ChevronRight size={12} />}
          </button>
        </div>
      </div>
    );
  }

  // ── 成绩报告 ──
  if (phase === "result" && examResult) {
    const { score, grade, grade_color, stats, type_stats, question_results } = examResult;
    const colorMap: Record<string, string> = {
      green: "text-green-500 border-green-500/30 bg-green-500/10",
      blue: "text-blue-500 border-blue-500/30 bg-blue-500/10",
      yellow: "text-yellow-500 border-yellow-500/30 bg-yellow-500/10",
      red: "text-red-500 border-red-500/30 bg-red-500/10",
    };
    const barColor = grade_color === "green" ? "bg-green-500" :
                     grade_color === "blue" ? "bg-blue-500" :
                     grade_color === "yellow" ? "bg-yellow-500" : "bg-red-500";

    return (
      <div className="overflow-y-auto h-full px-4 py-6">
        {/* 分数大卡片 */}
        <div className={`text-center p-6 rounded-xl border-2 mb-6 ${colorMap[grade_color] || colorMap.blue}`}>
          <div className="w-14 h-14 rounded-full bg-white/20 flex items-center justify-center mx-auto mb-3">
            <Trophy size={24} className={grade_color === "green" ? "text-green-500" :
              grade_color === "blue" ? "text-blue-500" :
              grade_color === "yellow" ? "text-yellow-500" : "text-red-500"} />
          </div>
          <div className={`text-5xl font-bold mb-1 ${
            grade_color === "green" ? "text-green-500" :
            grade_color === "blue" ? "text-blue-500" :
            grade_color === "yellow" ? "text-yellow-500" : "text-red-500"
          }`}>{score}</div>
          <div className="text-lg font-semibold mt-1">{grade}</div>
          <div className="flex items-center justify-center gap-4 mt-3 text-[11px] opacity-80">
            <span>正确 {stats.correct}</span>
            <span>错误 {stats.wrong}</span>
            <span>未答 {stats.unanswered}</span>
          </div>
          <p className="text-[10px] mt-2 opacity-60">
            用时 {Math.floor(stats.duration / 60)}分{stats.duration % 60}秒
          </p>
        </div>

        {/* 题型统计 */}
        {Object.keys(type_stats).length > 0 && (
          <div className="mb-6">
            <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">题型统计</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(type_stats).map(([type, ts]) => (
                <div key={type} className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                  <p className="text-[11px] font-medium text-[var(--color-text)] mb-1">
                    {type === "single" ? "单选题" : type === "multiple" ? "多选题" : type}
                  </p>
                  <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
                    <span className="text-green-500">{ts.correct}✓</span>
                    <span className="text-red-500">{ts.wrong}✗</span>
                    <span className="ml-auto">{ts.total}题</span>
                  </div>
                  <div className="w-full h-1 bg-[var(--color-border)]/30 rounded-full overflow-hidden mt-1.5">
                    <div className={`h-full rounded-full ${barColor}`}
                      style={{ width: `${(ts.correct / Math.max(ts.total, 1)) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 逐题回顾 */}
        <div className="mb-6">
          <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">逐题回顾</p>
          <div className="space-y-2">
            {question_results.map((qr, i) => (
              <div key={qr.question_id}
                className={`p-3 rounded-lg border ${
                  qr.is_correct
                    ? "border-green-500/20 bg-green-500/5"
                    : "border-red-500/20 bg-red-500/5"
                }`}>
                <div className="flex items-start gap-2">
                  <span className={`flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full text-[9px] font-medium ${
                    qr.is_correct ? "bg-green-500/20 text-green-600" : "bg-red-500/20 text-red-500"
                  }`}>
                    {qr.is_correct ? <Check size={10} /> : <X size={10} />}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-[var(--color-text)] leading-relaxed">
                      <span className="text-[9px] text-[var(--color-text-muted)] mr-1">#{i + 1}</span>
                      <QuestionStem stem={qr.stem} className="text-sm leading-relaxed" />
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[9px] text-[var(--color-text-muted)]">
                      <span>你的答案: {Array.isArray(qr.user_answer) ? qr.user_answer.join(", ") || "未答" : "未答"}</span>
                      {!qr.is_correct && (
                        <span className="text-green-600">
                          正确答案: {Array.isArray(qr.correct_answer) ? qr.correct_answer.join(", ") : ""}
                        </span>
                      )}
                    </div>
                    {qr.analysis && !qr.is_correct && (
                      <p className="text-[9px] text-[var(--color-text-muted)] mt-1 leading-relaxed">
                        {qr.analysis}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3 mb-8">
          <button onClick={handleRetry}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-[var(--color-border)]/50 text-sm text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-all">
            <Brain size={14} />再来一次
          </button>
          {onClose && (
            <button onClick={onClose}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity">
              <BarChart3 size={14} />返回
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── 提交中 ──
  if (phase === "submitting") {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-red-500 mb-3" />
        <p className="text-xs text-[var(--color-text-muted)]">正在批卷...</p>
      </div>
    );
  }

  return null;
}
