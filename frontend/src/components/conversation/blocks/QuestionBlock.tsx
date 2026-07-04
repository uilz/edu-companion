"use client";

import React, { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Send, ChevronLeft, ChevronRight, Check } from "lucide-react";
import { getChatStreamAPI } from "@/store/conversation/actions/send-message";
import { useMessageStore } from "@/store/conversation/message-store";
import MarkdownRenderer from "./MarkdownRenderer";

interface QuestionItem {
  question: string;
  options?: string[];
}

interface QuestionBlockProps {
  content: Record<string, unknown>;
  convId?: string;
}

/** 从 content 中提取已作答的答案列表。
 *  content.user_answer 是字符串（前端提交的 answers），按下划线/换行等分隔成多题。
 *  对多问题场景，前端提交时已用 "问题N：xxx" 格式拼接。
 */
function parseUserAnswer(content: Record<string, unknown>): string[] {
  const raw = (content.user_answer as string) || "";
  if (!raw) return [];
  // 多题分隔："问题1：xxx\n问题2：yyy" 或单题 "xxx"
  return raw
    .split(/\n+/)
    .map((line) => line.replace(/^问题\d+[：:]\s*/, "").trim())
    .filter(Boolean);
}

// ──────────────── 提交工具结果（恢复挂起的管线） ────────────────

async function submitToolResult(
  toolCallId: string,
  answers: string,
  convId: string,
) {
  const chatStream = getChatStreamAPI();
  if (!chatStream?.submitToolResult) return;

  // 方案A：不创建新的 assistant 占位消息。
  // 原 send() 的 streamingId 仍活跃，恢复后事件继续流入同一流式消息。
  await chatStream.submitToolResult(toolCallId, answers, convId);
}

/** 提交答案时立即把 user_answer 写入本地 store 中对应 tool 块的 result_content，
 *  让 UI 立刻进入"已作答"模式，无需等 server 端 done 事件回传。
 *  tool_call_id 同时匹配外层 tool_call_id 和 result_content.tool_call_id。
 */
function applyLocalUserAnswer(toolCallId: string, answerText: string) {
  if (!toolCallId || !answerText) return;
  const answeredAt = Date.now() / 1000;
  useMessageStore.setState((state) => ({
    messages: state.messages.map((msg) => ({
      ...msg,
      content_blocks: (msg.content_blocks || []).map((b: any) => {
        if (b?.type !== "tool") return b;
        const bTc = b.tool_call_id;
        const rcTc = b.result_content?.tool_call_id;
        if (bTc !== toolCallId && rcTc !== toolCallId) return b;
        if (!b.result_content) return b;
        return {
          ...b,
          result_content: {
            ...b.result_content,
            user_answer: answerText,
            answered_at: answeredAt,
          },
        };
      }),
    })),
  }));
}

// ──────────────── 选择题（多选交互） ────────────────

function ChoiceQuestion({
  question, options, selected, onToggle,
}: {
  question: string; options: string[]; selected: string[]; onToggle: (v: string) => void;
}) {
  const [showCustom, setShowCustom] = useState(false);
  const [customValue, setCustomValue] = useState("");

  const confirmCustom = () => {
    if (customValue.trim()) { onToggle(customValue.trim()); setCustomValue(""); }
  };

  if (showCustom) {
    return (
      <div>
        <div className="text-sm font-medium text-[var(--color-text)] mb-3">
          <MarkdownRenderer content={question} />
        </div>
        <div className="flex items-center gap-2">
          <input
            value={customValue}
            onChange={(e) => setCustomValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); confirmCustom(); } }}
            placeholder="输入你的回答..."
            className="flex-1 px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]
              focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30
              text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
            autoFocus
          />
          <button
            onClick={confirmCustom}
            disabled={!customValue.trim()}
            className="p-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-30 transition-opacity"
          >
            <Send size={16} />
          </button>
        </div>
        <button
          onClick={() => setShowCustom(false)}
          className="mt-2 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          返回选项
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="text-sm font-medium text-[var(--color-text)] mb-3">
        <MarkdownRenderer content={question} />
      </div>
      <div className="flex flex-col gap-1.5">
        {options.map((opt, i) => {
          const isSel = selected.includes(opt);
          return (
            <button
              key={i}
              onClick={() => onToggle(opt)}
              className={`flex items-center gap-3 px-3.5 py-2 rounded-lg border text-left transition-all duration-150 text-sm cursor-pointer
                ${isSel
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                  : "border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/5 text-[var(--color-text)]"
                }`}
            >
              <span className={`flex-shrink-0 w-5 h-5 rounded flex items-center justify-center text-xs font-bold
                ${isSel ? "bg-[var(--color-accent)] text-white" : "border border-[var(--color-border)] text-transparent"}`}>
                {isSel ? <Check size={12} /> : null}
              </span>
              <span className="[&_.katex]:text-inherit">
                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {opt}
                </ReactMarkdown>
              </span>
            </button>
          );
        })}
        <button
          onClick={() => setShowCustom(true)}
          className="flex items-center gap-3 px-3.5 py-2 rounded-lg border border-dashed border-[var(--color-border)]
            text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]
            hover:bg-[var(--color-accent)]/5 transition-all duration-150 cursor-pointer"
        >
          <span className="flex-shrink-0 w-5 h-5 rounded border border-dashed flex items-center justify-center text-xs text-[var(--color-text-muted)]">+</span>
          <span>其他（自定义回答）</span>
        </button>
      </div>
    </div>
  );
}

