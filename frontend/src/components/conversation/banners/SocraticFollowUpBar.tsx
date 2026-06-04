"use client";

/**
 * SocraticFollowUpBar — 苏格拉底追问模式切换条
 * "追问AI": 点击选项直接发送消息
 * "回答追问": 点击选项弹出回答卡片 → AI 判断
 */
export default function SocraticFollowUpBar({
  followUpMode,
  setFollowUpMode,
  onAnswerClick,
}: {
  followUpMode: "ask" | "answer";
  setFollowUpMode: (mode: "ask" | "answer") => void;
  onAnswerClick?: () => void;
}) {
  return (
    <div className="flex-shrink-0 border-t border-[var(--color-border)] px-4 py-1.5">
      <div className="flex items-center gap-1">
        <button
          onClick={() => setFollowUpMode("ask")}
          className={`px-3 py-1 text-[11px] rounded-full transition-all ${
            followUpMode === "ask"
              ? "bg-[var(--color-accent)] text-white font-medium"
              : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          <span className="mr-1">💬</span>追问AI
        </button>
        <button
          onClick={() => {
            setFollowUpMode("answer");
            onAnswerClick?.();
          }}
          className={`px-3 py-1 text-[11px] rounded-full transition-all ${
            followUpMode === "answer"
              ? "bg-amber-500 text-white font-medium"
              : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          <span className="mr-1">💡</span>回答追问
        </button>
        <div className="flex-1" />
        <span className="text-[10px] text-[var(--color-text-muted)]">
          {followUpMode === "ask" ? "点击选项直接提问" : "用卡片回答AI追问"}
        </span>
      </div>
    </div>
  );
}
