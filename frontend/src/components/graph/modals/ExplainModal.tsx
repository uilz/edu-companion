"use client";

import React, { useState } from "react";
import { Lightbulb, X, Send } from "lucide-react";

interface ExplainModalProps {
  open: boolean;
  originalText: string;
  onClose: () => void;
  onSave: (explanation: string) => void;
}

export default function ExplainModal({
  open,
  originalText,
  onClose,
  onSave,
}: ExplainModalProps) {
  const [explanation, setExplanation] = useState("");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 bg-surface border border rounded-xl shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border">
          <div className="flex items-center gap-2">
            <Lightbulb size={16} className="text-accent" />
            <span className="text-sm font-medium">用自己的话解释</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-hover text-muted"
          >
            <X size={14} />
          </button>
        </div>

        {/* Selected text */}
        <div className="px-4 py-3 bg-accent/5 border-b border/50">
          <p className="text-xs text-muted mb-1">原文：</p>
          <p className="text-sm text italic leading-relaxed">
            &ldquo;{originalText}&rdquo;
          </p>
        </div>

        {/* Input area */}
        <div className="px-4 py-3">
          <p className="text-xs text-muted mb-2">
            试着用自己的话重新解释上面这段内容。这能帮助你检查是否真正理解了。
          </p>
          <textarea
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            placeholder="输入你的理解..."
            className="w-full h-28 px-3 py-2 text-sm rounded-lg border border bg-page resize-none focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition-colors"
            autoFocus
          />
          <div className="flex justify-end mt-2">
            <button
              onClick={() => {
                if (explanation.trim()) {
                  onSave(explanation.trim());
                  setExplanation("");
                  onClose();
                }
              }}
              disabled={!explanation.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              <Send size={12} />
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
