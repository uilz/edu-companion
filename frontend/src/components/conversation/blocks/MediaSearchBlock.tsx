"use client";

// ──── 导入依赖：lucide-react 图标库和类型定义 ────
import { Loader2, ExternalLink } from "lucide-react";
import type { ResponseBlock } from "@/types";
import VideoEmbed from "./../media/VideoEmbed";

// ──── 检测 URL 是否为可嵌入的视频链接 ────
function isEmbeddableVideoUrl(url: string): boolean {
  return /bilibili\.com\/video\/BV/.test(url) ||
    /(?:youtube\.com\/watch|youtu\.be\/|youtube\.com\/embed\/)/.test(url) ||
    /\.(mp4|webm|mov|flv)(\?|$)/i.test(url);
}

// ──── 平台图标映射表 ────
// 为每个支持的平台（B站、YouTube、知乎等）分配对应的 Emoji 图标
const PLATFORM_ICONS: Record<string, string> = {
  bilibili: "🎬",
  youtube: "▶️",
  zhihu: "💬",
  baidu_wenku: "📄",
  xuexi_qiangguo: "🇨🇳",
  cnki: "📖",
  douyin: "🎵",
  xiaohongshu: "📕",
  bing: "🔍",
  baidu: "🌐",
};

// ──── 多平台媒体搜索结果展示组件 ────
// 接收 content 对象，渲染跨平台的视频/媒体搜索卡片列表
export default function MediaSearchBlock({ content }: { content: Record<string, unknown> }) {
  // 提取搜索关键词（如用户在对话中输入的查询）
  const query = (content.query as string) || "";
  // 提取各平台的搜索结果列表
  const platforms = (content.platforms as Array<{
    platform: string;
    name: string;
    icon: string;
    description: string;
    links: Array<{ query: string; url: string }>;
  }>) || [];

  // ──── 旧格式兼容：单个视频结果（无 platforms 字段时降级） ────
  if (content.url && !platforms.length) {
    return <LegacyVideoBlock content={content} />;
  }

  // 无搜索结果时直接返回空
  if (!platforms.length) return null;

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      {/* ──── 头部：显示搜索图标、标题和关键词 ──── */}
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

      {/* ──── 平台卡片列表：遍历每个平台的搜索结果 ──── */}
      <div className="p-2 space-y-2">
        {platforms.map((p) => {
          // 从映射表中取图标，找不到则使用平台自带图标或默认链接图标
          const icon = PLATFORM_ICONS[p.platform] || p.icon || "🔗";
          return (
            <div key={p.platform} className="border border-[var(--color-border)] px-3 py-2.5">
              {/* ──── 平台头部：图标 + 平台名称 + 描述 ──── */}
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-sm">{icon}</span>
                <span className="text-xs font-medium text-[var(--color-text)]">
                  {p.name}
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  · {p.description}
                </span>
              </div>

              {/* ──── 搜索链接列表：每个链接跳转到对应平台的搜索结果页 ──── */}
              <div className="space-y-1">
                {p.links.map((link, i) => (
                  isEmbeddableVideoUrl(link.url) ? (
                    <VideoEmbed key={i} url={link.url} title={link.query} />
                  ) : (
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
                  )
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* ──── 底部提示：操作说明（在新窗口打开、AI 优化搜索词） ──── */}
      <div className="px-3 py-1.5 border-t border-[var(--color-border)] text-[9px] text-[var(--color-text-muted)]">
        点击链接在新窗口打开搜索 · AI 优化搜索词
      </div>
    </div>
  );
}

// ──── 旧格式视频块组件（向后兼容） ────
// 当 content 使用旧的单视频格式（只有 url 无 platforms）时渲染
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
