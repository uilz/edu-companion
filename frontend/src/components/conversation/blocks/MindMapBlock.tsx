import { GitBranch as MindMap } from "lucide-react";

/** 思维导图块组件：显示思维导图标题和入口提示 */
export function MindMapBlock({ content }: { content: Record<string, unknown> }) {
  const topic = (content.topic as string) || "";

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <MindMap size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          思维导图
        </span>
      </div>
      <div className="px-3 py-3">
        <div className="text-sm text-[var(--color-text-secondary)]">
          🧠 {topic || "知识结构"}
        </div>
        <div className="text-[10px] text-[var(--color-text-muted)] mt-2">
          点击展开查看完整思维导图
        </div>
      </div>
    </div>
  );
}
