"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Volume2, VolumeX } from "lucide-react";

interface SpeakButtonProps {
  text: string;
  minLength?: number;
}

/** Premium Chinese voices (ordered by quality) */
const PREFERRED_VOICES = [
  "Microsoft Xiaoxiao",       // Win 11 — 最自然
  "Microsoft Yunxi",          // Win 11
  "Microsoft Xiaohan",        // Win 10+
  "Google 普通话",            // Chrome Android
  "Tingting",                 // macOS
  "Sin-Ji",                   // macOS Cantonese fallback
];

export default function SpeakButton({ text, minLength = 200 }: SpeakButtonProps) {
  const [speaking, setSpeaking] = useState(false);
  const [bestVoice, setBestVoice] = useState<SpeechSynthesisVoice | null>(null);
  const isSupported = typeof window !== "undefined" && !!window.speechSynthesis;
  const voicesLoaded = useRef(false);

  // Load voices and pick the best Chinese one
  useEffect(() => {
    if (!isSupported || voicesLoaded.current) return;

    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) return;
      voicesLoaded.current = true;

      // Try preferred voices first
      for (const name of PREFERRED_VOICES) {
        const found = voices.find(v => v.name.includes(name) && v.lang.startsWith("zh"));
        if (found) {
          setBestVoice(found);
          return;
        }
      }
      // Fallback: any Chinese voice
      const anyChinese = voices.find(v => v.lang.startsWith("zh"));
      if (anyChinese) setBestVoice(anyChinese);
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, [isSupported]);

  const speak = useCallback(() => {
    if (!isSupported || !text) return;

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    // Strip Markdown for cleaner TTS
    const cleanText = text
      .replace(/[#*_~`>[\]()]/g, "")
      .replace(/\$\$[\s\S]*?\$\$/g, "")   // remove display math
      .replace(/\$[^$\n]+?\$/g, "")        // remove inline math
      .replace(/\n{2,}/g, "。")
      .replace(/\n/g, "，")
      .substring(0, 500);  // limit length

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = "zh-CN";
    utterance.rate = 0.95;   // slightly slower = more natural
    utterance.pitch = 1.0;

    if (bestVoice) {
      utterance.voice = bestVoice;
    }

    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [text, speaking, isSupported, bestVoice]);

  if (!isSupported || text.length < minLength) return null;

  return (
    <button
      onClick={speak}
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] transition-colors ${
        speaking
          ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
          : "text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
      }`}
      title={speaking ? "停止朗读" : `朗读${bestVoice ? ` (${bestVoice.name})` : ""}`}
    >
      {speaking ? <VolumeX size={12} /> : <Volume2 size={12} />}
      {speaking ? "停止" : "朗读"}
    </button>
  );
}
