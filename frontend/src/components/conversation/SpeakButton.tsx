"use client";

import { useState, useCallback } from "react";
import { Volume2, VolumeX } from "lucide-react";

interface SpeakButtonProps {
  text: string;
  /** Only show button if text exceeds this length (default 200 chars) */
  minLength?: number;
}

export default function SpeakButton({ text, minLength = 200 }: SpeakButtonProps) {
  const [speaking, setSpeaking] = useState(false);
  const isSupported = typeof window !== "undefined" && !!window.speechSynthesis;

  const speak = useCallback(() => {
    if (!isSupported || !text) return;

    // If already speaking, cancel
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    // Strip Markdown for cleaner TTS
    const cleanText = text
      .replace(/[#*_~`>\[\]()]/g, "")
      .replace(/\n{2,}/g, "。")
      .replace(/\n/g, "，");

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = "zh-CN";
    utterance.rate = 1.05;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [text, speaking, isSupported]);

  // Don't render if too short or not supported
  if (!isSupported || text.length < minLength) return null;

  return (
    <button
      onClick={speak}
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] transition-colors ${
        speaking
          ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
          : "text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
      }`}
      title={speaking ? "停止朗读" : "朗读此消息"}
    >
      {speaking ? <VolumeX size={12} /> : <Volume2 size={12} />}
      {speaking ? "停止" : "朗读"}
    </button>
  );
}
