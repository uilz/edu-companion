"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Volume2, Pause, Play } from "lucide-react";
import { authedFetch } from "@/lib/api/api";

type PlayState = "idle" | "playing" | "paused";

const PREFERRED_VOICES = [
  "Microsoft Xiaoxiao", "Microsoft Yunxi", "Microsoft Xiaohan",
  "Google 普通话", "Tingting", "Sin-Ji",
];

// ── 全局音频单例（冲突管理）──
// 任意时刻只有一条消息在播放
let _activeKey: string | null = null;
let _activeStop: (() => void) | null = null;
let _activeCleanup: (() => void) | null = null;

function acquireAudio(key: string, stop: () => void) {
  if (_activeKey !== null && _activeKey !== key) {
    // 停掉上一条
    _activeStop?.();
    _activeCleanup?.();
  }
  _activeKey = key;
  _activeStop = stop;
}

function releaseAudio(key: string) {
  if (_activeKey === key) {
    _activeKey = null;
    _activeStop = null;
    _activeCleanup = null;
  }
}

function setAudioCleanup(key: string, cleanup: () => void) {
  if (_activeKey === key) _activeCleanup = cleanup;
}

// ── 进度 Map ──
const progressMap = new Map<string, number>();

function textHash(text: string): string { return `tts_${text.length}_${text.slice(0, 20)}`; }

interface SpeakButtonProps {
  text: string;
  minLength?: number;
}

/**
 * SpeakButton 语音朗读按钮
 *
 * 单击 = 播放/暂停（进度保留）
 * 双击 = 停止+重置
 * 全局单例：新消息朗读时自动停掉上一条
 */
