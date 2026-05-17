"use client";

import { useMemo } from "react";
import { renderMath } from "@/lib/math";

interface MathContentProps {
  text: string;
  className?: string;
  as?: "div" | "span" | "p";
}

/**
 * Renders text with LaTeX math ($...$ and $$...$$) to proper KaTeX HTML.
 */
export default function MathContent({ text, className = "", as: Tag = "div" }: MathContentProps) {
  const html = useMemo(() => renderMath(text), [text]);
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
