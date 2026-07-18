// ============================================================
// EXP-04 V2 · END Screen
//
// Vision finish-hero:
//   🍎
//   "今天就到这里。我会记住今天。"
//   "返回首页" 按钮
// ============================================================

"use client";

import { useRouter } from "next/navigation";

export default function Exp04EndScreen() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-page flex flex-col">
      <div className="flex-1 overflow-auto flex items-center justify-center">
        <div className="max-w-lg mx-auto px-5 py-12 text-center">
          {/* 🍎 emoji */}
          <div className="text-[48px] mb-6">🍎</div>

          {/* 结束语 */}
          <p className="font-serif text-[21px] text-ink-primary leading-relaxed mb-8">
            今天就到这里。我会记住今天。
          </p>

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
