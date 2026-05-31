import { Volume2 } from "lucide-react";

/** 语音块组件：根据是否有 URL 显示语音生成中状态或播放器 */
export function AudioBlock({ content }: { content: Record<string, unknown> }) {
  const url = (content.url as string) || "";
  const text = (content.text as string) || "";
  const skillId = (content.skill_id as string) || "";

  if (!url) {
    return (
      <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 px-3 py-2">
        <div className="flex items-center gap-2">
          <Volume2 size={14} className="text-[var(--color-accent)]" />
          <span className="text-xs text-[var(--color-text-muted)]">语音生成中…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <Volume2 size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          语音讲解 {skillId && `· ${skillId}`}
        </span>
      </div>
      <div className="px-3 py-3">
        <audio controls className="w-full" style={{ height: 36 }}>
          <source src={url} type="audio/mpeg" />
        </audio>
        {text && (
          <div className="text-[10px] text-[var(--color-text-muted)] mt-2 line-clamp-2">
            {text}
          </div>
        )}
      </div>
    </div>
  );
}