export default function SpeakButton({ text, minLength = 50 }: SpeakButtonProps) {
  const key = textHash(text);
  const [playState, setPlayState] = useState<PlayState>("idle");

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlRef = useRef<string | null>(null);
  const textRef = useRef(text);
  const lastClickRef = useRef(0);
  const isFetchingRef = useRef(false);
  const mountedRef = useRef(true);
  textRef.current = text;

  // ── 语音列表 ──
  const [bestVoice, setBestVoice] = useState<SpeechSynthesisVoice | null>(null);
  const isSupported = typeof window !== "undefined" && !!window.speechSynthesis;
  const voicesLoaded = useRef(false);

  useEffect(() => {
    if (!isSupported || voicesLoaded.current) return;
    const load = () => {
      const voices = window.speechSynthesis.getVoices();
      if (!voices.length) return;
      voicesLoaded.current = true;
      for (const name of PREFERRED_VOICES) {
        const f = voices.find(v => v.name.includes(name) && v.lang.startsWith("zh"));
        if (f) { setBestVoice(f); return; }
      }
      const anyCn = voices.find(v => v.lang.startsWith("zh"));
      if (anyCn) setBestVoice(anyCn);
    };
    load();
    window.speechSynthesis.onvoiceschanged = load;
  }, [isSupported]);

  // ── 暂停当前音频（不重置进度）──
  const pauseAudio = useCallback(() => {
    if (audioRef.current) audioRef.current.pause();
    if (isSupported) window.speechSynthesis.pause?.();
  }, [isSupported]);

  // ── 停止当前音频（重置进度到 0）──
  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      try { audioRef.current.currentTime = 0; } catch {}
    }
    if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null; }
    audioRef.current = null;
    if (isSupported) window.speechSynthesis.cancel();
    progressMap.delete(key);
  }, [isSupported, key]);

  // ── 清理辅助 ──
  const cleanupUrl = useCallback(() => {
    if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null; }
    audioRef.current = null;
  }, []);

  // ── 拉取并播放 ──
  const fetchAndPlay = useCallback(async (seekTo: number = 0) => {
    if (isFetchingRef.current || !mountedRef.current) return;
    isFetchingRef.current = true;

    try {
      const res = await authedFetch("/api/multimodal/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textRef.current, voice: "zh-CN-XiaoxiaoNeural" }),
      });
      if (!res.ok) throw new Error("TTS failed");
      if (!mountedRef.current) return;

      const blob = await res.blob();
      if (!mountedRef.current) return;

      const url = URL.createObjectURL(blob);
      cleanupUrl();
      blobUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;

      // seek（需等元数据）
      if (seekTo > 0) {
        await new Promise<void>((resolve) => {
          audio.onloadedmetadata = () => resolve();
          audio.onerror = () => resolve();
          setTimeout(resolve, 1000);
        });
        if (!mountedRef.current) return;
        try { audio.currentTime = seekTo; } catch {}
      }

      // 进度上报
      audio.ontimeupdate = () => {
        const a = audioRef.current;
        if (a && a.duration && a.duration > 0 && a.duration < 3600) {
          progressMap.set(key, a.currentTime);
        }
      };

      audio.onended = () => {
        cleanupUrl();
        progressMap.delete(key);
        releaseAudio(key);
        if (mountedRef.current) setPlayState("idle");
      };

      audio.onerror = () => {
        cleanupUrl();
        releaseAudio(key);
        if (mountedRef.current) setPlayState("idle");
      };

      // ── 注册到全局单例 ──
      acquireAudio(key, stopAudio);
      setAudioCleanup(key, () => {
        cleanupUrl();
        releaseAudio(key);
        if (mountedRef.current) setPlayState("idle");
      });

      if (!mountedRef.current) return;
      setPlayState("playing");
      await audio.play();
    } catch {
      cleanupUrl();
      releaseAudio(key);
      if (mountedRef.current) setPlayState("idle");
    } finally {
      isFetchingRef.current = false;
    }
  }, [cleanupUrl, key, stopAudio]);

  // ── 浏览器 TTS ──
  const speakBrowser = useCallback(() => {
    if (!isSupported) return;
    // 停掉全局其他
    acquireAudio(key, () => {
      window.speechSynthesis.cancel();
      if (mountedRef.current) setPlayState("idle");
    });

    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(textRef.current);
    u.lang = "zh-CN";
    u.rate = 0.95;
    if (bestVoice) u.voice = bestVoice;
    u.onend = () => { releaseAudio(key); if (mountedRef.current) setPlayState("idle"); };
    u.onerror = () => { releaseAudio(key); if (mountedRef.current) setPlayState("idle"); };
    u.onpause = () => { if (mountedRef.current) setPlayState("paused"); };
    u.onresume = () => { if (mountedRef.current) setPlayState("playing"); };
    if (mountedRef.current) setPlayState("playing");
    window.speechSynthesis.speak(u);
  }, [isSupported, bestVoice, key]);

  // ── 主点击 ──
  const handleClick = useCallback(() => {
    const now = Date.now();
    const isDbl = now - lastClickRef.current < 350;
    lastClickRef.current = now;

    if (isDbl) {
      // ══ 双击：停止+重置 ══
      stopAudio();
      releaseAudio(key);
      setPlayState("idle");
      return;
    }

    if (playState === "playing") {
      pauseAudio();
      setPlayState("paused");
      return;
    }

    if (playState === "paused") {
      if (audioRef.current) {
        audioRef.current.play().then(() => setPlayState("playing")).catch(() => {
          const saved = progressMap.get(key) || 0;
          fetchAndPlay(saved);
        });
        return;
      }
      const saved = progressMap.get(key) || 0;
      fetchAndPlay(saved);
      return;
    }

    // idle → 开始播放
    fetchAndPlay(progressMap.get(key) || 0);
  }, [playState, key, stopAudio, pauseAudio, fetchAndPlay]);

  // ── 被全局冲突抢占时的回调 ──
  // 因为是模块级变量，直接挂到全局
  // 在 acquireAudio/fetchAndPlay 中已处理

  // ── 卸载 ──
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const a = audioRef.current;
      if (a && a.duration && a.duration > 0 && a.duration < 3600) {
        progressMap.set(key, a.currentTime);
      }
      stopAudio();
      releaseAudio(key);
    };
  }, [key, stopAudio]);

  if (text.length < minLength) return null;

  const icon = playState === "playing" ? <Pause size={12} /> :
              playState === "paused"  ? <Play size={12} /> :
              <Volume2 size={12} />;
  const label = playState === "playing" ? "暂停" :
               playState === "paused"  ? "续播" :
               "朗读";

  return (
    <button
      onClick={handleClick}
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] transition-colors ${
        playState !== "idle"
          ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
          : "text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
      }`}
      title={playState === "playing" ? "单击暂停 · 双击停止" :
             playState === "paused"  ? "单击续播 · 双击停止" :
             "单击朗读 · 双击停止"}
    >
      {icon}
      {label}
    </button>
  );
}
