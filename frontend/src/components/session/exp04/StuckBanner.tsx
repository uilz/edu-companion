"use client";

import { AlertTriangle } from "lucide-react";
import type { SessionMode } from "@/lib/exp04/types";

interface Props {
  onAction: (action: "retry" | "canvas" | "reflect") => void;
}

/**
 * 卡住横幅 — stuck-detected 体验
 * 显示检测到卡顿 + 3 个行动选项
 */
export default function StuckBanner({ onAction }: Props) {
  return (
    <div className="mx-5 mb-4 rounded-xl border border-orange-200 bg-orange-50 p-4 animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-full bg-orange-100 grid place-items-center flex-shrink-0 mt-0.5">
          <AlertTriangle size={16} className="text-orange-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-orange-800 mb-1">
            苹果果注意到你在这里停了一会儿
          </p>
          <p className="text-[13px] text-orange-600 leading-relaxed mb-3">
            要不要试试换个方式？
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onAction("retry")}
              className="px-3 py-1.5 rounded-full bg-orange-500 text-white text-[12px] font-medium hover:bg-orange-600 transition-colors"
            >
              换个角度再讲一遍
            </button>
            <button
              onClick={() => onAction("canvas")}
              className="px-3 py-1.5 rounded-full bg-white text-orange-700 text-[12px] font-medium border border-orange-200 hover:bg-orange-50 transition-colors"
            >
              打开画布看看
            </button>
            <button
              onClick={() => onAction("reflect")}
              className="px-3 py-1.5 rounded-full bg-white text-orange-700 text-[12px] font-medium border border-orange-200 hover:bg-orange-50 transition-colors"
            >
              差不多了
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
