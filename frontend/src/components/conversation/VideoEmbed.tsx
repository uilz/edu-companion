"use client";

import { useState } from "react";
import { Play, ExternalLink } from "lucide-react";

interface VideoEmbedProps {
  url: string;
  title?: string;
  thumbnail?: string;
}

// ── URL Parser ──

interface VideoInfo {
  platform: "bilibili" | "youtube" | "direct";
  embedUrl: string;
}

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

export default function VideoEmbed({ url, title, thumbnail }: VideoEmbedProps) {
  const [showVideo, setShowVideo] = useState(false);
  const videoInfo = parseVideoUrl(url);

  if (!videoInfo) return null;

  // Thumbnail / click-to-play for iframe embeds
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

  // Inline iframe (B站 / YouTube)
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

  // Direct <video> tag
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 overflow-hidden">
      <video src={videoInfo.embedUrl} controls className="w-full max-h-96" preload="metadata">
        您的浏览器不支持视频播放。
      </video>
    </div>
  );
}
