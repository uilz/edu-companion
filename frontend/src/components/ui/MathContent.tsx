"use client";

import { useMemo } from "react";
import { renderMath } from "@/lib/math";

// ── 组件属性接口 ────────────────────────────────────────────────────
// text:      包含 LaTeX 公式（$...$ 或 $$...$$）的原始文本
// className: 自定义 CSS 类名（可选）
// as:        渲染为的 HTML 标签，支持 div / span / p（可选，默认 div）
interface MathContentProps {
  text: string;
  className?: string;
  as?: "div" | "span" | "p";
}

/**
 * Renders text with LaTeX math ($...$ and $$...$$) to proper KaTeX HTML.
 *
 * 将包含 LaTeX 数学公式的文本渲染为 KaTeX HTML。
 * 公式语法：行内公式用 $...$，行间公式用 $$...$$。
 */
export default function MathContent({ text, className = "", as: Tag = "div" }: MathContentProps) {
  // 使用 useMemo 缓存渲染结果，仅当 text 变化时重新调用 renderMath
  const html = useMemo(() => renderMath(text), [text]);

  // 将渲染后的 HTML 通过 dangerouslySetInnerHTML 注入到指定标签中
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
