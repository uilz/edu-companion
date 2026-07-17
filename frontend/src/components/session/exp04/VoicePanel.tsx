"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { X, Mic, Square, Send } from "lucide-react";
import { sendChatMessage } from "@/lib/exp04/session-chat-api";

// ── Props ──────────────────────────────────────────────────

interface Props {
  convId?: string | null;
  sessionId?: string | null;
  open: boolean;
  onClose: () => void;
}

// ── Transcript line ───────────────────────────────────────

interface TranscriptLine {
  role: "ai" | "user";
  text: string;
  loading?: boolean;
}

// ── Quick reply presets ───────────────────────────────────

const AI_PRESETS = [
  "能帮我解释一下这个概念吗？",
  "给我举个例子",
  "我好像有点懂了",
];

const FALLBACK_PRESETS = [
  "我想介绍一下我自己",
  "今天天气怎么样",
  "我最近在学线性代数",
];

const FALLBACK_REPLY_MAP: Record<string, string> = {
  "我想介绍一下我自己": "Nice. It takes courage to introduce yourself in a new language. Where are you from?",
  "今天天气怎么样": "Good icebreaker. Do you prefer sunny or rainy days when you study?",
  "我最近在学线性代数": "Linear algebra. What part feels hardest right now?",
  "我在学递归": "Recursion! That's a fun one. What's your mental model for how it works?",
};

// ── Web Speech API type (browser only) ────────────────────

declare global {
  interface Window {
    SpeechRecognition?: typeof SpeechRecognition;
    webkitSpeechRecognition?: typeof SpeechRecognition;
  }
}

// ── Feature detection ─────────────────────────────────────

const supportsSTT = !!(
  typeof window !== "undefined" &&
  (window.SpeechRecognition || window.webkitSpeechRecognition)
);

const supportsTTS = !!(
  typeof window !== "undefined" && window.speechSynthesis
);

// ── Component ─────────────────────────────────────────────

