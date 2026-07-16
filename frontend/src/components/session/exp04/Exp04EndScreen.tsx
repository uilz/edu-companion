// ============================================================
// EXP-04 V2 · END Screen
//
// "今天不是获得了多少分。"
//   - 成长叙事（非指标）
//   - "今天，你已经开始能够解释……"
//   - "这会成为苹果果以后陪伴你的基础"
// ============================================================

"use client";

import { useMemo } from "react";
import { ArrowLeft, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { createConversationEngine } from "@/lib/exp04/conversation-engine";
import type { Exp04State } from "@/lib/exp04/types";

interface EndScreenProps {
  engine: ReturnType<typeof createConversationEngine>;
  reflectionContent: string | null;
  missionTitle?: string;
}

export default function Exp04EndScreen({ engine, reflectionContent, missionTitle }: EndScreenProps) {
  const router = useRouter();

  const farewell = useMemo(() => {
    if (engine?.process) {
      const output = engine.process("END" as Exp04State, "SESSION_ENDING");
      return output.message;
    }
    return null;
  }, [engine]);

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-auto flex items-center justify-center">
        <div className="max-w-lg mx-auto px-5 py-12 text-center">
          {/* 图标 */}
          <div className="w-16 h-16 rounded-2xl bg-[#FFF6E8] flex items-center justify-center mx-auto mb-6">
            <Sparkles size={28} className="text-[#A96F00]" />
          </div>

          {/* 标题 */}
          <h1 className="text-[28px] font-bold text-ink-primary leading-[1.2] mb-4 tracking-tight">
            今天就到这里
          </h1>

          {/* 成长叙事 */}
          <div className="bg-surface rounded-2xl border border-border/50 p-5 sm:p-6 mb-6 text-left">
            <p className="text-base text-ink-secondary leading-relaxed">
              {reflectionContent
                ? (
                  <>
                    <span className="font-medium text-ink-primary">你今天收获了什么？</span>
                    <br />
                    <span className="text-ink-muted mt-2 block">
                      &ldquo;{reflectionContent}&rdquo;
                    </span>
                  </>
                )
                : (
                  <>
                    <span className="font-medium text-ink-primary">
                      今天，你已经开始能够解释{missionTitle || "新的概念"}。
                    </span>
                    <br />
                    <span className="text-ink-muted mt-2 block">
                      每一次你试着用自己的话讲出来，都是在建立真正的理解。
                    </span>
                  </>
                )}
            </p>
          </div>

          {/* 苹果果的话 */}
          <div className="text-left mb-8">
            <p className="text-base text-ink-muted leading-relaxed">
              {farewell || "这会成为苹果果以后陪伴你的基础。"}
            </p>
          </div>

          {/* 返回按钮 */}
          <button
            onClick={() => router.push("/")}
            className="inline-flex items-center justify-center h-14 px-8 rounded-xl bg-[#F4B400] text-white text-base font-semibold hover:bg-[#e5a800] transition-colors"
          >
            <ArrowLeft size={18} className="mr-2" />
            返回 Today
          </button>
        </div>
      </div>
    </div>
  );
}
