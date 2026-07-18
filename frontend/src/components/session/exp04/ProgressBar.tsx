"use client";

import type { SessionStage } from "@/lib/exp04/types";
import { getStageIndex } from "@/lib/exp04/types";

interface Props {
  currentState: SessionStage;
}

export default function ProgressBar({ currentState }: Props) {
  const index = getStageIndex(currentState);
  // enter=5%, chat=33%, reflect=66%, finish=100%
  const progress = index < 0 ? 0 : index === 0 ? 5 : Math.round((index / 3) * 100);

  return (
    <div className="h-[3px] w-full bg-divider-soft relative overflow-hidden">
      <div
        className="absolute left-0 top-0 bottom-0 bg-accent rounded-r transition-all duration-500"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
