"use client";

import React, { useState, useEffect, lazy, Suspense } from "react";
import { authedFetch } from "@/lib/api/api";
import MarkdownRenderer from "@/components/MarkdownRenderer";

// ── 类型 ──
export interface PreviewFile {
  material_id: string;
  file_name: string;
  file_type: string;
}

// 从文件名取小写扩展名
export function getExt(name: string): string {
  return name.toLowerCase().split('.').pop() || "";
}

// 读取 localStorage 中的 access_token
function getAccessToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || "";
}

// 浏览器原生可渲染的媒体类型（直接用 URL，无需 blob，支持流式加载）
const INLINE_TYPES = new Set([
  "jpg","jpeg","png","gif","bmp","webp","svg","ico","tiff","tif","avif",
  "pdf",
  "html","htm",
  "mp3","wav","m4a","ogg",
  "mp4","webm","mkv","mov","avi",
]);

// 代码语言映射（仅用于语法高亮）
const LANG_MAP: Record<string, string> = {
  py:"python", js:"javascript", ts:"typescript", jsx:"jsx", tsx:"tsx",
  java:"java", cpp:"cpp", c:"c", h:"c", hpp:"cpp",
  sql:"sql", rs:"rust", go:"go", rb:"ruby", php:"php",
  swift:"swift", kt:"kotlin", scala:"scala", r:"r", lua:"lua",
  sh:"bash", vue:"vue", svelte:"svelte", dart:"dart",
  gradle:"groovy", cmake:"cmake", tex:"latex", m:"matlab",
  mm:"objectivec", pl:"perl", pm:"perl",
  yaml:"yaml", yml:"yaml", toml:"toml", ini:"ini",
  json:"json", xml:"xml", csv:"text", md:"markdown",
};

// ── 主组件 ──
export default function PreviewContent({ file, className = "" }: {
  file: PreviewFile;
  className?: string;
}) {
  const ext = getExt(file.file_name);
  const baseUrl = `/api/files/${file.material_id}/preview`;

  // ── 浏览器原生类型：直接用 URL（加 ?token= 认证），流式加载，零内存 ──
  if (INLINE_TYPES.has(ext)) {
    const token = getAccessToken();
    const url = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
    return <InlinePreview ext={ext} url={url} fileName={file.file_name} className={className} />;
  }

  // ── 其他类型：authedFetch /preview 端点，后端决定渲染格式 ──
  return <FetchedPreview ext={ext} previewUrl={baseUrl} fileName={file.file_name} className={className} />;
}

// ═══════════════════════════════════════════════
// 子组件 1: 浏览器原生渲染（img / iframe / video / audio）
// ═══════════════════════════════════════════════

function InlinePreview({ ext, url, fileName, className }: {
  ext: string; url: string; fileName: string; className: string;
}) {
  const imageExts = new Set(["jpg","jpeg","png","gif","bmp","webp","svg","ico","tiff","tif","avif"]);

  if (imageExts.has(ext)) {
    return <ImagePreview url={url} fileName={fileName} className={className} />;
  }

  if (ext === "pdf") {
    return (
      <div className={className}>
        <iframe src={url} className="w-full h-[60vh] rounded" title="PDF预览" />
      </div>
    );
  }

  if (ext === "html" || ext === "htm") {
    return (
      <div className={className}>
        <iframe src={url} className="w-full h-[60vh] rounded" title="HTML预览" />
      </div>
    );
  }

  if (["mp3","wav","m4a","ogg"].includes(ext)) {
    return (
      <div className={`w-full p-6 ${className}`}>
        <audio controls className="w-full" src={url}>
          您的浏览器不支持音频播放
        </audio>
        <p className="text-center text-[11px] text-[var(--color-text-muted)] mt-3">{fileName}</p>
      </div>
    );
  }

  if (["mp4","webm","mkv","mov","avi"].includes(ext)) {
    return (
      <div className={`w-full p-2 ${className}`}>
        <video controls className="w-full max-h-[60vh] rounded" src={url}>
          您的浏览器不支持视频播放
        </video>
      </div>
    );
  }

  return null;
}

// ── 图片预览（带加载动画 & 错误回退） ──
function ImagePreview({ url, fileName, className }: { url: string; fileName: string; className: string }) {
  const [loaded, setLoaded] = useState(false);
  const [errored, setErrored] = useState(false);

  return (
    <div className={`relative ${className}`}>
      {!loaded && !errored && (
        <div className="flex items-center justify-center min-h-[200px]">
          <div className="animate-spin w-8 h-8 border-2 border-[var(--color-accent)] border-t-transparent rounded-full" />
        </div>
      )}
      {errored && (
        <div className="flex flex-col items-center justify-center min-h-[200px] text-center">
          <svg className="w-8 h-8 text-[var(--color-text-muted)] mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z" />
          </svg>
          <p className="text-sm text-[var(--color-text-muted)]">图片加载失败</p>
        </div>
      )}
      <img src={url} alt={fileName}
        className={`max-w-full max-h-[60vh] object-contain rounded transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'} ${loaded ? '' : 'absolute inset-0 pointer-events-none'}`}
        onLoad={() => setLoaded(true)}
        onError={() => setErrored(true)} />
    </div>
  );
}

// ═══════════════════════════════════════════════
// 子组件 2: fetch /preview，根据后端返回类型分发渲染
// ═══════════════════════════════════════════════

