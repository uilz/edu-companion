"use client";

import type { SessionStage } from "@/lib/exp04/types";
import { getStageIndex } from "@/lib/exp04/types";

// Demo 中有 4 个 stage dots：enter → chat → reflect → finish
const ALL_STAGES: SessionStage[] = ["enter", "chat", "reflect", "finish"];

interface Props {
  currentState: SessionStage;
}

export default function StageDots({ currentState }: Props) {
  const currentIndex = getStageIndex(currentState);

  return (
    <div className="sh-stage-dots">
      {ALL_STAGES.map((stage, i) => {
        const isActive = i === currentIndex;
        const isDone = i < currentIndex;
        return (
          <span
            key={stage}
            className={`stage-dot ${isActive ? "active" : ""} ${isDone ? "done" : ""}`}
          />
        );
      })}
    </div>
  );
}
