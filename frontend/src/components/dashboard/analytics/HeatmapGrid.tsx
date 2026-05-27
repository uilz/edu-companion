// ═══════════════════════════════════════════════
//  热力图组件 — 星期 × 时段答题分布
// ═══════════════════════════════════════════════

import { HeatmapCell } from "@/components/dashboard/analytics/utils";

export function HeatmapGrid({ data }: { data: HeatmapCell[] }) {
  const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const hours = [8, 10, 14, 16, 20, 22];
  const maxQ = Math.max(...data.map((d) => d.count), 1);

  const getCell = (day: number, hour: number) =>
    data.find((d) => d.day === day && d.hour === hour)?.count ?? 0;

  // 根据题量计算单元格背景色（透明度渐变）
  const bg = (q: number) => {
    if (q === 0) return "var(--color-surface)";
    const alpha = 0.2 + (q / maxQ) * 0.8;
    return `rgba(0,102,255,${alpha.toFixed(2)})`;
  };

  return (
    <div className="overflow-x-auto">
      <div className="grid gap-px" style={{ gridTemplateColumns: `60px repeat(7, 1fr)` }}>
        {/* 表头：星期 */}
        <div />
        {dayNames.map((d) => (
          <div key={d} className="text-center text-[10px] text-[var(--color-text-muted)] py-1">{d}</div>
        ))}
        {/* 数据行：各时段 */}
        {hours.map((h) => (
          <div key={h} className="contents">
            <div className="text-[10px] text-[var(--color-text-muted)] flex items-center justify-end pr-2">
              {h}:00
            </div>
            {[1, 2, 3, 4, 5, 6, 7].map((day) => {
              const q = getCell(day, h);
              return (
                <div
                  key={day}
                  className="aspect-square flex items-center justify-center text-[9px] font-mono text-[var(--color-text-secondary)]"
                  style={{ backgroundColor: bg(q) }}
                  title={`${dayNames[day - 1]} ${h}:00 — ${q}题`}
                >
                  {q > 0 ? q : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {/* 图例：少 → 多 */}
      <div className="flex items-center gap-2 mt-3 justify-end text-[10px] text-[var(--color-text-muted)]">
        <span>少</span>
        <div className="w-3 h-3" style={{ backgroundColor: "var(--color-surface)" }} />
        <div className="w-3 h-3" style={{ backgroundColor: "rgba(0,102,255,0.3)" }} />
        <div className="w-3 h-3" style={{ backgroundColor: "rgba(0,102,255,0.6)" }} />
        <div className="w-3 h-3" style={{ backgroundColor: "rgba(0,102,255,0.9)" }} />
        <span>多</span>
      </div>
    </div>
  );
}