function FetchedPreview({ ext, previewUrl, fileName, className }: {
  ext: string; previewUrl: string; fileName: string; className: string;
}) {
  const [content, setContent] = useState("");
  const [fromChunks, setFromChunks] = useState(false);
  const [lang, setLang] = useState("");
  const [docxBuf, setDocxBuf] = useState<ArrayBuffer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    if (ext === "docx") {
      // DOCX: /preview 返回原文件，用 mammoth.js 转 HTML
      authedFetch(previewUrl)
        .then(r => { if (!r.ok) throw new Error(`预览失败 (${r.status})`); return r.arrayBuffer(); })
        .then(buf => {
          if (cancelled) return;
          setDocxBuf(buf);
          setLoading(false);
        })
        .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    } else {
      // 非 DOCX: /preview 返回 JSON
      authedFetch(previewUrl)
        .then(r => { if (!r.ok) throw new Error(`预览失败 (${r.status})`); return r.json(); })
        .then(data => {
          if (cancelled) return;
          if (!data.content && data.type === "empty") {
            setError("该文件无预览内容");
          } else {
            setContent(data.content || "");
            setFromChunks(!!data.from_chunks);
            setLang(data.lang || "");
          }
          setLoading(false);
        })
        .catch(e => { if (!cancelled) { setError(e.message); setLoading(false); } });
    }

    return () => { cancelled = true; };
  }, [previewUrl, ext]);

  // 加载中
  if (loading) {
    return (
      <div className={`flex items-center justify-center min-h-[300px] ${className}`}>
        <div className="animate-spin w-8 h-8 border-2 border-[var(--color-accent)] border-t-transparent rounded-full" />
        <span className="ml-3 text-sm text-[var(--color-text-muted)]">加载中...</span>
      </div>
    );
  }

  // 错误
  if (error) {
    return (
      <div className={`flex flex-col items-center justify-center min-h-[200px] text-center ${className}`}>
        <p className="text-sm text-red-400 mb-2">{error}</p>
      </div>
    );
  }

  // DOCX → mammoth 渲染
  if (docxBuf) {
    return <DocxPreview buf={docxBuf} className={className} />;
  }

  // Markdown（来自 chunks 或 .md 文件）
  if (fromChunks || ext === "md") {
    return (
      <div className={`w-full max-h-[60vh] overflow-auto p-4 ${className}`}>
        <MarkdownRenderer>{content}</MarkdownRenderer>
      </div>
    );
  }

  // 代码 → 语法高亮
  if (lang && LANG_MAP[lang]) {
    return <CodePreview lang={LANG_MAP[lang]} text={content} className={className} />;
  }

  // 纯文本
  if (content) {
    return <PlainText text={content} className={className} />;
  }

  return (
    <div className={`flex items-center justify-center min-h-[200px] ${className}`}>
      <p className="text-sm text-[var(--color-text-muted)]">此文件类型暂不支持预览</p>
    </div>
  );
}

// ═══════════════════════════════════════════════
// 子组件 3: DOCX 预览（mammoth.js）
// ═══════════════════════════════════════════════

function DocxPreview({ buf, className }: { buf: ArrayBuffer; className: string }) {
  const [html, setHtml] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    import("mammoth").then(m => {
      const mm = m.default || m;
      return mm.convertToHtml({ arrayBuffer: buf });
    }).then(result => {
      if (!cancelled) { setHtml(result.value); setLoading(false); }
    }).catch(e => {
      if (!cancelled) { setError(e.message); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [buf]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center min-h-[200px] ${className}`}>
        <div className="animate-spin w-6 h-6 border-2 border-[var(--color-accent)] border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return <div className={`p-4 text-sm text-red-400 ${className}`}>{error}</div>;
  }

  return (
    <div
      className={`w-full p-4 max-h-[60vh] overflow-auto text-sm leading-relaxed text-[var(--color-text)] ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// ═══════════════════════════════════════════════
// 子组件 4: 代码语法高亮
// ═══════════════════════════════════════════════

const SyntaxHighlighter = lazy(() =>
  import("react-syntax-highlighter/dist/esm/prism-light").then(m => ({ default: m.default }))
);

function CodePreview({ lang, text, className }: { lang: string; text: string; className: string }) {
  const [style, setStyle] = useState<any>(null);
  useEffect(() => {
    import("react-syntax-highlighter/dist/esm/styles/prism").then(m => setStyle(m.oneDark));
  }, []);

  if (!style) return <PlainText text={text} className={className} />;

  return (
    <div className={`w-full max-h-[60vh] overflow-auto rounded text-xs ${className}`}>
      <Suspense fallback={<PlainText text={text} />}>
        <SyntaxHighlighter language={lang} style={style} showLineNumbers
          customStyle={{ margin: 0, borderRadius: "0.5rem", fontSize: "12px" }}>
          {text}
        </SyntaxHighlighter>
      </Suspense>
    </div>
  );
}

// ═══════════════════════════════════════════════
// 子组件 5: 纯文本
// ═══════════════════════════════════════════════

function PlainText({ text, className = "" }: { text: string; className?: string }) {
  return (
    <div className={`w-full p-4 max-h-[60vh] overflow-auto ${className}`}>
      <pre className="text-xs leading-relaxed text-[var(--color-text)] whitespace-pre-wrap font-sans">{text}</pre>
    </div>
  );
}