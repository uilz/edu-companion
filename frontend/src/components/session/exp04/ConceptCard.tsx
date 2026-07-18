"use client";

/**
 * 概念卡片 — silent-user 体验
 * 大段讲解内容 + 低压力建议按钮
 * 在用户沉默时展示，AI 继续讲解而非提问
 */
interface Props {
  title: string;
  content: string;
  onContinue: () => void;
  onAsk: (question: string) => void;
}

export default function ConceptCard({ title, content, onContinue, onAsk }: Props) {
  return (
    <div className="mx-5 mb-4 rounded-xl bg-surface border border-border/50 p-5 animate-in fade-in duration-300">
      <p className="text-[12px] text-ink-muted font-medium mb-2">{title}</p>
      <p className="text-[15px] leading-relaxed text-ink-primary font-serif">
        {content}
      </p>
      <div className="flex gap-2 mt-4">
        <button
          onClick={onContinue}
          className="px-3.5 py-2 rounded-full bg-accent text-white text-[12px] font-medium hover:bg-accent-hover transition-colors"
        >
          继续说
        </button>
        <button
          onClick={() => onAsk("这个地方能再细说一下吗？")}
          className="px-3.5 py-2 rounded-full border border-border text-[12px] text-ink-secondary hover:bg-surface-hover transition-colors"
        >
          能细说一下吗？
        </button>
        <button
          onClick={() => onAsk("我好像懂了，继续")}
          className="px-3.5 py-2 rounded-full border border-border text-[12px] text-ink-secondary hover:bg-surface-hover transition-colors"
        >
          我懂了，继续
        </button>
      </div>
    </div>
  );
}
