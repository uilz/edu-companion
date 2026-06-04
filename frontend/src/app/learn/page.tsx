"use client";

import { useState, useEffect, useCallback } from "react";
import { useConversation } from "@/components/conversation/useConversation";
import ConversationPanel from "@/components/conversation/ConversationPanel";
import FocusModePanel from "@/components/conversation/FocusModePanel";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

const FOCUS_KEY = "learn-focus-mode";

export default function LearnPage() {
  const [focusMode, setFocusMode] = useState<boolean>(false);
  const [init, setInit] = useState(false);
  const conv = useConversation();

  // Restore focus mode state on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(FOCUS_KEY);
      if (saved === "true") setFocusMode(true);
    } catch {}
    setInit(true);
  }, []);

  // Persist focus mode changes
  const toggleFocus = useCallback((on: boolean) => {
    setFocusMode(on);
    try { localStorage.setItem(FOCUS_KEY, on ? "true" : "false"); } catch {}
  }, []);

  if (!init) return null;

  return (
    <ErrorBoundary>
      {focusMode ? (
        <FocusModePanel onExitFocusMode={() => toggleFocus(false)} />
      ) : (
        <ConversationPanel {...conv} onEnterFocusMode={() => toggleFocus(true)} />
      )}
    </ErrorBoundary>
  );
}
