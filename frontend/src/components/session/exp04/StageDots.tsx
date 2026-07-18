"use client";

import type { Exp04State } from "@/lib/exp04/types";

const STAGES: Exp04State[] = ["ENTER", "LEARN", "SELF_VALIDATION", "REFLECTION"];

function normalize(state: Exp04State): Exp04State {
  if (state === "COGNITIVE_SEARCH") return "LEARN";
  return state;
}

interface Props {
  currentState: Exp04State;
}

export default function StageDots({ currentState }: Props) {
  const normalized = normalize(currentState);
  const activeIndex = STAGES.indexOf(normalized);

  return (
    <div className="flex items-center gap-1" aria-label="session-stages">
      {STAGES.map((stage, i) => {
        const isActive = i === activeIndex;
        const isDone = i < activeIndex;
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
