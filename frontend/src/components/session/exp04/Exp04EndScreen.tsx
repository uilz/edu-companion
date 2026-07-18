// ============================================================
// EXP-04 V2 · END Screen
//
// Vision finish-hero:
//   🍎
//   "今天就到这里。我会记住今天。"
//   "下次再打开，你会变得不一样。"
//   额外：Session 统计 + 成长记录
// ============================================================

"use client";

import { useRouter } from "next/navigation";

interface Props {
  sessionTitle?: string | null;
}

export default function Exp04EndScreen({ sessionTitle }: Props) {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-auto flex items-center justify-center">
        <div className="max-w-lg mx-auto px-5 py-12 text-center">
          {/* 🍎 emoji */}
          <div className="text-[48px] mb-6">🍎</div>

          {/* 结束语 */}
          <p className="font-serif text-[21px] text-ink-primary leading-relaxed mb-3">
            今天就到这里。
          </p>

          {/* Vision 对齐：温暖的第二行 */}
          <p className="text-[21px] text-ink-primary leading-relaxed mb-2 font-serif">
            我会记住今天的。
          </p>

          {/* 新增：温暖提示 */}
          {sessionTitle && (
            <p className="text-[15px] text-ink-muted leading-relaxed mb-6 mt-4">
              「{sessionTitle}」—— 下次再打开，你会变得不一样。
            </p>
          )}

          {/* 返回首页按钮 */}
          <button
            onClick={() => router.push("/")}
            className="inline-flex items-center justify-center h-14 px-8 rounded-full border-2 border-border text-ink-primary text-base font-semibold hover:bg-surface-hover transition-colors"
          >
            返回首页
          </button>
        </div>
      </div>
    </div>
  );
}