// ──────────────── 开放题（输入交互） ────────────────

function OpenQuestion({
  question, value, onChange,
}: {
  question: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <div className="text-sm font-medium text-[var(--color-text)] mb-3">
        <MarkdownRenderer content={question} />
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="输入你的回答..."
        autoComplete="off"
        className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]
          focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30
          text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
        autoFocus
      />
    </div>
  );
}

// ──────────────── 只读摘要（提交后的浏览模式 / 持久化还原） ────────────────

function ReadOnlySummary({ questions, answers }: { questions: QuestionItem[]; answers: string[][]; }) {
  return (
    <div className="mt-3 mb-2 rounded-lg border border-[var(--color-border)]/40 bg-[var(--color-surface)]/30 overflow-hidden">
      <div className="px-4 py-2 text-xs text-[var(--color-text-muted)] border-b border-[var(--color-border)]/20">
        已作答
      </div>
      {questions.map((q, i) => (
        <div key={i} className="px-4 py-2 flex items-baseline gap-2 text-sm">
          <span className="text-[var(--color-text-muted)] flex-shrink-0 [&_.katex]:text-inherit">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {q.question}
            </ReactMarkdown>
          </span>
          <span className="text-[var(--color-text)]">—</span>
          <span className="text-[var(--color-text)] [&_.katex]:text-inherit">
            {answers[i]?.length > 0
              ? answers[i].map((a, ai) => (
                  <ReactMarkdown
                    key={ai}
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                    components={{ p: ({ children }) => <>{children}</> }}
                  >
                    {a}
                  </ReactMarkdown>
                ))
              : "未回答"}
          </span>
        </div>
      ))}
    </div>
  );
}

/** 持久化的已作答视图：从 content.user_answer 解析答案并直接展示只读摘要。
 *  适用于刷新页面后、或者从历史消息加载时的场景。
 */
function PersistedAnswersView({
  content, fallbackQuestions,
}: {
  content: Record<string, unknown>;
  fallbackQuestions: QuestionItem[];
}) {
  const multiQuestions = (content.questions as QuestionItem[] | undefined) || [];
  const singleQuestion = (content.question as string) || "";
  const questions: QuestionItem[] = multiQuestions.length > 0
    ? multiQuestions
    : (singleQuestion ? [{ question: singleQuestion, options: content.options as string[] | undefined }] : fallbackQuestions);
  const flatAnswers = parseUserAnswer(content);
  // 将扁平答案按题目数对齐
  const answers: string[][] = questions.map((_, i) => flatAnswers[i] ? [flatAnswers[i]] : []);
  if (questions.length === 0) return null;
  return <ReadOnlySummary questions={questions} answers={answers} />;
}

// ──────────────── 单问题卡片（交互 + 只读两种状态） ────────────────

