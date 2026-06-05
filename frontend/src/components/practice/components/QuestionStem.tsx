"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

/**
 * 共享题干渲染组件 — 用于练习系统的所有子页面。
 * 封装对话系统的 MarkdownRenderer，统一渲染题干中的 Markdown + LaTeX 公式。
 *
 * 使用场景：
 * - 题库列表 (banks/[id])
 * - 练习会话 (sessions/[id])
 * - 练习面板 (PracticePanel)
 * - 错题本 (errors)
 * - 考试 (ExamPanel)
 * - 导入预览 (import)
 */
export default function QuestionStem({
  stem,
  className = "",
}: {
  stem: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {stem}
      </ReactMarkdown>
    </div>
  );
}
