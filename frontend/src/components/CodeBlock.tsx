"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useTheme } from "@/contexts/ThemeContext";
import { Check, Copy } from "lucide-react";

interface Props {
  language: string;
  value: string;
}

// 按需加载 react-syntax-highlighter，避免 webpack 构建时处理整个 Prism 库
let highlighterCache: {
  Prism: any;
  oneDark: any;
  oneLight: any;
} | null = null;

async function loadHighlighter() {
  if (highlighterCache) return highlighterCache;
  const [hl, styles] = await Promise.all([
    import("react-syntax-highlighter"),
    import("react-syntax-highlighter/dist/esm/styles/prism"),
  ]);
  highlighterCache = {
    Prism: hl.Prism,
    oneDark: styles.oneDark,
    oneLight: styles.oneLight,
  };
  return highlighterCache;
}

export default function CodeBlock({ language, value }: Props) {
  const { theme } = useTheme();
  const [copied, setCopied] = useState(false);
  const [SyntaxHighlighter, setSyntaxHighlighter] = useState<any>(null);
  const [style, setStyle] = useState<any>(null);
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    loadHighlighter().then(({ Prism, oneDark, oneLight }) => {
      setSyntaxHighlighter(() => Prism);
      setStyle(theme === "dark" ? oneDark : oneLight);
    });
  }, [theme]);

  useEffect(() => {
    if (highlighterCache) {
      setStyle(
        theme === "dark"
          ? highlighterCache.oneDark
          : highlighterCache.oneLight
      );
    }
  }, [theme]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = value;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [value]);

  const headerBar = (
    <div className="flex items-center justify-between px-3 py-1.5 bg-surface-hover border-b border">
      <span className="text-[10px] text-muted font-mono uppercase tracking-wider">
        {language || "text"}
      </span>
      <button
        onClick={handleCopy}
        className="flex items-center gap-1 text-[10px] text-muted hover:text transition-colors"
        title="复制代码"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? "已复制" : "复制"}
      </button>
    </div>
  );

  // 高亮库加载中时显示纯文本代码块
  if (!SyntaxHighlighter || !style) {
    return (
      <div className="relative group my-2 rounded-lg overflow-hidden border border">
        {headerBar}
        <pre className="m-0 p-3 text-xs leading-relaxed overflow-x-auto bg-surface text">
          <code>{value}</code>
        </pre>
      </div>
    );
  }

  return (
    <div className="relative group my-2 rounded-lg overflow-hidden border border">
      {headerBar}
      <SyntaxHighlighter
        language={language || "text"}
        style={style}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "12px",
          lineHeight: "1.6",
        }}
        showLineNumbers={value.split("\n").length > 8}
        lineNumberStyle={{
          minWidth: "2.5em",
          paddingRight: "1em",
          opacity: 0.4,
        }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}