function SingleQuestionCard({
  question, options, qType, onAnswer,
}: {
  question: string; options: string[]; qType: string; onAnswer: (answer: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [sent, setSent] = useState(false);

  if (sent) {
    return (
      <ReadOnlySummary
        questions={[{ question, options: qType === "choice" ? options : undefined }]}
        answers={[qType === "choice" ? selected : (inputValue ? [inputValue] : [])]}
      />
    );
  }

  // 选择题
  if (qType === "choice" && options.length > 0) {
    return (
      <div className="mt-3 mb-2 rounded-xl border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 overflow-hidden">
        <div className="flex items-center gap-2 px-4 pt-3 pb-2">
          <span className="w-6 h-6 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center text-xs flex-shrink-0">❓</span>
          <span className="text-sm font-medium text-[var(--color-text)]">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {question}
            </ReactMarkdown>
          </span>
        </div>
        <div className="px-4 pb-3">
          <ChoiceQuestion
            question={question}
            options={options}
            selected={selected}
            onToggle={(v) => setSelected(prev => prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v])}
          />
        </div>
        <div className="px-4 pb-4">
          <button
            onClick={() => { onAnswer(selected.join("、")); setSent(true); }}
            disabled={selected.length === 0}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium
              bg-[var(--color-accent)] text-white hover:opacity-90
              disabled:opacity-30 disabled:cursor-not-allowed transition-opacity"
          >
            <Check size={16} />
            提交
          </button>
        </div>
      </div>
    );
  }

  // 开放题
  return (
    <div className="mt-3 mb-2 rounded-xl border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 overflow-hidden">
      <div className="flex items-center gap-2 px-4 pt-3 pb-2">
        <span className="w-6 h-6 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center text-xs flex-shrink-0">❓</span>
        <span className="text-sm font-medium text-[var(--color-text)]">
          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
            {question}
          </ReactMarkdown>
        </span>
      </div>
      <div className="px-4 pb-4 flex items-center gap-2">
        <input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (inputValue.trim()) { onAnswer(inputValue.trim()); setSent(true); } } }}
          placeholder="输入你的回答..."
          className="flex-1 px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]
            focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30
            text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
          autoFocus
        />
        <button
          onClick={() => { if (inputValue.trim()) { onAnswer(inputValue.trim()); setSent(true); } }}
          disabled={!inputValue.trim()}
          className="p-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-30 transition-opacity"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

// ──────────────── 多问题分组（逐步导航 + 统一提交 + 只读浏览） ────────────────

