// ═══════════════════════════════════════════════
//  趋势图组件 — 纯 SVG 线形图（题量趋势）
// ═══════════════════════════════════════════════

import { DailyPoint } from "@/components/dashboard/analytics/utils";

export function TrendChart({ data }: { data: DailyPoint[] }) {
  const w = 600, h = 160, pad = { t: 20, r: 20, b: 30, l: 40 };
  const pw = w - pad.l - pad.r;
  const ph = h - pad.t - pad.b;

  const maxQ = Math.max(...data.map((d) => d.questions), 1);
  const xs = data.map((_, i) => pad.l + (i / Math.max(data.length - 1, 1)) * pw);
  const ys = data.map((d) => pad.t + ph - (d.questions / maxQ) * ph);

  const pointsQ = xs.map((x, i) => `${x},${ys[i].toFixed(1)}`).join(" ");
  const maxY = pad.t + ph;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" style={{ fontFamily: "inherit" }}>
      {/* 网格线 */}
      {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
        const y = pad.t + ph * (1 - frac);
        return (
          <g key={frac}>
            <line x1={pad.l} y1={y} x2={w - pad.r} y2={y} stroke="var(--color-border)" strokeWidth="0.5" />
            <text x={pad.l - 8} y={y + 4} textAnchor="end" fill="var(--color-text-muted)" fontSize="10">
              {Math.round(maxQ * frac)}
            </text>
          </g>
        );
      })}
      {/* 日期标签 */}
      {data.map((d, i) => (
        <text
          key={d.date}
          x={xs[i]}
          y={maxY + 18}
          textAnchor="middle"
          fill="var(--color-text-muted)"
          fontSize="9"
        >
          {d.date}
        </text>
      ))}
      {/* 面积填充 */}
      <polygon
        points={`${xs[0]},${maxY} ${pointsQ} ${xs[xs.length - 1]},${maxY}`}
        fill="var(--color-accent)"
        opacity="0.08"
      />
      {/* 折线 */}
      <polyline
        points={pointsQ}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 数据点圆点 */}
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r="3" fill="var(--color-accent)" />
      ))}
    </svg>
  );
}
