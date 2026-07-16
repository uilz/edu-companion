"use client";

import type { Exp04State } from "@/lib/exp04/types";

const STAGES: Exp04State[] = ["ENTER", "LEARN", "SELF_VALIDATION", "OBSERVATION", "REFLECTION"];

function normalize(state: Exp04State): Exp04State {
  if (state === "COGNITIVE_SEARCH") return "LEARN";
  return state;
}

interface Props {
  currentState: Exp04State;
}

export default function ProgressBar({ currentState }: Props) {
  const normalized = normalize(currentState);
  const index = STAGES.indexOf(normalized);
  const progress =
    index < 0 ? 0 : index === 0 ? 5 : Math.round((index / (STAGES.length - 1)) * 100);

  return (
    <div className="h-[3px] w-full bg-divider-soft relative overflow-hidden">
      <div
        className="absolute left-0 top-0 bottom-0 bg-accent rounded-r transition-all duration-500"
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
