"use client";

import { Lightbulb, Loader2, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
// katex/dist/katex.min.css 已在 app/globals.css 统一 import

interface Props {
  hintText: string;
  loading?: boolean;
  visible: boolean;
  onClose: () => void;
}

/** 提示面板 */
export default function HintPanel({ hintText, loading, visible, onClose }: Props) {
  if (!visible) return null;

  return (
    <div className="rounded-xl bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 p-4">
      <div className="flex items-start gap-2">
        <Lightbulb size={14} className="text-blue-500 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-medium text-blue-600 dark:text-blue-400">提示</span>
            <button onClick={onClose} className="p-0.5 rounded hover:bg-blue-100 dark:hover:bg-blue-800 text-blue-400">
              <X size={12} />
            </button>
          </div>
          {loading ? (
            <Loader2 size={14} className="animate-spin text-blue-400" />
          ) : (
            <p className="text-[12px] text-[var(--color-text-muted)] leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                {hintText}
              </ReactMarkdown>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
