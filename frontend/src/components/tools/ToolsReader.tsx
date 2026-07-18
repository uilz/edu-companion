"use client";

import { useState } from "react";
import { toast } from "@/components/ui/Toast";

// ── Reading content ────────────────────────────────────────

const SUBJECT_READINGS: Record<
  string,
  { title: string; meta: string; paragraphs: string[]; highlights: { text: string; hint: string }[] }
> = {
  linear: {
    title: "矩阵乘法的几何意义",
    meta: "还剩 12 分钟的阅读量",
    paragraphs: [
      "矩阵乘法最容易被理解成「逐元素相乘」，但这是一个常见的误解。它的真正含义，是用一个矩阵的行，去乘另一个矩阵的列。",
      "这种运算对应着线性变换的复合。这也解释了为什么矩阵乘法不满足交换律。",
    ],
    highlights: [
      { text: "用一个矩阵的行，去乘另一个矩阵的列", hint: "行×列，不是逐元素" },
      { text: "不满足交换律", hint: "A×B ≠ B×A" },
    ],
  },
  recursion: {
    title: "递归树：把调用画出来",
    meta: "还剩 10 分钟的阅读量",
    paragraphs: [
      "递归调用看起来像无限循环，其实不是。每次调用，问题都在变小，小到基线条件就返回。",
      "把递归调用画成树状，能看出哪些计算是重复的。这就是递归树。",
    ],
    highlights: [
      { text: "问题都在变小", hint: "每次调用离基线更近一步" },
      { text: "递归树", hint: "可视化重复计算" },
    ],
  },
};

// ── Component ──────────────────────────────────────────────

interface Props {
  onClose: () => void;
}

export default function ToolsReader({ onClose }: Props) {
  const [subject] = useState<"linear" | "recursion">("linear");
  const reading = SUBJECT_READINGS[subject];

  const handleHighlight = (hint: string) => {
    toast.info(`🍎 已标记：「${hint}」`);
  };

  return (
    <div className="max-w-[680px] mx-auto px-5 py-6">
      {/* Meta */}
      <p className="text-[13px] text-ink-muted mb-2">{reading.meta}</p>

      {/* Title */}
      <h1 className="text-[26px] font-bold tracking-tight mb-3 leading-tight">
        {reading.title}
      </h1>

      {/* Body */}
      <div className="font-serif text-[17px] leading-relaxed text-ink-primary space-y-4">
        {reading.paragraphs.map((para, i) => (
          <p key={i}>{renderParagraph(para, reading.highlights, handleHighlight)}</p>
        ))}
      </div>

      {/* AI note */}
      <div className="mt-6 p-4 bg-[#f7f3ea] rounded-[3px_14px_14px_14px] text-[14.5px] leading-relaxed animate-in fade-in">
        <div className="flex items-center gap-1.5 text-[12px] text-ink-muted mb-2 font-semibold">
          🍎 苹果果注意到你划了这段
        </div>
        这正是你之前卡过的地方。可以回 Session 练习时做成卡片。
      </div>

      {/* Subject toggle hint */}
      <p className="mt-8 text-center text-[12px] text-ink-muted">
        在 Session 中阅读时可以划线做卡片
      </p>
    </div>
  );
}

// ── Paragraph renderer (highlights matched by substring) ───

function renderParagraph(
  text: string,
  highlights: { text: string; hint: string }[],
  onHighlight: (hint: string) => void,
): React.ReactNode {
  // Find all highlight positions
  const matches: { start: number; end: number; hint: string }[] = [];
  for (const h of highlights) {
    const idx = text.indexOf(h.text);
    if (idx !== -1) {
      matches.push({ start: idx, end: idx + h.text.length, hint: h.hint });
    }
  }

  if (matches.length === 0) return text;

  // Sort by position and split
  matches.sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  for (const m of matches) {
    if (m.start > cursor) {
      parts.push(text.slice(cursor, m.start));
    }
    parts.push(
      <mark
        key={m.start}
        onClick={() => onHighlight(m.hint)}
        className="cursor-pointer bg-gradient-to-t from-[rgba(255,159,10,0.25)] to-transparent bg-[length:100%_60%] bg-no-repeat bg-bottom px-0.5 transition-colors hover:from-[rgba(175,82,222,0.25)]"
      >
        {text.slice(m.start, m.end)}
      </mark>,
    );
    cursor = m.end;
  }

  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return parts;
}
