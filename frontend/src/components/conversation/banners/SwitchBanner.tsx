"use client";

/**
 * SwitchBanner — 上下文切换横幅
 * 检测到用户谈论其他专题时提示切换会话
 */
export default function SwitchBanner({
  domainName,
  topicName,
  fullPath,
  onSwitch,
  onDismiss,
}: {
  domainName: string;
  topicName: string;
  fullPath: string;
  onSwitch: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="mx-4 mt-2 px-4 py-3 bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30 rounded-lg active:scale-[0.97] transition-transform">
      <div className="flex items-start gap-3">
        <span className="text-lg">🔀</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--color-text)] leading-relaxed">
            检测到你在聊{" "}
            <strong>
              {fullPath ||
                `${domainName}${topicName ? ` → ${topicName}` : ""}`}
            </strong>
            ，要切换到对应会话吗？
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onSwitch}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] rounded-md active:scale-[0.97] transition-colors"
          >
            切换
          </button>
          <button
            onClick={onDismiss}
            className="px-2 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            留在此处
          </button>
        </div>
      </div>
    </div>
  );
}
