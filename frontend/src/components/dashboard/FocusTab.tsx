'use client';

import { useRouter } from 'next/navigation';
import { Focus, Brain, Clock, BarChart3, ArrowRight } from 'lucide-react';
import { useConversationStore } from '@/store/conversation-store';

/**
 * FocusTab — 专注模式入口组件
 * 展示学习概况和快速进入专注模式的入口
 */
export default function FocusTab() {
  const router = useRouter();
  const partitions = useConversationStore((s) => s.partitions);

  const handleStartFocus = (partitionId?: string) => {
    const params = new URLSearchParams();
    if (partitionId) params.set('p', partitionId);
    router.push(`/focus?${params.toString()}`);
  };

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-[var(--color-text)] flex items-center gap-2">
            <Focus size={20} className="text-[var(--color-accent)]" />
            专注模式
          </h2>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            全屏极简界面，减少干扰，专注深度学习
          </p>
        </div>
      </div>

      {/* 功能特点卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
              <Brain size={20} className="text-[var(--color-accent)]" />
            </div>
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">认知负荷感知</div>
              <div className="text-xs text-[var(--color-text-muted)]">自适应调节学习节奏</div>
            </div>
          </div>
        </div>
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
              <Clock size={20} className="text-[var(--color-accent)]" />
            </div>
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">极简界面</div>
              <div className="text-xs text-[var(--color-text-muted)]">仅保留核心对话流</div>
            </div>
          </div>
        </div>
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
              <BarChart3 size={20} className="text-[var(--color-accent)]" />
            </div>
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">苏格拉底引导</div>
              <div className="text-xs text-[var(--color-text-muted)]">启发式提问促进思考</div>
            </div>
          </div>
        </div>
      </div>

      {/* 学习分区列表 */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">选择学习分区</h3>

        {(partitions || []).length === 0 ? (
          <div className="text-center py-12 bg-[var(--color-surface)] border border-dashed border-[var(--color-border)] rounded-xl">
            <Focus size={32} className="mx-auto text-[var(--color-text-muted)] mb-3" />
            <p className="text-sm text-[var(--color-text-muted)]">还没有学习分区，先去创建吧</p>
            <button
              onClick={() => router.push('/learn')}
              className="mt-3 px-4 py-2 text-xs bg-[var(--color-accent)] text-white rounded-lg
                         hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-all"
            >
              去创建
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {partitions.map((p) => (
              <button
                key={p.id}
                onClick={() => handleStartFocus(p.id)}
                className="group flex items-center gap-4 bg-[var(--color-surface)] border border-[var(--color-border)]
                           hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/5
                           rounded-xl p-4 active:scale-[0.98] transition-all text-left"
              >
                <span className="text-2xl">{p.emoji || '📚'}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-[var(--color-text)] truncate">
                    {p.name || '未命名分区'}
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {(p as unknown as Record<string, unknown>).message_count as number || 0} 条消息
                  </div>
                </div>
                <ArrowRight size={16} className="text-[var(--color-text-muted)]
                  group-hover:text-[var(--color-accent)] group-hover:translate-x-1 transition-all" />
              </button>
            ))}
          </div>
        )}

        {/* 快速开始（无分区选择） */}
        <button
          onClick={() => handleStartFocus()}
          className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-3
                     bg-[var(--color-accent)] text-white rounded-xl
                     hover:bg-[var(--color-accent-hover)] active:scale-[0.97]
                     transition-all text-sm font-medium"
        >
          <Focus size={16} />
          开始专注学习
        </button>
      </div>
    </div>
  );
}
