"use client";

import { Loader2, ExternalLink } from "lucide-react";
import type { ResponseBlock } from "@/types";

// ──── Platform Icons ────
const PLATFORM_ICONS: Record<string, string> = {
  bilibili: "🎬",
  youtube: "▶️",
  zhihu: "💬",
  baidu_wenku: "📄",
  xuexi_qiangguo: "🇨🇳",
  cnki: "📖",
  douyin: "🎵",
};

// ──── Multi-platform media search block ────
export default function MediaSearchBlock({ content }: { content: Record<string, unknown> }) {
  const query = (content.query as string) || "";
  const platforms = (content.platforms as Array<{
    platform: string;
    name: string;
    icon: string;
    description: string;
    links: Array<{ query: string; url: string }>;
  }>) || [];

  // Old format (single video result) — fallback
  if (content.url && !platforms.length) {
    return <LegacyVideoBlock content={content} />;
  }

  if (!platforms.length) return null;

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <span className="text-sm">🔍</span>
        <span className="text-xs font-medium text-[var(--color-text)]">
          搜索视频教程
        </span>
        {query && (
          <span className="text-[10px] text-[var(--color-text-muted)] truncate ml-1">
            · {query}
          </span>
        )}
      </div>

      {/* Platform cards */}
      <div className="p-2 space-y-2">
        {platforms.map((p) => {
          const icon = PLATFORM_ICONS[p.platform] || p.icon || "🔗";
          return (
            <div key={p.platform} className="border border-[var(--color-border)] px-3 py-2.5">
              {/* Platform header */}
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-sm">{icon}</span>
                <span className="text-xs font-medium text-[var(--color-text)]">
                  {p.name}
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  · {p.description}
                </span>
              </div>

              {/* Search links */}
              <div className="space-y-1">
                {p.links.map((link, i) => (
                  <a
                    key={i}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-2 py-1.5 text-xs text-[var(--color-accent)] hover:bg-[var(--color-bg)] transition-colors group"
                  >
                    <ExternalLink
                      size={11}
                      className="flex-shrink-0 opacity-50 group-hover:opacity-100 transition-opacity"
                    />
                    <span className="flex-1 truncate">{link.query}</span>
                  </a>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer hint */}
      <div className="px-3 py-1.5 border-t border-[var(--color-border)] text-[9px] text-[var(--color-text-muted)]">
        点击链接在新窗口打开搜索 · AI 优化搜索词
      </div>
    </div>
  );
}

// ──── Legacy single video block (backward compat) ────
function LegacyVideoBlock({ content }: { content: Record<string, unknown> }) {
  const title = (content.title as string) || "视频";
  const url = (content.url as string) || "";
  const duration = (content.duration as string) || "";
  const source = (content.source as string) || "";

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 overflow-hidden">
      <div className="px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-sm">▶️</span>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[var(--color-text)] hover:text-[var(--color-accent)] transition-colors truncate"
          >
            {title}
          </a>
        </div>
        {source && (
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
            来源: {source} {duration && `· ${duration}`}
          </div>
        )}
      </div>
    </div>
  );
}
