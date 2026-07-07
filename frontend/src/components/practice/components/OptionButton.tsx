"use client";

import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
// katex/dist/katex.min.css 已在 app/globals.css 统一 import

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
function OptionButtonImpl({
  label, text, selected, showResult, isCorrect, disabled, onSelect,
}: Props) {
  let border = "border hover:border-accent/40 hover:bg-surface";
  let bg = "bg-page";
  let textColor = "text";
  let indicator = null;

  if (showResult) {
    if (isCorrect) {
      border = "border-success/40 dark:border-success/60";
      bg = "bg-success/10 dark:bg-success/10";
      textColor = "text-success dark:text-success";
      indicator = (
        <span className="w-5 h-5 rounded-full bg-success flex items-center justify-center flex-shrink-0">
          <svg viewBox="0 0 16 16" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="3,8 7,12 13,4" />
          </svg>
        </span>
      );
    } else if (selected) {
      border = "border-danger/40 dark:border-danger/40";
      bg = "bg-danger/10 dark:bg-danger/10";
      textColor = "text-danger dark:text-danger";
      indicator = (
        <span className="w-5 h-5 rounded-full bg-danger flex items-center justify-center flex-shrink-0">
          <svg viewBox="0 0 16 16" className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="4" y1="4" x2="12" y2="12" /><line x1="12" y1="4" x2="4" y2="12" />
          </svg>
        </span>
      );
    } else {
      border = "border opacity-40";
    }
  } else if (selected) {
    border = "border-accent";
    bg = "bg-accent/5";
    textColor = "text-accent";
  }

  return (
    <button
      onClick={onSelect}
      disabled={disabled}
      className={`w-full flex items-center gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl border transition-all duration-150 ${border} ${bg} ${textColor} ${disabled ? "cursor-default" : "cursor-pointer"}`}
    >
      <span className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border ${
        showResult
          ? isCorrect
            ? "border-success/40 bg-success text-white"
            : selected
              ? "border-danger/40 bg-danger text-white"
              : "border text-muted"
          : selected
            ? "border-accent bg-accent text-white"
            : "border text-muted"
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

/**
 * React.memo 包裹的 OptionButton — 选中/反馈状态未变时跳过重渲
 * 自定义比较函数：text 变化才重渲（KaTeX 渲染昂贵）
 */
const OptionButton = memo(OptionButtonImpl, (prev, next) => {
  return (
    prev.label === next.label &&
    prev.text === next.text &&
    prev.selected === next.selected &&
    prev.showResult === next.showResult &&
    prev.isCorrect === next.isCorrect &&
    prev.disabled === next.disabled
  );
});

export default OptionButton;
