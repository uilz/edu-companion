"use client";

import { useEffect, useRef, useMemo } from "react";
import { renderMarkdown } from "@/lib/math";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export default function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  const ref = useRef<HTMLDivElement>(null);

  const renderedContent = useMemo(() => {
    // renderMarkdown already handles LaTeX internally (Steps 2 & 5 of pipeline).
    // Calling renderMath first → renderMarkdown destroys KaTeX HTML (Step 3 HTML-escapes < >).
    return renderMarkdown(content);
  }, [content]);

  const time = new Date(timestamp).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[80%] px-4 py-3 ${
          isUser
            ? "bg-[var(--color-accent)] text-[#ffffff]"
            : "bg-[var(--color-surface)] text-[var(--color-text)]"
        }`}
      >
        <div
          ref={ref}
          className="message-content text-sm leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0"
          dangerouslySetInnerHTML={{ __html: renderedContent }}
        />
        <div
          className={`text-[10px] mt-1 ${
            isUser ? "text-[#ffffff]/50 text-right" : "text-[var(--color-text-muted)]"
          }`}
        >
          {time}
        </div>
      </div>
    </div>
  );
}
