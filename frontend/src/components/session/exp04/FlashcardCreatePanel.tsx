"use client";

import { useState } from "react";
import { X, Loader2 } from "lucide-react";
import { createSessionFlashcard } from "@/lib/api/session-tool-api";
import type { FlashCard } from "@/lib/api/flashcard-api";

interface Props {
  sessionId: string;
  defaultFront?: string;
  onCreated: (card: FlashCard) => void;
  onClose: () => void;
}

export default function FlashcardCreatePanel({
  sessionId,
  defaultFront = "",
  onCreated,
  onClose,
}: Props) {
  const [front, setFront] = useState(defaultFront);
  const [back, setBack] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!front.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await createSessionFlashcard(sessionId, {
        front_text: front.trim(),
        back_text: back.trim(),
        tags: ["session"],
      });
      onCreated(result.card);
      setFront("");
      setBack("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-page">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface/80 backdrop-blur">
        <span className="text-sm font-medium text-ink-primary">记一张闪卡</span>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-hover text-ink-muted">
          <X size={20} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-6">
        <div className="max-w-lg mx-auto space-y-4">
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">正面（问题/概念）</label>
            <textarea
              value={front}
              onChange={(e) => setFront(e.target.value)}
              placeholder="写一个问题或关键词…"
              className="w-full min-h-[120px] p-4 rounded-2xl bg-white border border-border/60 text-base leading-relaxed text-ink-primary resize-none outline-none focus:border-[#F4B400] transition-colors placeholder:text-ink-muted/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1.5">背面（答案/解释）</label>
            <textarea
              value={back}
              onChange={(e) => setBack(e.target.value)}
              placeholder="写下答案或解释…"
              className="w-full min-h-[160px] p-4 rounded-2xl bg-white border border-border/60 text-base leading-relaxed text-ink-primary resize-none outline-none focus:border-[#F4B400] transition-colors placeholder:text-ink-muted/50"
            />
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>
      </div>

      <div className="border-t border-border/50 px-5 py-4 bg-surface/80 backdrop-blur">
        <div className="max-w-lg mx-auto flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 h-12 rounded-xl bg-white border border-border/60 text-ink-primary font-medium hover:bg-surface transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleCreate}
            disabled={!front.trim() || loading}
            className="flex-1 h-12 rounded-xl bg-[#F4B400] text-white font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-40"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={18} className="animate-spin" />
                保存中…
              </span>
            ) : (
              "保存"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
