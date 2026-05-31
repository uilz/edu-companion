import { FileText } from "lucide-react";

/** 文档块组件：显示文档标题、格式及下载链接 */
export function DocumentBlock({ content }: { content: Record<string, unknown> }) {
  const title = (content.title as string) || "文档";
  const format = (content.format as string) || "pdf";
  const url = (content.url as string) || "";
  const pageCount = content.page_count as number | undefined;

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 px-3 py-2">
      <div className="flex items-center gap-2">
        <FileText size={14} className="text-[var(--color-accent)] flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[var(--color-text)] truncate">{title}</div>
          <div className="text-[10px] text-[var(--color-text-muted)]">
            {format.toUpperCase()}
            {pageCount && ` · ${pageCount} 页`}
          </div>
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[var(--color-accent)] hover:underline flex-shrink-0"
          >
            下载
          </a>
        )}
      </div>
    </div>
  );
}
