"use client";

import React, { useMemo } from "react";
import katex from "katex";
import { Message } from "@/types";
import { User, Bot } from "lucide-react";

interface ChatMessageProps {
  message: Message;
}

function renderMarkdown(content: string): string {
  let html = content;

  // Code blocks (must be before inline code)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang: string, code: string) => {
    const escaped = code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return `<pre><code class="language-${lang}">${escaped}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // KaTeX: display mode $$...$$
  html = html.replace(/\$\$([\s\S]+?)\$\$/g, (_match, tex: string) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false });
    } catch {
      return `<code>${tex}</code>`;
    }
  });

  // KaTeX: inline mode $...$
  html = html.replace(/\$([^\$\n]+?)\$/g, (_match, tex: string) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false });
    } catch {
      return `<code>${tex}</code>`;
    }
  });

  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Italic
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Blockquote
  html = html.replace(/^>\s(.+)$/gm, "<blockquote>$1</blockquote>");

  // Unordered lists
  html = html.replace(/^[*-]\s(.+)$/gm, "<li>$1</li>");
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");

  // Ordered lists
  html = html.replace(/^\d+\.\s(.+)$/gm, "<li>$1</li>");

  // Paragraphs (double newline)
  html = html.replace(/\n\n/g, "</p><p>");
  // Single newlines -> br (but not inside pre)
  html = html.replace(/(?<!<\/pre>)\n/g, "<br/>");

  // Wrap in paragraph if not already
  if (!html.startsWith("<")) {
    html = "<p>" + html + "</p>";
  }

  return html;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  const renderedContent = useMemo(() => {
    return renderMarkdown(message.content);
  }, [message.content]);

  return (
    <div className={`flex gap-3 px-4 py-5 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-bg-tertiary)] flex items-center justify-center">
          <Bot size={18} className="text-[var(--color-accent)]" />
        </div>
      )}

      <div
        className={`max-w-[85%] sm:max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed message-content ${
          isUser
            ? "bg-[var(--color-user-bubble)] text-[var(--color-text-primary)] rounded-br-md"
            : "bg-[var(--color-assistant-bubble)] text-[var(--color-text-primary)] rounded-bl-md"
        }`}
        dangerouslySetInnerHTML={{ __html: renderedContent }}
      />

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-accent)] flex items-center justify-center">
          <User size={18} className="text-white" />
        </div>
      )}
    </div>
  );
}
