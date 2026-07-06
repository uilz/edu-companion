"use client";

/**
 * SwitchBanner — 上下文切换横幅（demo 暖黄色）
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
    <div
      className="mx-4 mt-2 px-4 py-3 rounded-lg active:scale-[0.97] transition-transform"
      style={{
        backgroundColor: "var(--banner-switch-bg)",
        border: "1px solid var(--banner-switch-border)",
      }}
    >
      <div className="flex items-start gap-3">
        <span className="text-lg">🔀</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm leading-relaxed" style={{ color: "var(--color-ink-primary)" }}>
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
            className="px-3 py-1.5 text-xs text-white rounded-md active:scale-[0.97] transition-colors"
            style={{
              backgroundColor: "var(--color-amber)",
            }}
          >
            切换
          </button>
          <button
            onClick={onDismiss}
            className="px-2 py-1.5 text-xs"
            style={{ color: "var(--color-ink-muted)" }}
          >
            留在此处
          </button>
        </div>
      </div>
    </div>
  );
}
