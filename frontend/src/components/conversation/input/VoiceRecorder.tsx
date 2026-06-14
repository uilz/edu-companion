"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

// ── 组件 Props 接口 ──
interface VoiceRecorderProps {
  onTranscription: (text: string) => void; // 语音识别回调，返回转写文本
  disabled?: boolean;                       // 是否禁用录音按钮
}

// ── Web Speech API 类型声明（浏览器原生语音识别） ──
// SpeechRecognition 事件类型：携带识别结果
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

// SpeechRecognition 错误事件类型
interface SpeechRecognitionError extends Event {
  error: string;
  message: string;
}

// SpeechRecognition 实例接口定义
interface SpeechRecognition extends EventTarget {
  continuous: boolean;         // 是否持续监听
  interimResults: boolean;     // 是否返回中间结果
  lang: string;                // 识别语言
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionError) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

// 扩展全局 Window 类型，包含浏览器前缀的 SpeechRecognition
declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  }
}

// 录音组件的三种状态：空闲 / 录音中 / 处理中
type RecorderState = "idle" | "recording" | "processing";

// ── 主组件：VoiceRecorder（优先使用浏览器原生 Web Speech API） ──
export default function VoiceRecorder({ onTranscription, disabled }: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");      // 当前录音状态
  const [interimText, setInterimText] = useState("");             // 语音识别的中间结果（实时显示）
  const [error, setError] = useState("");                         // 错误提示信息
  const recognitionRef = useRef<SpeechRecognition | null>(null);  // 保存 SpeechRecognition 实例引用
  const stateRef = useRef<RecorderState>("idle");                 // 状态 ref，用于回调中获取最新状态（避免闭包陈旧值）
  const isSupported = typeof window !== "undefined" &&
    (!!window.SpeechRecognition || !!window.webkitSpeechRecognition); // 浏览器是否支持原生语音识别

  // 同步 state 到 ref，确保回调中能获取到最新状态
  useEffect(() => { stateRef.current = state; }, [state]);

  // ── 开始录音 ──
  const startRecording = useCallback(() => {
    setError("");
    setInterimText("");

    try {
      // 获取浏览器 SpeechRecognition 构造函数（兼容 webkit 前缀）
      const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognitionAPI) {
        setError("浏览器不支持语音识别");
        return;
      }

      const recognition = new SpeechRecognitionAPI();
      recognition.continuous = false;      // 不持续监听，一次识别完成后自动停止
      recognition.interimResults = true;   // 开启中间结果，实现实时字幕效果
      recognition.lang = "zh-CN";          // 识别语言设为中文

      // 语音识别结果回调
      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let final = "";
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            final += result[0].transcript;   // 最终结果
          } else {
            interim += result[0].transcript; // 中间临时结果
          }
        }
        if (final) {
          // 获取到最终结果后，清空中间文本，回调转写结果，恢复空闲状态
          setInterimText("");
          onTranscription(final);
          setState("idle");
        } else {
          // 只有中间结果时，实时更新显示
          setInterimText(interim);
        }
      };

      // 语音识别错误回调
      recognition.onerror = (event: SpeechRecognitionError) => {
        setError(event.error === "no-speech" ? "未检测到语音" : `识别失败: ${event.error}`);
        setState("idle");
      };

      // 语音识别结束回调
      recognition.onend = () => {
        // 使用 ref 获取当前状态，避免闭包捕获陈旧值
        if (stateRef.current === "recording") {
          setState("idle");
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
      setState("recording");
    } catch (e) {
      setError("语音识别启动失败");
      setState("idle");
    }
  }, [onTranscription]); // 不使用 state 依赖，通过 ref 替代

  // ── 停止录音 ──
  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    setState("idle");
  }, []);

  // ── 组件卸载时清理：中止语音识别 ──
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  // ── 如果浏览器不支持 Web Speech API，降级到 MediaRecorder 方案 ──
  if (!isSupported) {
    return <MediaRecorderFallback onTranscription={onTranscription} disabled={disabled} />;
  }

  // ── 渲染：语音按钮 + 状态提示 ──
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

      {/* 录音中指示器 */}
      {state === "recording" && (
        <div className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] bg-[#ef4444] text-white">
            <span className="w-1.5 h-1.5 bg-white animate-pulse" />
            录音中...
          </span>
        </div>
      )}

      {/* 语音识别中间结果预览 */}
      {interimText && (
        <span className="ml-2 text-xs text-[var(--color-text-muted)] italic max-w-[200px] truncate">
          {interimText}
        </span>
      )}

      {/* 错误提示 */}
      {error && (
        <span className="ml-2 text-[10px] text-[#ef4444]">{error}</span>
      )}
    </div>
  );
}

// ── 降级方案：MediaRecorder + Whisper API ──
// 当浏览器不支持 Web Speech API 时，使用 MediaRecorder 录制音频，
// 然后上传到后端的 Whisper API 进行转写。

function MediaRecorderFallback({ onTranscription, disabled }: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");         // 当前录音状态
  const [error, setError] = useState("");                            // 错误提示
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);       // MediaRecorder 实例引用
  const chunksRef = useRef<Blob[]>([]);                              // 录音数据块缓存

  // ── 开始录音（降级方案） ──
  const startRecording = useCallback(async () => {
    setError("");
    try {
      // 获取用户麦克风权限
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      // 每当有音频数据可用时，追加到缓存
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      // 录音停止后，释放麦克风资源，上传音频并转写
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
      setError("无法访问麦克风");
    }
  }, []);

  // ── 停止录音（降级方案） ──
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // ── 上传音频到 Whisper API 进行转写 ──
  const uploadAndTranscribe = async (blob: Blob) => {
    try {
      const formData = new FormData();
      formData.append("audio_file", blob, "recording.webm");
      const res = await authedFetch("/api/multimodal/transcribe", { method: "POST", body: formData });
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

  // ── 渲染：降级方案的 UI ──
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
