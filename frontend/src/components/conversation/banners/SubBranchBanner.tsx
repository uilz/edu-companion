"use client";

/**
 * SubBranchBanner — 子分支模式横幅提示
 */
export default function SubBranchBanner({
  quotedText,
  onExit,
}: {
  quotedText: string;
  onExit: () => void;
}) {
  const truncated =
    quotedText.length > 60 ? quotedText.slice(0, 60) + "…" : quotedText;
  return (
    <div className="mx-4 mt-2 px-4 py-3 bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30 rounded-lg active:scale-[0.97] transition-transform">
      <div className="flex items-center gap-3">
        <button
          onClick={onExit}
          className="flex-shrink-0 px-3 py-1.5 text-xs text-[var(--color-text-secondary)]
                     hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]
                     border border-[var(--color-border)] rounded-md active:scale-[0.97] transition-all"
        >
          ← 退出
        </button>
        <span className="text-sm text-[var(--color-text)] truncate">
          💬 「{truncated}」
        </span>
      </div>
    </div>
  );
}
