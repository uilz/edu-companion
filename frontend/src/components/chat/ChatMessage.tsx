"use client";

import { useEffect, useRef, useMemo } from "react";
import katex from "katex";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

function renderMarkdown(text: string): string {
  let html = text;
  // Escape HTML
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
  });
  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Line breaks to paragraphs
  html = html
    .split("\n\n")
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");
  return html;
}

function renderLatex(text: string): string {
  // Display math: $$ ... $$
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: true,
        throwOnError: false,
      });
    } catch {
      return formula;
    }
  });
  // Inline math: $ ... $
  result = result.replace(/\$([^\$\n]+?)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: false,
        throwOnError: false,
      });
    } catch {
      return formula;
    }
  });
  return result;
}

export default function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  const ref = useRef<HTMLDivElement>(null);

  const renderedContent = useMemo(() => {
    const withLatex = renderLatex(content);
    return renderMarkdown(withLatex);
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
