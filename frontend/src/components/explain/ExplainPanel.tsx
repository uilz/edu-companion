'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Youtube, Loader2, Volume2, ExternalLink, AlertCircle, Sparkles } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface MediaResult {
  platform: string;
  title: string;
  url: string;
  snippet?: string;
}

/** Raw media search result item from the API — may use 'link' or 'url', 'title' or 'snippet' as display fallback */
interface MediaSearchItem {
  title?: string;
  snippet?: string;
  url?: string;
  link?: string;
}

interface ExplainPanelProps {
  /** 知识点标识 */
  skillId: string;
  /** 知识点显示名 */
  skillName: string;
  /** 是否可见 */
  visible: boolean;
  /** 关闭回调 */
  onClose: () => void;
}

/** 讲解浮窗 — 答错后自动弹出，包含视频推荐+语音+图文卡片 */
export default function ExplainPanel({ skillId, skillName, visible, onClose }: ExplainPanelProps) {
  const [loading, setLoading] = useState(false);
  const [videos, setVideos] = useState<MediaResult[]>([]);
  const [ttsUrl, setTtsUrl] = useState<string | null>(null);
  const [error, setError] = useState('');

  // 加载讲解内容
  useEffect(() => {
    if (!visible || !skillId) return;

    async function loadExplain() {
      setLoading(true);
      setError('');
      setVideos([]);
      setTtsUrl(null);

      try {
        // 并发搜索视频 + TTS
        const [videoRes] = await Promise.all([
          fetch(`${API_BASE}/api/v2/explain/for-error`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skill_id: skillId, error_type: 'conceptual' }),
          }),
        ]);

        if (videoRes.ok) {
          const data = await videoRes.json();
          const results = data.results || {};
          // 合并多平台结果
          const merged: MediaResult[] = [];
          for (const [platform, items] of Object.entries(results)) {
            if (Array.isArray(items)) {
              items.forEach((item: MediaSearchItem) => {
                merged.push({
                  platform,
                  title: item.title || item.snippet || platform,
                  url: item.url || item.link || '',
                  snippet: item.snippet || '',
                });
              });
            }
          }
          setVideos(merged.slice(0, 6));
        }
      } catch (e) {
        setError('加载讲解失败，请重试');
      } finally {
        setLoading(false);
      }
    }

    loadExplain();
  }, [visible, skillId]);

  const handleTTS = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v2/explain/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_id: skillId,
          skill_name: skillName,
          explanation: `${skillName} 的核心概念讲解。`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setTtsUrl(data.url);
      }
    } catch {
      // silent
    }
  }, [skillId, skillName]);

  if (!visible) return null;

  return (
    <div className="fixed bottom-24 right-4 z-50 w-80 sm:w-96 max-h-[70vh] overflow-y-auto border border-[var(--color-border)] bg-[var(--color-card)] shadow-xl">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)] sticky top-0 bg-[var(--color-card)] z-10">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-[var(--color-accent)]" />
          <span className="text-sm font-semibold text-[var(--color-text)]">讲解</span>
        </div>
        <button onClick={onClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1">
          <X size={16} />
        </button>
      </div>

      {/* 知识点名 */}
      <div className="px-4 py-2 text-xs text-[var(--color-text-muted)] border-b border-[var(--color-border)] truncate">
        {skillName || skillId}
      </div>

      {/* 内容 */}
      <div className="p-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 py-4 text-xs text-red-400">
            <AlertCircle size={14} />
            {error}
          </div>
        ) : (
          <>
            {/* TTS 语音按钮 */}
            <button
              onClick={handleTTS}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors"
            >
              <Volume2 size={14} className="text-[var(--color-accent)]" />
              <span className="text-[var(--color-text-secondary)]">播放语音讲解</span>
              {ttsUrl && (
                <audio src={ttsUrl} controls className="ml-auto h-6 w-24" autoPlay />
              )}
            </button>

            {/* 视频推荐 */}
            {videos.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-[var(--color-text)] mb-2 flex items-center gap-1">
                  <Youtube size={13} className="text-red-400" />
                  推荐视频
                </div>
                <div className="space-y-1">
                  {videos.map((v, i) => (
                    <a
                      key={`${v.platform}-${i}`}
                      href={v.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-start gap-2 px-3 py-2 bg-[var(--color-surface)] text-xs hover:bg-[var(--color-accent)]/10 transition-colors group"
                    >
                      <ExternalLink size={12} className="text-[var(--color-text-muted)] flex-shrink-0 mt-0.5 group-hover:text-[var(--color-accent)]" />
                      <div className="flex-1 min-w-0">
                        <div className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-accent)] truncate">
                          {v.title}
                        </div>
                        {v.snippet && (
                          <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
                            {v.snippet}
                          </div>
                        )}
                      </div>
                      <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0 uppercase">
                        {v.platform}
                      </span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {videos.length === 0 && !loading && (
              <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                暂无相关视频，可尝试搜索
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
