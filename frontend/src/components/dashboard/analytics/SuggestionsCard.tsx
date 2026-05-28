// ═══════════════════════════════════════════════
//  建议行动卡片 — 基于学习数据的个性化建议
// ═══════════════════════════════════════════════

import Link from "next/link";
import Card from "@/components/ui/Card";
import { Suggestion } from "./utils";

export function SuggestionsCard({ suggestions }: { suggestions: Suggestion[] }) {
  if (suggestions.length === 0) return null;

  return (
    <Card title="🎯 建议行动" className="!p-5">
      <div className="space-y-2">
        {suggestions.map((s, i) => (
          <div
            key={i}
            className="flex items-start gap-2 text-sm text-[var(--color-text-secondary)] leading-relaxed"
          >
            <span className="text-[var(--color-accent)] mt-0.5">•</span>
            <span>
              {s.text}
              {s.link && (
                <Link
                  href={s.link}
                  className="ml-1 text-[var(--color-accent)] hover:underline text-xs"
                >
                  {s.action || "去看看"} →
                </Link>
              )}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