export default function VoicePanel({ convId, sessionId, open, onClose }: Props) {
  const [speaking, setSpeaking] = useState(false);
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);        // STT in progress
  const [transcript, setTranscript] = useState<TranscriptLine[]>([
    { role: "ai", text: "还没开始。准备好了点下面的按钮。" },
  ]);
  const [manualInput, setManualInput] = useState("");        // text input fallback
  const [audioLevel, setAudioLevel] = useState(0);           // 0-1 for wave
  const aborterRef = useRef<AbortController | null>(null);
  const recognitionRef = useRef<InstanceType<typeof SpeechRecognition> | null>(null);
  const synthRef = useRef<SpeechSynthesisUtterance | null>(null);
  const audioCtxRef = useRef<AnalyserNode | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const hasRealAI = !!(convId && sessionId);

  // ── Cleanup on close ──

  useEffect(() => {
    if (!open) {
      stopListening();
      stopTTS();
      aborterRef.current?.abort();
    }
    return () => {
      stopListening();
      stopTTS();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // ── Audio wave animation (AnalyserNode) ──

  const startAudioWave = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      const ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      src.connect(analyser);
      audioCtxRef.current = analyser;

      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(data);
        const avg = Array.from(data).reduce((a, b) => a + b, 0) / data.length;
        setAudioLevel(Math.min(avg / 128, 1));
        animFrameRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // mic permission denied — wave stays at 0
    }
  }, []);

  const stopAudioWave = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    audioCtxRef.current = null;
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((t) => t.stop());
      audioStreamRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  // ── STT: Speech-to-Text ──

  const startListening = useCallback(() => {
    if (!supportsSTT) return;
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) return;

    const recognition = new SpeechRecognitionAPI();
    recognition.lang = "zh-CN";
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalText += event.results[i][0].transcript;
        }
      }
      if (finalText) {
        // User said something — send it
        setTranscript((prev) => [...prev, { role: "user", text: `🎤 ${finalText}` }]);
        if (hasRealAI) {
          sendToRealAI(finalText);
        } else {
          sendFallback(finalText);
        }
      }
    };

    recognition.onerror = () => {
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasRealAI]);

  const stopListening = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch { /* ignore */ }
    recognitionRef.current = null;
    setListening(false);
  }, []);

  // ── TTS: Text-to-Speech ──

  const speakText = useCallback((text: string) => {
    if (!supportsTTS) return;
    // Stop any current speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    synthRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, []);

  const stopTTS = useCallback(() => {
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  // ── Start conversation / listen ──

  const handleMicClick = useCallback(() => {
    if (speaking || listening) {
      stopTTS();
      stopListening();
      stopAudioWave();
      return;
    }

    if (supportsSTT) {
      startAudioWave();
      startListening();
    } else {
      // No STT — fall back to text-only mode
      setSpeaking(true);
      if (hasRealAI) {
        setTranscript((prev) => [
          ...prev,
          { role: "ai", text: "你好。今天想聊什么？（语音不可用，请用文字输入）" },
        ]);
      } else {
        setTranscript((prev) => [
          ...prev,
          { role: "ai", text: "Hello. Tell me, what are you studying these days?" },
        ]);
      }
    }
  }, [speaking, listening, supportsSTT, startAudioWave, startListening, stopTTS, stopListening, stopAudioWave, hasRealAI]);

  // ── Send message to real AI ──

  const sendToRealAI = useCallback((text: string) => {
    if (!convId || !sessionId || sending) return;
    setSending(true);
    stopTTS();
    setListening(false);

    const placeholderLine: TranscriptLine = { role: "ai", text: "", loading: true };
    setTranscript((prev) => [...prev, placeholderLine]);

    const ctrl = new AbortController();
    aborterRef.current = ctrl;

    let accumulated = "";

    sendChatMessage(convId, sessionId, text, {
      onChunk: (chunk) => {
        accumulated += chunk;
        setTranscript((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.loading) {
            copy[copy.length - 1] = { role: "ai", text: accumulated, loading: true };
          }
          return copy;
        });
      },
      onDone: () => {
        setTranscript((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.loading) {
            copy[copy.length - 1] = { role: "ai", text: accumulated, loading: false };
          }
          return copy;
        });
        setSending(false);
        aborterRef.current = null;
        // Speak the result
        if (supportsTTS && accumulated) {
          speakText(accumulated);
        }
      },
      onError: () => {
        setTranscript((prev) => prev.filter((_, i) => i !== prev.length - 1 || !prev[i].loading));
        setSending(false);
        aborterRef.current = null;
      },
    }, ctrl.signal);
  }, [convId, sessionId, sending, stopTTS, speakText]);

  // ── Send fallback (local) reply ──

  const sendFallback = useCallback((text: string) => {
    const reply = FALLBACK_REPLY_MAP[text] || "Interesting. Tell me more.";
    setTimeout(() => {
      setTranscript((prev) => [...prev, { role: "ai", text: reply }]);
      if (supportsTTS) speakText(reply);
    }, 600);
  }, [speakText]);

  // ── Handle quick reply click ──

  const handleQuickReply = useCallback((text: string) => {
    if (hasRealAI) {
      sendToRealAI(text);
    } else {
      sendFallback(text);
    }
  }, [hasRealAI, sendToRealAI, sendFallback]);

  // ── Handle manual text send (when STT unavailable) ──

  const handleManualSend = useCallback(() => {
    const text = manualInput.trim();
    if (!text) return;
    setManualInput("");
    setTranscript((prev) => [...prev, { role: "user", text }]);
    if (hasRealAI) {
      sendToRealAI(text);
    } else {
      sendFallback(text);
    }
  }, [manualInput, hasRealAI, sendToRealAI, sendFallback]);

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleManualSend();
    }
  }, [handleManualSend]);

  // ── Compute wave heights ──

  const aiThinking = transcript.some((t) => t.loading);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-surface rounded-2xl shadow-xl border border-border/50 w-full max-w-sm relative animate-in zoom-in-95 duration-300">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-ink-muted hover:text-ink-secondary transition-colors z-10"
          aria-label="关闭语音"
        >
          <X size={18} />
        </button>

        <div className="flex flex-col items-center p-6 pt-8">
          {/* Connection badges */}
          <div className="mb-3 flex items-center gap-2 flex-wrap justify-center">
            {hasRealAI && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent/10 text-xs text-accent font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                AI 对话
              </span>
            )}
            {supportsSTT && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-100 text-xs text-teal-700 font-medium">
                <Mic size={10} />
                语音识别
              </span>
            )}
            {supportsTTS && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-100 text-xs text-purple-700 font-medium">
                <span className="text-[10px]">🔊</span>
                语音朗读
              </span>
            )}
          </div>

          {/* Orb */}
          <div
            className="relative w-32 h-32 rounded-full grid place-items-center mb-6 transition-all duration-300"
            style={{
              background: listening
                ? "radial-gradient(circle at 30% 30%, #34d399, #059669)"
                : speaking
                  ? "radial-gradient(circle at 30% 30%, var(--color-accent), var(--color-accent-hover))"
                  : "rgba(160,160,171,0.15)",
            }}
          >
            {(speaking || listening) && (
              <>
                <span className="absolute inset-0 rounded-full border-2 border-accent/50 animate-ping" />
                <span className="absolute inset-0 rounded-full border-2 border-accent/30 animate-ping [animation-delay:0.6s]" />
              </>
            )}
            <span className="text-4xl drop-shadow-md select-none">
              {listening ? "🎤" : "🍎"}
            </span>
          </div>

          {/* Status */}
          <p className="text-base font-semibold text-ink-primary mb-1">
            {listening ? "我在听……" : aiThinking ? "苹果果在想……" : speaking ? "苹果果在说……" : "准备好了"}            </p>
          <p className="text-sm text-ink-muted mb-5">
            {listening ? "说出你想说的话" : aiThinking ? "稍等一下" : speaking ? "它在等你接话" : supportsSTT ? "点击麦克风说话" : "输入文字开始对话"}
          </p>

          {/* Wave — live audio level when listening, animated pulse otherwise */}
          <div className="flex items-center gap-[3px] h-8 mb-5">
            {Array.from({ length: 9 }).map((_, i) => {
              let h: number;
              if (listening && audioLevel > 0) {
                // Real audio level
                const factor = 0.5 + 0.5 * Math.sin((i / 9) * Math.PI);
                h = 4 + audioLevel * 24 * factor;
              } else if (speaking) {
                h = 4 + Math.sin(i * 0.8 + Date.now() * 0.003) * 12 + 8;
              } else {
                h = 4;
              }
              return (
                <span
                  key={i}
                  className={`w-[3px] rounded-full transition-all duration-150 ${
                    listening ? "bg-teal-500" : speaking ? "bg-accent" : "bg-ink-muted/30"
                  } ${speaking ? "animate-pulse" : ""}`}
                  style={{ height: `${Math.max(4, h)}px` }}
                />
              );
            })}
          </div>

          {/* Transcript */}
          <div className="w-full max-h-36 overflow-y-auto mb-4 bg-page rounded-xl p-3 border border-border/40 space-y-2">
            {transcript.map((line, i) => (
              <p key={i} className="text-sm leading-relaxed">
                <strong className={line.role === "ai" ? "text-accent" : "text-ink-secondary"}>
                  {line.role === "ai" ? "🍎 苹果果：" : "你："}
                </strong>
                {line.loading && !line.text ? (
                  <span className="inline-flex gap-1 ml-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-accent/60 animate-bounce" style={{ animationDelay: "300ms" }} />
                  </span>
                ) : (
                  line.text
                )}
              </p>
            ))}
          </div>

          {/* STT Mic button (when STT available) or text input */}
          {supportsSTT ? (
            <div className="flex items-center gap-3 mb-4">
              <button
                onClick={handleMicClick}
                disabled={sending}
                className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all ${
                  listening
                    ? "bg-teal-500 text-white shadow-md animate-pulse"
                    : speaking
                      ? "bg-ink-primary text-white hover:opacity-90"
                      : "bg-accent text-white shadow-md hover:opacity-90"
                } disabled:opacity-50`}
              >
                {listening ? (
                  <>
                    <Mic size={14} />
                    聆听中...
                  </>
                ) : speaking ? (
                  <>
                    <Square size={14} fill="currentColor" />
                    停止朗读
                  </>
                ) : (
                  <>
                    <Mic size={14} />
                    开始说话
                  </>
                )}
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2.5 rounded-full border border-border/60 text-ink-secondary text-sm hover:bg-surface-hover transition-colors"
              >
                结束
              </button>
            </div>
          ) : (
            /* Text input fallback (when STT not available) */
            <div className="w-full flex items-center gap-2 mb-4">
              <input
                type="text"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="输入你想说的话..."
                disabled={sending}
                className="flex-1 px-3 py-2 text-sm bg-page border border-border/60 rounded-xl outline-none focus:border-accent transition-colors disabled:opacity-50"
              />
              <button
                onClick={handleManualSend}
                disabled={!manualInput.trim() || sending}
                className="w-9 h-9 rounded-full bg-accent text-white grid place-items-center hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                <Send size={14} />
              </button>
            </div>
          )}

          {/* Quick replies (only when not listening and not waiting for AI) */}
          {!listening && !aiThinking && (
            <div className="flex flex-wrap gap-2 justify-center">
              {(hasRealAI ? AI_PRESETS : FALLBACK_PRESETS).map((text) => (
                <button
                  key={text}
                  onClick={() => handleQuickReply(text)}
                  disabled={sending}
                  className="px-3 py-1.5 rounded-full border border-border/50 text-xs text-ink-secondary hover:bg-surface-hover hover:border-ink-muted transition-colors disabled:opacity-40"
                >
                  {text}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
