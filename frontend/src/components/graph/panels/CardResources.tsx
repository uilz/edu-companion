"use client";

import React from "react";
import { RefreshCw, Search, Youtube } from "lucide-react";

interface Props {
  nodeLabel: string;
  results: any[];
  loading: boolean;
  error: string | null;
  onSearch: () => void;
}

export default function CardResources({ nodeLabel, results, loading, error, onSearch }: Props) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <Youtube size={12} className="text-[var(--color-accent)]" />
        <span className="text-[11px] font-medium text-[var(--color-text-muted)]">B站视频</span>
        <div className="flex-1" />
        {results.length > 0 && <span className="text-[10px] text-[var(--color-text-muted)]">{results.length} 个结果</span>}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-6 gap-2">
          <RefreshCw size={12} className="animate-spin text-[var(--color-text-muted)]" />
          <span className="text-[11px] text-[var(--color-text-muted)]">搜索中…</span>
        </div>
      ) : error ? (
        <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-center">
          <p className="text-[10px] text-[var(--color-error)]">{error}</p>
          <button onClick={onSearch} className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:underline mt-2 mx-auto">
            <RefreshCw size={10} />重试
          </button>
        </div>
      ) : results.length === 0 ? (
        <div className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50 text-center">
          <p className="text-[10px] text-[var(--color-text-muted)]">暂无推荐视频</p>
          <button onClick={onSearch} className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:underline mt-2 mx-auto">
            <Search size={10} />搜索「{nodeLabel} 讲解」
          </button>
        </div>
      ) : (
        <div className="space-y-1.5">
          {results.map((video: any, i: number) => (
            <a key={video.bvid || i} href={video.link || `https://www.bilibili.com/video/${video.bvid}`}
              target="_blank" rel="noopener noreferrer"
              className="flex gap-2 p-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50 hover:bg-[var(--color-accent)]/5 hover:border-[var(--color-accent)]/20 transition-all group">
              {video.cover && <img src={video.cover} alt="" className="w-12 h-8 rounded object-cover flex-shrink-0" />}
              <div className="min-w-0 flex-1">
                <p className="text-[11px] text-[var(--color-text)] line-clamp-1 group-hover:text-[var(--color-accent)] transition-colors">{video.title || video.name}</p>
                {video.author && <p className="text-[9px] text-[var(--color-text-muted)] mt-0.5">{video.author}</p>}
                {video.played && <p className="text-[9px] text-[var(--color-text-muted)]">{video.played} 次播放</p>}
              </div>
            </a>
          ))}
        </div>
      )}

      <button onClick={onSearch} className="flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:underline mt-2">
        <RefreshCw size={10} />重新搜索
      </button>
    </div>
  );
}
