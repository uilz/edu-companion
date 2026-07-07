"use client";

import React, { useState, useEffect } from "react";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useMessageStore } from "@/store/conversation/message-store";

/**
 * StreamingControls — 流式回复控制按钮（简化版）
 *
 * 运行时：
 *  - 单击按钮：停止生成
 */
export default function StreamingControls() {
  const isLoading = useConversationStore((s) => s.isLoading);
  const [visible, setVisible] = useState(false);

  // 延迟显示，避免一闪而过
  useEffect(() => {
    if (isLoading) {
      const t = setTimeout(() => setVisible(true), 300);
      return () => clearTimeout(t);
    }
    setVisible(false);
  }, [isLoading]);

  if (!visible) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      <button
        type="button"
        onClick={() => useMessageStore.getState().stopGeneration()}
        className="
          inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
          transition-all select-none
          bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400
          active:scale-95
        "
        title="停止生成"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
          <rect x="3" y="3" width="10" height="10" rx="2" />
        </svg>
        <span>停止生成</span>
      </button>
    </div>
  );
}
