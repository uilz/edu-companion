"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeSlug from "rehype-slug";
import CodeBlock from "@/components/CodeBlock";
import MermaidBlock from "@/components/MermaidBlock";

// ── 文本预处理器：在传给 react-markdown 之前清理常见问题 ──
function preprocess(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // 1. 「**标题** |  |  | 」→ 去掉非表格行的尾部多个 |
    if (!line.trimStart().startsWith("|") && line.trimEnd().endsWith("|")) {
      line = line.replace(/\s*\|+$/, "");
    }

    out.push(line);
  }

  return out.join("\n");
}

export default function MarkdownRenderer({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  const cleaned = preprocess(children);

  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeSlug]}
        components={{
          // ── 代码块: 内联 vs 代码块（含语法高亮 / Mermaid） ──
          code: ({ className: cls, children: codeChildren, ...props }) => {
            const isInline = !cls;
            if (isInline) {
              return (
                <code
                  className="bg-surface-hover px-1 py-0.5 rounded text-xs"
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

          // ── 表格: 响应式容器 + 边框 ──
          table: ({ children: tblChildren }) => (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full border-collapse border border text-xs">
                {tblChildren}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => (
            <th className="border border bg-surface-hover px-2 py-1.5 text-left font-medium whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border px-2 py-1">
              {children}
            </td>
          ),

          // ── 图片: 跳过空/无效 src ──
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

          // ── 段落: 紧凑间距 ──
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
                      className="accent-accent"
                    />
                    <span>{children}</span>
                  </label>
                </li>
              );
            }
            return <li>{children}</li>;
          },

          // ── 标题: 紧凑间距 ──
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
        {cleaned}
      </ReactMarkdown>
    </div>
  );
}
