"use client";

// React hooks
import { useState, useCallback, useEffect, useRef } from "react";
// 音量图标组件
import { Volume2, VolumeX } from "lucide-react";

/**
 * SpeakButton 组件的属性接口
 * @param text   - 要朗读的文本内容
 * @param minLength - 触发朗读的最小文本长度（默认 200 字符，防止过短文本触发朗读）
 */
interface SpeakButtonProps {
  text: string;
  minLength?: number;
}

/**
 * 首选中文语音列表（按发音质量从高到低排序）—— 浏览器 TTS 回退用
 */
const PREFERRED_VOICES = [
  "Microsoft Xiaoxiao",
  "Microsoft Yunxi",
  "Microsoft Xiaohan",
  "Google 普通话",
  "Tingting",
  "Sin-Ji",
];

/**
 * SpeakButton 语音朗读按钮组件
 *
 * 功能：
 * 1. 优先使用 Edge-TTS（服务端高质量语音合成）
 * 2. 如果 Edge-TTS 不可用，回退到浏览器内置 SpeechSynthesis API
 *
 * 仅当文本长度超过 minLength 时才会显示该按钮。
 */
export default function SpeakButton({ text, minLength = 200 }: SpeakButtonProps) {
  // 当前是否正在朗读
  const [speaking, setSpeaking] = useState(false);
  // 已选中的最佳中文语音对象（浏览器 TTS 回退用）
  const [bestVoice, setBestVoice] = useState<SpeechSynthesisVoice | null>(null);
  // 浏览器是否支持 SpeechSynthesis 接口
  const isSupported = typeof window !== "undefined" && !!window.speechSynthesis;
  // 防止重复加载语音列表
  const voicesLoaded = useRef(false);
  // 当前播放的 Audio 对象（Edge-TTS 模式）
  const audioRef = useRef<HTMLAudioElement | null>(null);

  /**
   * 加载系统语音列表，自动选择最优质的中文语音（浏览器 TTS 回退用）
   */
  useEffect(() => {
    if (!isSupported || voicesLoaded.current) return;

    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) return;
      voicesLoaded.current = true;

      for (const name of PREFERRED_VOICES) {
        const found = voices.find(v => v.name.includes(name) && v.lang.startsWith("zh"));
        if (found) {
          setBestVoice(found);
          return;
        }
      }
      const anyChinese = voices.find(v => v.lang.startsWith("zh"));
      if (anyChinese) setBestVoice(anyChinese);
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, [isSupported]);

  /**
   * 清理 Markdown 符号，使 TTS 朗读更自然
   */
  const cleanForTTS = useCallback((raw: string) => {
    return raw
      .replace(/[#*_~`>[\\]()]/g, "")
      .replace(/\$\$[\s\S]*?\$\$/g, "")   // 移除行间数学公式
      .replace(/\$[^$\n]+?\$/g, "")        // 移除行内数学公式
      .replace(/\n{2,}/g, "。")
      .replace(/\n/g, "，")
      .substring(0, 500);
  }, []);

  /**
   * 使用浏览器 SpeechSynthesis API 朗读（回退方案）
   */
  const speakWithBrowser = useCallback((cleanText: string) => {
    if (!isSupported) return false;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = "zh-CN";
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    if (bestVoice) {
      utterance.voice = bestVoice;
    }

    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
    return true;
  }, [isSupported, bestVoice]);

  /**
   * 使用 Edge-TTS 服务端语音合成
   */
  const speakWithEdgeTTS = useCallback(async (rawText: string) => {
    try {
      setSpeaking(true);

      const response = await fetch("/api/multimodal/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: rawText,
          voice: "zh-CN-XiaoxiaoNeural",
        }),
      });

      if (!response.ok) {
        // Edge-TTS 不可用，回退到浏览器 TTS
        console.warn("Edge-TTS unavailable, falling back to browser TTS");
        const cleanText = cleanForTTS(rawText);
        speakWithBrowser(cleanText);
        return;
      }

      const data = await response.json();
      const audioUrl = data.audio_url as string;

      // 播放音频
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setSpeaking(false);
        audioRef.current = null;
      };
      audio.onerror = () => {
        setSpeaking(false);
        audioRef.current = null;
        // 播放出错也回退
        const cleanText = cleanForTTS(rawText);
        speakWithBrowser(cleanText);
      };

      await audio.play();
    } catch (err) {
      // 网络错误等，回退到浏览器 TTS
      console.warn("Edge-TTS fetch failed, falling back to browser TTS:", err);
      const cleanText = cleanForTTS(rawText);
      speakWithBrowser(cleanText);
    }
  }, [cleanForTTS, speakWithBrowser]);

  /**
   * 朗读 / 停止朗读 的切换函数
   */
  const speak = useCallback(() => {
    if (!text) return;

    // 切换停止
    if (speaking) {
      // 停止 Edge-TTS 音频
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
        audioRef.current = null;
      }
      // 停止浏览器 TTS
      if (isSupported) {
        window.speechSynthesis.cancel();
      }
      setSpeaking(false);
      return;
    }

    // 优先使用 Edge-TTS
    speakWithEdgeTTS(text);
  }, [text, speaking, isSupported, speakWithEdgeTTS]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (isSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [isSupported]);

  // 如果浏览器不支持语音合成且 Edge-TTS 也可能不可用，仍然显示按钮（Edge-TTS 可用）
  // 只有文本长度不足时不显示
  if (text.length < minLength) return null;

  return (
    <button
      onClick={speak}
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] transition-colors ${
        speaking
          ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
          : "text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
      }`}
      title={speaking ? "停止朗读" : "朗读 (Edge-TTS)"}
    >
      {speaking ? <VolumeX size={12} /> : <Volume2 size={12} />}
      {speaking ? "停止" : "朗读"}
    </button>
  );
}
