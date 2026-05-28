// ═══════════════════════════════════════════════
//  知识掌握度 + 错因分布（双栏并排）
// ═══════════════════════════════════════════════

import Link from "next/link";
import Card from "@/components/ui/Card";
import { MasteryBar, ErrorDist, ERROR_LABELS, MASTERY_EMOJI } from "./utils";

export function MasteryErrorsCard({
  masteryBars,
  errorDistribution,
}: {
  masteryBars: MasteryBar[];
  errorDistribution: ErrorDist[];
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      {/* 知识掌握度 */}
      <Card title="🔥 知识掌握度" className="!p-5">
        {masteryBars.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">暂无数据，答几道题就出来了</p>
        ) : (
          <div className="space-y-3">
            {masteryBars.map((mb) => {
              const pct = Math.round(mb.p_known * 100);
              const color =
                mb.p_known >= 0.8
                  ? "var(--color-success)"
                  : mb.p_known >= 0.5
                  ? "var(--color-warning)"
                  : "var(--color-error)";
              return (
                <div key={mb.skill_id}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-[var(--color-text-secondary)] truncate max-w-[140px]">
                      {MASTERY_EMOJI[mb.mastery_level] || ""} {mb.skill_id}
                    </span>
                    <span className="text-xs text-[var(--color-text-muted)]">{pct}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-[var(--color-surface)]">
                    <div
                      className="h-full transition-all"
                      style={{ width: `${pct}%`, backgroundColor: color }}
                    />
                  </div>
                  <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                    {mb.correct_count}/{mb.attempt_count}正确 · {mb.mastery_level}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* 错因分布 */}
      <Card title="📊 错因分布" className="!p-5">
        {errorDistribution.length === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">暂无错题，继续保持！</p>
        ) : (
          <div className="space-y-3">
            {errorDistribution.map((e) => {
              const label = ERROR_LABELS[e.type] || e.type;
              return (
                <div key={e.type}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-[var(--color-text-secondary)]">{label}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {e.count}次 · {(e.pct * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-[var(--color-surface)]">
                    <div
                      className="h-full bg-[var(--color-error)] transition-all"
                      style={{ width: `${(e.pct * 100).toFixed(0)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {errorDistribution.length > 0 && (
          <Link
            href="/errors"
            className="inline-block mt-4 text-[11px] text-[var(--color-accent)] hover:underline"
          >
            查看全部错题 →
          </Link>
        )}
      </Card>
    </div>
  );
}
