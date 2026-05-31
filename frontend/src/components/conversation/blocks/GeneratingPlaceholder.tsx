import React from "react";
import { Loader2, FileText, Image, GitBranch as MindMap, Volume2 } from "lucide-react";

/** 生成中的占位组件：根据内容类型显示对应的 loading 图标和动画 */
export function GeneratingPlaceholder({ type }: { type: string }) {
  // 各类型对应的加载提示文本
  const labels: Record<string, string> = {
    image: "正在生成图像...",
    audio: "正在合成语音...",
    mindmap: "正在生成思维导图...",
    document: "正在生成文档...",
  };

  // 各类型对应的加载图标
  const icons: Record<string, React.ReactNode> = {
    image: <Image size={16} />,
    audio: <Volume2 size={16} />,
    mindmap: <MindMap size={16} />,
    document: <FileText size={16} />,
  };

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 mt-2">
      <div className="flex items-center gap-2 text-[var(--color-accent)]">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-xs font-medium">
          {labels[type] || "生成中..."}
        </span>
      </div>
      <div className="mt-2 h-1 bg-[var(--color-border)] overflow-hidden">
        <div
          className="h-full bg-[var(--color-accent)] animate-pulse active:scale-[0.97] transition-transform"
          style={{ width: "60%" }}
        />
      </div>
    </div>
  );
}
