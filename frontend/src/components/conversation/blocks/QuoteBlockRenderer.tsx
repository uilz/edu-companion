"use client";

import React from "react";
import { Quote } from "lucide-react";
import { useRenderedContent } from "@/hooks/useRenderedContent";
import { sanitizeHtml } from "@/lib/utils/sanitize";

interface Props {
  quotedText: string;
  sourceConversationId?: string;
  sourceMessageId?: string;
}

function QuoteBlockRenderer({ quotedText, sourceConversationId, sourceMessageId }: Props) {
  const html = useRenderedContent(quotedText);
  const plainText = quotedText.length > 200 ? quotedText.slice(0, 200) + "…" : quotedText;

  return (
    <div
      className="flex items-start gap-2.5 px-3.5 py-3 mb-2 rounded-lg
                 bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/20
                 border-l-[4px] border-l-amber-500 dark:border-l-amber-400
                 text-sm cursor-default select-text"
      title={plainText}
    >
      <Quote size={16} className="shrink-0 mt-0.5 text-[var(--color-warning)] dark:text-[var(--color-warning)]" />
      <div className="flex-1 min-w-0">
        <div
          className="text-[var(--color-warning)] dark:text-[var(--color-warning)] text-[13px] leading-relaxed break-words
                     [&_p]:mb-1 [&_p:last-child]:mb-0
                     [&_pre]:bg-[var(--color-warning)]/10 [&_pre]:rounded [&_pre]:p-2 [&_pre]:text-xs
                     [&_code]:bg-[var(--color-warning)]/10 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs
                     [&_.katex]:text-[var(--color-warning)] dark:[&_.katex]:text-[var(--color-warning)]
                     [&_strong]:font-semibold [&_em]:italic"
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }}
        />
        <span className="text-[10px] text-[var(--color-warning)] dark:text-[var(--color-warning)] mt-1 block font-medium">
          📌 引用自上文
        </span>
      </div>
    </div>
  );
}

export default React.memo(QuoteBlockRenderer);
