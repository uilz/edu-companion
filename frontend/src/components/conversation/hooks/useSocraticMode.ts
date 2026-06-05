"use client";

import { useState, useMemo, useEffect, useCallback } from "react";

/**
 * useSocraticMode — 苏格拉底模式状态管理 hook
 *
 * 封装了专注模式中的苏格拉底追问逻辑：
 * - socraticEnabled: 全局开关（从设置页读取）
 * - followUpMode: "ask" = 用户问 AI, "answer" = 用户回答 AI 的追问
 * - hasPendingQuestion: 检测 AI 最后一条消息是否以问号结尾
 * - handleSendWithSocratic: 自动添加 [回答追问] 前缀的发送函数
 */
export function useSocraticMode(
  messages: { role: string; text_summary?: string; content_blocks?: { text?: string }[] }[],
  sendMessage: (text: string) => void,
  socraticEnabled: boolean = false,
) {
  const [followUpMode, setFollowUpMode] = useState<"ask" | "answer">("ask");

  // 检测 AI 最后一条消息是否以问号/？结尾
  const hasPendingQuestion = useMemo(() => {
    if (!socraticEnabled) return false;
    const aiMessages = messages.filter((m) => m.role === "assistant");
    if (aiMessages.length === 0) return false;
    const last = aiMessages[aiMessages.length - 1];
    const text =
      last.text_summary ||
      last.content_blocks?.map((b) => b.text || "").join(" ") ||
      "";
    return /[？?]\s*$/.test(text) || /\n\n.*[？?]\s*$/.test(text);
  }, [messages, socraticEnabled]);

  // 自动切换追问模式
  useEffect(() => {
    setFollowUpMode(hasPendingQuestion ? "answer" : "ask");
  }, [hasPendingQuestion]);

  // 发送消息（带苏格拉底前缀）
  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      if (!socraticEnabled) {
        sendMessage(text.trim());
        return;
      }
      const payload =
        followUpMode === "answer" && hasPendingQuestion
          ? `[回答追问] ${text.trim()}`
          : text.trim();
      sendMessage(payload);
    },
    [sendMessage, followUpMode, hasPendingQuestion, socraticEnabled],
  );

  return {
    socraticEnabled,
    followUpMode,
    setFollowUpMode,
    hasPendingQuestion,
    handleSend,
  };
}
