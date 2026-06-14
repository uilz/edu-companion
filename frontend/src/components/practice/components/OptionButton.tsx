"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

interface Props {
  label: string;
  text: string;
  selected: boolean;
  showResult?: boolean;
  isCorrect?: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

/** 选项按钮 — 支持 selected / correct / wrong 三种态 */
export default function OptionButton({
  label, text, selected, showResult, isCorrect, disabled, onSelect,
}: Props) {
  let border = "border-[var(--color-border)] hover:border-[var(--color-accent)]/40 hover:bg-[var(--color-surface)]";
  let bg = "bg-[var(--color-bg)]";
  let textColor = "text-[var(--color-text)]";
  let indicator = null;

  if (showResult) {
    if (isCorrect) {
      border = "border-green-400 dark:border-green-600";
      bg = "bg-green-50 dark:bg-green-900/15";
      textColor = "text-green-700 dark:text-green-300";
      indicator = (
        <span className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
          <svg viewBox="0 0 16 16" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="3,8 7,12 13,4" />
          </svg>
        </span>
      );
    } else if (selected) {
      border = "border-red-400 dark:border-red-600";
      bg = "bg-red-50 dark:bg-red-900/15";
      textColor = "text-red-700 dark:text-red-300";
      indicator = (
        <span className="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center flex-shrink-0">
          <svg viewBox="0 0 16 16" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="4" y1="4" x2="12" y2="12" /><line x1="12" y1="4" x2="4" y2="12" />
          </svg>
        </span>
      );
    } else {
      border = "border-[var(--color-border)] opacity-40";
    }
  } else if (selected) {
    border = "border-[var(--color-accent)]";
    bg = "bg-[var(--color-accent)]/5";
    textColor = "text-[var(--color-accent)]";
  }

  return (
    <button
      onClick={onSelect}
      disabled={disabled}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-150 ${border} ${bg} ${textColor} ${disabled ? "cursor-default" : "cursor-pointer"}`}
    >
      <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border ${
        showResult
          ? isCorrect
            ? "border-green-400 bg-green-500 text-white"
            : selected
              ? "border-red-400 bg-red-500 text-white"
              : "border-[var(--color-border)] text-[var(--color-text-muted)]"
          : selected
            ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
            : "border-[var(--color-border)] text-[var(--color-text-muted)]"
      }`}>
        {label}
      </span>
      <span className="flex-1 text-left text-sm leading-relaxed [&_p]:m-0 [&_.katex]:text-sm">
        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
          {text}
        </ReactMarkdown>
      </span>
      {indicator}
    </button>
  );
}
