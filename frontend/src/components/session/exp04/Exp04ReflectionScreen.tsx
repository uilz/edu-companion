// ============================================================
// EXP-04 V2 · REFLECTION Screen
//
// "今天最大的变化是什么？"
//   - 一个温柔的问题，不是考试
//   - 大输入框
//   - 可以跳过（P3, 最小记录）
//   - 安静、留白
// ============================================================

"use client";

import { useState, useCallback } from "react";
import { Loader2 } from "lucide-react";

interface ReflectionScreenProps {
  engine: any;
  currentState: string;
  onSkip: () => Promise<void>;
  onSubmit: (content: string) => Promise<void>;
  transitioning: boolean;
}

export default function Exp04ReflectionScreen({
  engine,
  onSkip,
  onSubmit,
  transitioning,
}: ReflectionScreenProps) {
  const [text, setText] = useState("");

  const handleSubmit = useCallback(async () => {
    if (transitioning) return;
    await onSubmit(text.trim() || "（跳过）");
  }, [text, transitioning, onSubmit]);

  const handleSkip = useCallback(async () => {
    if (transitioning) return;
    await onSkip();
  }, [transitioning, onSkip]);

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-auto">
        <div className="max-w-lg mx-auto px-5 pt-12">
          {/* 标题 */}
          <p className="text-xs text-ink-muted tracking-[2px] uppercase mb-4 font-medium">
            Reflection
          </p>

          <h1 className="text-[28px] font-bold text-ink-primary leading-[1.2] mb-3 tracking-tight">
            今天最大的变化是什么？
          </h1>

          <p className="text-base text-ink-muted leading-relaxed mb-8">
            不用写很多。一句话也可以。理解上的任何变化都值得记下来。
          </p>

          {/* 输入框 */}
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="比如：我以前以为 TCP 只是建立连接，现在发现它的核心是可靠……"
            disabled={transitioning}
            className="w-full min-h-[200px] p-5 rounded-2xl bg-white border border-border/60 text-base leading-relaxed text-ink-primary resize-none outline-none focus:border-[#F4B400] transition-colors placeholder:text-ink-muted/50"
          />
        </div>
      </div>

      {/* 底部 */}
      <div className="border-t border-border/50 px-5 py-4">
        <div className="max-w-lg mx-auto flex gap-3">
          <button
            onClick={handleSkip}
            disabled={transitioning}
            className="flex-1 h-14 rounded-xl bg-white border border-border/60 text-ink-muted text-base font-medium hover:bg-surface transition-colors disabled:opacity-40"
          >
            跳过
          </button>
          <button
            onClick={handleSubmit}
            disabled={transitioning}
            className="flex-1 h-14 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors disabled:opacity-50"
          >
            {transitioning ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={18} className="animate-spin" />
                保存中
              </span>
            ) : (
              "记下来"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
