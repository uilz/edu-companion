"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
  disabled?: boolean;
}

// Web Speech API type declarations
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionError extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionError) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  }
}

type RecorderState = "idle" | "recording" | "processing";

export default function VoiceRecorder({ onTranscription, disabled }: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [interimText, setInterimText] = useState("");
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const isSupported = typeof window !== "undefined" &&
    (!!window.SpeechRecognition || !!window.webkitSpeechRecognition);

  const startRecording = useCallback(() => {
    setError("");
    setInterimText("");

    try {
      const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognitionAPI) {
        setError("浏览器不支持语音识别");
        return;
      }

      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "zh-CN";

      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let final = "";
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            final += result[0].transcript;
          } else {
            interim += result[0].transcript;
          }
        }
        if (final) {
          setInterimText("");
          onTranscription(final);
          setState("idle");
        } else {
          setInterimText(interim);
        }
      };

      recognition.onerror = (event: SpeechRecognitionError) => {
        console.error("Speech recognition error:", event.error);
        setError(event.error === "no-speech" ? "未检测到语音" : `识别失败: ${event.error}`);
        setState("idle");
      };

      recognition.onend = () => {
        if (state === "recording") {
          setState("idle");
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
      setState("recording");
    } catch (e) {
      console.error("Failed to start speech recognition:", e);
      setError("语音识别启动失败");
      setState("idle");
    }
  }, [onTranscription, state]);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setState("idle");
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  if (!isSupported) {
    return <MediaRecorderFallback onTranscription={onTranscription} disabled={disabled} />;
  }

  return (
    <div className="relative inline-flex items-center">
      <button
        onClick={state === "recording" ? stopRecording : startRecording}
        disabled={disabled || state === "processing"}
        className={`p-1.5 transition-all duration-200 disabled:opacity-30 ${
          state === "recording"
            ? "text-[#ef4444] bg-[#ef4444]/10 animate-pulse"
            : "text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)]"
        }`}
        title={state === "recording" ? "点击停止录音" : "语音输入"}
      >
        {state === "processing" ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Mic size={16} />
        )}
      </button>

      {/* Recording indicator */}
      {state === "recording" && (
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] bg-[#ef4444] text-white">
            <span className="w-1.5 h-1.5 bg-white animate-pulse" />
            录音中...
          </span>
        </div>
      )}

      {/* Interim text preview */}
      {interimText && (
        <span className="ml-2 text-xs text-[var(--color-text-muted)] italic max-w-[200px] truncate">
          {interimText}
        </span>
      )}

      {/* Error toast */}
      {error && (
        <span className="ml-2 text-[10px] text-[#ef4444]">{error}</span>
      )}
    </div>
  );
}

// ── Channel B: MediaRecorder → Whisper API fallback ──

function MediaRecorderFallback({ onTranscription, disabled }: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [error, setError] = useState("");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("processing");
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await uploadAndTranscribe(blob);
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setState("recording");
    } catch (e) {
      console.error("MediaRecorder error:", e);
      setError("无法访问麦克风");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const uploadAndTranscribe = async (blob: Blob) => {
    try {
      const formData = new FormData();
      formData.append("audio_file", blob, "recording.webm");
      const res = await fetch("/api/multimodal/transcribe", { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "转写失败");
      }
      const data = await res.json();
      onTranscription(data.transcription);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setState("idle");
    }
  };

  return (
    <div className="relative inline-flex items-center">
      <button
        onClick={state === "recording" ? stopRecording : startRecording}
        disabled={disabled || state === "processing"}
        className={`p-1.5 transition-all duration-200 disabled:opacity-30 ${
          state === "recording"
            ? "text-[#ef4444] bg-[#ef4444]/10 animate-pulse"
            : "text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)]"
        }`}
        title={state === "recording" ? "点击停止" : "语音输入（上传模式）"}
      >
        {state === "processing" ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Mic size={16} />
        )}
      </button>
      {state === "recording" && (
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] bg-[#ef4444] text-white">
            <span className="w-1.5 h-1.5 bg-white animate-pulse" />
            录音中...
          </span>
        </div>
      )}
      {state === "processing" && (
        <span className="ml-2 text-xs text-[var(--color-text-muted)]">转写中...</span>
      )}
      {error && (
        <span className="ml-2 text-[10px] text-[#ef4444]">{error}</span>
      )}
    </div>
  );
}
