import { BookOpen } from "lucide-react";
import { useRenderedContent } from "@/lib/hooks/useRenderedContent";
import { sanitizeHtml } from "@/lib/utils/sanitize";

/** 纯文本块组件：渲染 Markdown/数学公式 转换后的 HTML，并显示引用来源 */
export function TextBlock({ content, sources }: { content: Record<string, unknown>; sources?: string[] }) {
  const text = (content.text as string) || "";
  const renderedHtml = useRenderedContent(text);

  return (
    <div>
      <div
        className="message-content text-base leading-[1.65] [&_p]:mb-2 [&_p:last-child]:mb-0"
        dangerouslySetInnerHTML={{ __html: sanitizeHtml(renderedHtml) }}
      />
      {sources && sources.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="flex flex-wrap gap-1.5">
            {sources.map((s, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] bg-[var(--color-accent)]/10 text-[var(--color-accent)] border border-[var(--color-accent)]/20 active:scale-[0.97] transition-transform"
              >
                <BookOpen size={10} />
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
