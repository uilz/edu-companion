"use client";

interface Props {
  onPractice: () => void;
}

/**
 * 顿悟庆祝 — breakthrough 体验
 * 庆祝用户理解 + "趁热来一道" 按钮
 */
export default function BreakthroughCelebration({ onPractice }: Props) {
  return (
    <div className="mx-5 mb-4 rounded-xl border border-green-200 bg-green-50 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="flex items-center gap-3">
        <div className="text-2xl">🎉</div>
        <div className="flex-1">
          <p className="text-sm font-medium text-green-800 mb-1">你理解了！</p>
          <p className="text-[13px] text-green-600 leading-relaxed">
            这个感觉很棒。趁热来一道，巩固一下？
          </p>
        </div>
        <button
          onClick={onPractice}
          className="px-4 py-2 rounded-full bg-green-500 text-white text-[13px] font-medium hover:bg-green-600 transition-colors flex-shrink-0"
        >
          来一道题
        </button>
      </div>
    </div>
  );
}