function MultiQuestionGroup({
  questions, qType, onAnswer,
}: {
  questions: QuestionItem[]; qType: string; onAnswer: (answer: string) => void;
}) {
  const total = questions.length;
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<string[][]>(() => questions.map(() => []));
  const [submitted, setSubmitted] = useState(false);
  // ref 同步跟踪最新 answers，handleSubmit 中读取避免闭包捕获旧值
  const answersRef = React.useRef<string[][]>(questions.map(() => []));

  const toggleAnswer = useCallback((val: string) => {
    setAnswers(prev => {
      const next = prev.map(a => [...a]);
      const cur = next[step];
      const idx = cur.indexOf(val);
      if (idx >= 0) cur.splice(idx, 1);
      else cur.push(val);
      answersRef.current = next;
      return next;
    });
  }, [step]);

  const setAnswer = useCallback((val: string) => {
    setAnswers(prev => {
      const next = prev.map(a => [...a]);
      next[step] = val ? [val] : [];
      answersRef.current = next;
      return next;
    });
  }, [step]);

  const handleSubmit = () => {
    const latest = answersRef.current;
    console.debug("[MultiQuestionGroup] answers snapshot:", JSON.stringify(latest));
    const lines = questions.map((q, i) => {
      const ans = latest[i];
      if (!ans || ans.length === 0) return `问题${i + 1}：未回答`;
      return `问题${i + 1}：${ans.join("、")}`;
    });
    onAnswer(lines.join("\n"));
    setSubmitted(true);
  };

  // ── 已提交 → 只读浏览 ──
  if (submitted) {
    return <ReadOnlySummary questions={questions} answers={answers} />;
  }

  const q = questions[step];
  const hasAnswer = answers[step]?.length > 0;
  const isFirst = step === 0;
  const isLast = step === total - 1;

  return (
    <div className="mt-3 mb-2 rounded-xl border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 overflow-hidden">
      {/* 头部 + 进度 */}
      <div className="flex items-center justify-between px-4 pt-3 pb-1">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 rounded-full bg-[var(--color-accent)]/10 flex items-center justify-center text-xs flex-shrink-0">❓</span>
          <span className="text-sm font-medium text-[var(--color-text)]">提问</span>
        </div>
        <span className="text-xs text-[var(--color-text-muted)]">{step + 1}/{total}</span>
      </div>

      {/* 进度条 */}
      <div className="px-4 pt-1 pb-2">
        <div className="flex gap-1">
          {questions.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors duration-200 cursor-pointer
                ${i === step ? "bg-[var(--color-accent)]" : answers[i]?.length > 0 ? "bg-[var(--color-accent)]/40" : "bg-[var(--color-border)]"}`}
              onClick={() => setStep(i)}
            />
          ))}
        </div>
      </div>

      {/* 题目 — key={step} 强制切换步骤时重新挂载，避免浏览器 autofill 串值 */}
      <div className="px-4 pb-4" key={step}>
        {qType === "choice" || q.options?.length ? (
          <ChoiceQuestion
            question={q.question}
            options={q.options || []}
            selected={answers[step] || []}
            onToggle={(v) => toggleAnswer(v)}
          />
        ) : (
          <OpenQuestion
            question={q.question}
            value={answers[step]?.[0] || ""}
            onChange={(v) => setAnswer(v)}
          />
        )}
      </div>

      {/* 导航按钮 */}
      <div className="flex items-center justify-between px-4 pb-4">
        <button
          onClick={() => !isFirst && setStep(s => s - 1)}
          disabled={isFirst}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm
            text-[var(--color-text-muted)] hover:text-[var(--color-text)]
            disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft size={16} />
          上一题
        </button>

        {isLast ? (
          <button
            onClick={handleSubmit}
            disabled={!hasAnswer}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium
              bg-[var(--color-accent)] text-white hover:opacity-90
              disabled:opacity-30 disabled:cursor-not-allowed transition-opacity"
          >
            <Check size={16} />
            提交{total}题
          </button>
        ) : (
          <button
            onClick={() => !isLast && setStep(s => s + 1)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm
              text-[var(--color-text)] hover:bg-[var(--color-accent)]/10 transition-colors"
          >
            下一题
            <ChevronRight size={16} />
          </button>
        )}
      </div>
    </div>
  );
}

// ──────────────── 入口组件 ────────────────

export default function QuestionBlock({ content, convId }: QuestionBlockProps) {
  const qType = (content.type as string) || "choice";
  const questions = (content.questions as QuestionItem[]) || [];
  const singleQuestion = (content.question as string) || "";
  const singleOptions = (content.options as string[]) || [];
  const toolCallId = (content.tool_call_id as string) || "";
  const hasPersistedAnswer = !!(content.user_answer as string | undefined)?.length;

  // 已持久化（后端写入 result_content.user_answer）→ 优先显示只读摘要
  if (hasPersistedAnswer) {
    const fallbackQuestions: QuestionItem[] = questions.length > 0
      ? questions
      : (singleQuestion ? [{ question: singleQuestion, options: singleOptions }] : []);
    return <PersistedAnswersView content={content} fallbackQuestions={fallbackQuestions} />;
  }

  const handleAnswer = useCallback((answerText: string) => {
    if (!toolCallId || !convId) {
      console.warn("[QuestionBlock] 缺少必要字段", {
        toolCallId: toolCallId || "(空)",
        convId: convId || "(空)",
        contentKeys: Object.keys(content || {}),
      });
      return;
    }
    // 立即在本地 store 写入 user_answer，UI 立刻进入"已作答"模式
    applyLocalUserAnswer(toolCallId, answerText);
    submitToolResult(toolCallId, answerText, convId);
  }, [toolCallId, convId, content]);

  if (questions.length > 0) {
    return <MultiQuestionGroup questions={questions} qType={qType} onAnswer={handleAnswer} />;
  }

  if (!singleQuestion) return null;

  return <SingleQuestionCard question={singleQuestion} options={singleOptions} qType={qType} onAnswer={handleAnswer} />;
}
