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
 * 首选中文语音列表（按发音质量从高到低排序）
 * 各平台对应的默认高质量语音：
 *   - Win 11 → Microsoft Xiaoxiao（最自然）
 *   - Win 11 → Microsoft Yunxi
 *   - Win 10+ → Microsoft Xiaohan
 *   - Chrome Android → Google 普通话
 *   - macOS → Tingting
 *   - macOS Cantonese fallback → Sin-Ji
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
 * 功能：使用浏览器内置的 SpeechSynthesis API 朗读指定文本，
 * 自动检测并选用系统中最优质的中文语音。
 * 仅当文本长度超过 minLength 时才会显示该按钮，
 * 以避免按钮过多干扰用户。
 */
export default function SpeakButton({ text, minLength = 200 }: SpeakButtonProps) {
  // 当前是否正在朗读
  const [speaking, setSpeaking] = useState(false);
  // 已选中的最佳中文语音对象
  const [bestVoice, setBestVoice] = useState<SpeechSynthesisVoice | null>(null);
  // 浏览器是否支持 SpeechSynthesis 接口
  const isSupported = typeof window !== "undefined" && !!window.speechSynthesis;
  // 防止重复加载语音列表
  const voicesLoaded = useRef(false);

  /**
   * 加载系统语音列表，自动选择最优质的中文语音。
   * 优先匹配 PREFERRED_VOICES 列表中的语音，若无匹配则回退到任意可用中文语音。
   * 使用 onvoiceschanged 事件监听语音列表异步加载完成。
   */
  useEffect(() => {
    if (!isSupported || voicesLoaded.current) return;

    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) return;
      voicesLoaded.current = true;

      // 先尝试从首选语音列表中匹配
      for (const name of PREFERRED_VOICES) {
        const found = voices.find(v => v.name.includes(name) && v.lang.startsWith("zh"));
        if (found) {
          setBestVoice(found);
          return;
        }
      }
      // 回退策略：任意可用中文语音
      const anyChinese = voices.find(v => v.lang.startsWith("zh"));
      if (anyChinese) setBestVoice(anyChinese);
    };

    loadVoices();
    // 语音列表异步加载完成后再次尝试
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, [isSupported]);

  /**
   * 朗读 / 停止朗读 的切换函数
   *
   * 若当前正在朗读 → 停止朗读并重置状态；
   * 若当前未朗读  → 对文本做以下处理后再朗读：
   *   1. 去除 Markdown 符号（# * _ ~ ` > [ ] ( ) 等）
   *   2. 移除数学公式（行间 $$...$$ 和行内 $...$）
   *   3. 将换行符替换为中文标点，使朗读更自然
   *   4. 截断到前 500 字符，避免过长的文本
   *
   * 朗读时使用预选的最佳中文语音，语速略慢（0.95）以获得更自然的听感。
   */
  const speak = useCallback(() => {
    if (!isSupported || !text) return;

    // 切换停止
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    // 去除 Markdown 符号，使 TTS 朗读更自然
    const cleanText = text
      .replace(/[#*_~`>[\]()]/g, "")
      .replace(/\$\$[\s\S]*?\$\$/g, "")   // 移除行间数学公式
      .replace(/\$[^$\n]+?\$/g, "")        // 移除行内数学公式
      .replace(/\n{2,}/g, "。")
      .replace(/\n/g, "，")
      .substring(0, 500);  // 限制朗读长度

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = "zh-CN";
    utterance.rate = 0.95;   // 略慢语速，更自然
    utterance.pitch = 1.0;

    // 应用已选中的最佳语音
    if (bestVoice) {
      utterance.voice = bestVoice;
    }

    // 朗读结束/出错时重置状态
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [text, speaking, isSupported, bestVoice]);

  // 如果浏览器不支持语音合成，或文本长度不足，则不显示按钮
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
      {/* 朗读中显示音量关闭图标，否则显示音量图标 */}
      {speaking ? <VolumeX size={12} /> : <Volume2 size={12} />}
      {/* 朗读中显示"停止"，否则显示"朗读" */}
      {speaking ? "停止" : "朗读"}
    </button>
  );
}
