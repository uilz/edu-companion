"use client";

// 导入 React hooks 和图标组件
import { useState } from "react";
import { Play, ExternalLink } from "lucide-react";

// ── 组件属性类型定义 ──
// url: 视频链接（B站/YouTube/直链）
// title: 视频标题（可选）
// thumbnail: 自定义缩略图 URL（可选）
interface VideoEmbedProps {
  url: string;
  title?: string;
  thumbnail?: string;
}

// ── URL Parser ──

// ── 解析后的视频信息类型 ──
// platform: 视频平台标识（bilibili / youtube / direct）
// embedUrl: 用于嵌入播放的 URL
interface VideoInfo {
  platform: "bilibili" | "youtube" | "direct";
  embedUrl: string;
}

/**
 * 解析视频 URL，提取嵌入播放所需的参数
 * 支持三种格式：
 *   - B站：bilibili.com/video/BVxxx
 *   - YouTube：youtube.com/watch?v=xxx / youtu.be/xxx
 *   - 直接视频文件：.mp4 / .webm / .mov / .flv
 */
function parseVideoUrl(url: string): VideoInfo | null {
  // B站: bilibili.com/video/BVxxx
  const biliMatch = url.match(/bilibili\.com\/video\/(BV[a-zA-Z0-9]+)/);
  if (biliMatch) {
    return {
      platform: "bilibili",
      embedUrl: `//player.bilibili.com/player.html?bvid=${biliMatch[1]}&page=1&high_quality=1`,
    };
  }

  // YouTube: youtube.com/watch?v=xxx or youtu.be/xxx
  const ytMatch = url.match(
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]+)/
  );
  if (ytMatch) {
    return {
      platform: "youtube",
      embedUrl: `https://www.youtube-nocookie.com/embed/${ytMatch[1]}`,
    };
  }

  // Direct video file
  if (/\.(mp4|webm|mov|flv)(\?|$)/i.test(url)) {
    return { platform: "direct", embedUrl: url };
  }

  return null;
}

// ── Component ──

/**
 * 视频嵌入组件
 * 根据 URL 自动识别平台（B站 / YouTube / 直链视频），
 * 渲染对应的嵌入播放器或缩略图预览 + 点击播放界面。
 */
export default function VideoEmbed({ url, title, thumbnail }: VideoEmbedProps) {
  const [showVideo, setShowVideo] = useState(false);
  const videoInfo = parseVideoUrl(url);

  if (!videoInfo) return null;

  // ── 缩略图预览 + 点击播放（仅 iframe 嵌入的视频） ──
  // 首次渲染时显示缩略图和播放按钮，用户点击后才加载 iframe
  if (videoInfo.platform !== "direct" && !showVideo) {
    return (
      <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 overflow-hidden">
        <div className="relative aspect-video bg-[#0a0a0a] cursor-pointer group" onClick={() => setShowVideo(true)}>
          {thumbnail ? (
            <img src={thumbnail} alt={title || "视频缩略图"} className="w-full h-full object-cover opacity-60 group-hover:opacity-40 transition-opacity" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <span className="text-4xl opacity-30 group-hover:opacity-50 transition-opacity">
                {videoInfo.platform === "bilibili" ? "🎬" : "▶️"}
              </span>
            </div>
          )}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-14 h-14 flex items-center justify-center bg-[var(--color-accent)]/90 group-hover:bg-[var(--color-accent)] transition-colors">
              <Play size={24} className="text-white ml-0.5" fill="white" />
            </div>
          </div>
          {title && (
            <div className="absolute bottom-0 left-0 right-0 px-3 py-2 bg-gradient-to-t from-black/80 to-transparent">
              <span className="text-xs text-white/80 line-clamp-1">{title}</span>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-[var(--color-border)]">
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {videoInfo.platform === "bilibili" ? "B站" : "YouTube"}
          </span>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:underline"
          >
            <ExternalLink size={10} />
            在外部打开
          </a>
        </div>
      </div>
    );
  }

  // ── iframe 嵌入播放器（B站 / YouTube） ──
  // 用户已点击播放，或直接渲染非直链视频的 iframe
  if (videoInfo.platform !== "direct") {
    return (
      <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 overflow-hidden">
        <div className="relative aspect-video">
          <iframe
            src={videoInfo.embedUrl}
            className="absolute inset-0 w-full h-full"
            allowFullScreen
            allow="autoplay; encrypted-media"
            title={title || "视频播放器"}
          />
        </div>
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-[var(--color-border)]">
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {videoInfo.platform === "bilibili" ? "B站" : "YouTube"}
            {title && ` · ${title}`}
          </span>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:underline"
          >
            <ExternalLink size={10} />
            在外部打开
          </a>
        </div>
      </div>
    );
  }

  // ── 原生 <video> 标签播放器（直链视频文件） ──
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 overflow-hidden">
      <video src={videoInfo.embedUrl} controls className="w-full max-h-96" preload="metadata">
        您的浏览器不支持视频播放。
      </video>
    </div>
  );
}
