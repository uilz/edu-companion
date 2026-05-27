// ═══════════════════════════════════════════════
//  遗忘曲线面板 — SVG 多线图展示各知识点遗忘趋势
// ═══════════════════════════════════════════════

import { useState, useEffect } from "react";
import Card from "@/components/ui/Card";
import { RetentionData } from "@/components/dashboard/analytics/utils";

// ── API 地址：优先使用环境变量，否则回退到本地 8000 ──
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function RetentionPanel() {
  const [data, setData] = useState<RetentionData | null>(null);
  const [loading, setLoading] = useState(true);

  // 请求遗忘曲线数据
  useEffect(() => {
    fetch(`${API_BASE}/api/knowledge/retention?user_id=default_user`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;
  if (!data || data.skills.length === 0) return null;

  const colors = ["#0066FF", "#f59e0b", "#22c55e", "#a855f7", "#ec4899"];
  const days = [0, 1, 3, 7, 14, 30, 60, 90];
  const w = 500, h = 220, pad = { l: 40, r: 20, t: 20, b: 30 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;

  return (
    <Card title={`🧠 遗忘曲线预估 · 7日后平均保留 ${data.avg_retention_7d}%`} className="mb-8 !p-5">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-lg mx-auto">
        {/* 网格线（保留率参考线） */}
        {[0, 25, 50, 75, 100].map((v) => (
          <line key={v} x1={pad.l} y1={pad.t + ph * (1 - v / 100)}
            x2={pad.l + pw} y2={pad.t + ph * (1 - v / 100)}
            stroke="#1a1a1a" strokeWidth={0.5} />
        ))}
        {/* X 轴标签（天） */}
        {days.map((d, i) => (
          <text key={d} x={pad.l + (pw * i) / (days.length - 1)} y={h - 4}
            textAnchor="middle" fill="#525252" fontSize={9}>{d === 0 ? "现在" : `${d}天`}</text>
        ))}
        {/* 各知识点遗忘曲线（最多5条，每条不同颜色） */}
        {data.skills.slice(0, 5).map((skill, si) => (
          <polyline key={skill.skill_id}
            points={skill.curve.map((p, i) =>
              `${pad.l + (pw * i) / (days.length - 1)},${pad.t + ph * (1 - p.retention / 100)}`
            ).join(" ")}
            fill="none" stroke={colors[si]} strokeWidth={2} opacity={0.8}
          />
        ))}
        {/* 图例 */}
        {data.skills.slice(0, 5).map((skill, si) => (
          <text key={skill.skill_id} x={pad.l + pw + 8} y={pad.t + si * 16 + 4}
            fill={colors[si]} fontSize={9}>{skill.label}</text>
        ))}
      </svg>
      {/* 高风险知识点提醒 */}
      {data.at_risk.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--color-surface)]">
          <div className="text-xs text-[var(--color-text-muted)] mb-1">
            ⚠️ 7天后保持率 &lt; 50% 的高风险知识点：
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.at_risk.map((s) => (
              <span key={s.skill_id} className="text-xs px-2 py-0.5 border border-[#f59e0b] text-[#f59e0b]">
                {s.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
