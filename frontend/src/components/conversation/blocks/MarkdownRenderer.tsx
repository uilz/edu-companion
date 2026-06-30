"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeSlug from "rehype-slug";
import rehypeSentenceSegment from "@/lib/rehype-sentence-segment";
import CodeBlock from "@/components/CodeBlock";
import MermaidBlock from "@/components/MermaidBlock";
import "katex/dist/katex.min.css";

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <div className="prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeSlug, rehypeSentenceSegment]}
        components={{
          // ── 代码块 ──
          code: ({ className: cls, children: codeChildren, ...props }) => {
            const isInline = !cls;
            if (isInline) {
              return (
                <code
                  className="bg-[var(--color-surface-hover)] px-1 py-0.5 rounded text-xs"
                  {...props}
                >
                  {codeChildren}
                </code>
              );
            }
            const match = /language-(\w+)/.exec(cls || "");
            const lang = match ? match[1] : "";
            const value = String(codeChildren).replace(/\n$/, "");

            // Mermaid 图表
            if (lang === "mermaid") {
              return <MermaidBlock chart={value} />;
            }

            return <CodeBlock language={lang} value={value} />;
          },

          // ── 表格 ──
          table: ({ children: tblChildren }) => (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full border-collapse border border-[var(--color-border)] text-xs">
                {tblChildren}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => (
            <th className="border border-[var(--color-border)] bg-[var(--color-surface-hover)] px-2 py-1.5 text-left font-medium whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-[var(--color-border)] px-2 py-1">
              {children}
            </td>
          ),

          // ── 图片 ──
          img: ({ src, alt }) => {
            if (!src || src.trim() === "") return null;
            if (src.startsWith("data:") && src.endsWith("...")) return null;
            if (
              src === "data:image/png;base64..." ||
              src === "()" ||
              src === "("
            )
              return null;
            return (
              <img
                src={src}
                alt={alt || ""}
                className="max-w-full h-auto rounded my-1"
                loading="lazy"
              />
            );
          },

          // ── 段落 ──
          p: ({ children }) => <p className="my-1">{children}</p>,

          // ── GFM 任务列表 ──
          li: ({ children, ...props }) => {
            const input = (props as any)?.checked;
            if (typeof input === "boolean") {
              return (
                <li className="list-none -ml-1">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={input}
                      readOnly
                      className="accent-[var(--color-accent)]"
                    />
                    <span>{children}</span>
                  </label>
                </li>
              );
            }
            return <li>{children}</li>;
          },

          // ── 标题 ──
          h1: ({ children }) => (
            <h1 className="text-lg font-bold mt-4 mb-2">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-bold mt-3 mb-1.5">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-sm font-semibold mt-1.5 mb-1">{children}</h4>
          ),
          h5: ({ children }) => (
            <h5 className="text-xs font-medium mt-1 mb-0.5">{children}</h5>
          ),
          h6: ({ children }) => (
            <h6 className="text-xs font-medium mt-1 mb-0.5">{children}</h6>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
