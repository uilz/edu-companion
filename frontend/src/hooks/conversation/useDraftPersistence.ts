"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const STORAGE_KEY = "chat_draft";
const SAVE_DEBOUNCE_MS = 300;

/**
 * useDraftPersistence — 对话输入框草稿持久化
 *
 * 固定 key 存 localStorage，刷新/关闭自动恢复。
 * 不受 conversationId 影响，任何时候都用同一份草稿。
 *
 * @returns [text, setText, clearDraft]
 */
export function useDraftPersistence(): [string, React.Dispatch<React.SetStateAction<string>>, () => void] {
  const [text, setText] = useState<string>("");

  // ── 挂载时从 localStorage 恢复 ──
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved != null) {
        setText(saved);
      }
    } catch {
      // localStorage 不可用，静默忽略
    }
  }, []);

  // ── 防抖自动保存（正常输入时） ──
  const textRef = useRef(text);
  textRef.current = text;
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, text);
      } catch {
        // 静默失败
      }
    }, SAVE_DEBOUNCE_MS);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [text]);

  // ── beforeunload / 卸载时同步保存（确保刷新不丢） ──
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saveSync = () => {
      try {
        localStorage.setItem(STORAGE_KEY, textRef.current);
      } catch {
        // 静默失败
      }
    };
    window.addEventListener("beforeunload", saveSync);
    return () => {
      window.removeEventListener("beforeunload", saveSync);
      saveSync(); // React 卸载时也保存
    };
  }, []);

  // ── 清空草稿 ──
  const clearDraft = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // 静默失败
    }
    setText("");
  }, []);

  return [text, setText, clearDraft];
}
