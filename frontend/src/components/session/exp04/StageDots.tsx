"use client";

import type { SessionStage } from "@/lib/exp04/types";
import { getStageIndex } from "@/lib/exp04/types";

const STAGE_LABELS: SessionStage[] = ["enter", "chat", "reflect"];

interface Props {
  currentState: SessionStage;
}

export default function StageDots({ currentState }: Props) {
  const index = getStageIndex(currentState);

  return (
    <div className="flex items-center gap-1" aria-label="session-stages">
      {STAGE_LABELS.map((stage, i) => {
        const isActive = i === index;
        const isDone = i < index;
        return (
          <span
            key={stage}
            className={`h-1.5 rounded-full transition-all duration-300 ${
              isActive
                ? "w-4 bg-accent"
                : isDone
                  ? "w-1.5 bg-accent"
                  : "w-1.5 bg-border"
            }`}
          />
        );
      })}
    </div>
  );
}
