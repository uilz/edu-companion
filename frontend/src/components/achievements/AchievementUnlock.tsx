"use client";

import { useEffect, useState } from "react";
import { Award, X } from "lucide-react";

interface UnlockedAchievement {
  id: string;
  name: string;
  icon: string;
  tier: string;
  level: number;
  description: string;
}

interface Props {
  achievement: UnlockedAchievement | null;
  onClose: () => void;
}

export default function AchievementUnlock({ achievement, onClose }: Props) {
  const [visible, setVisible] = useState(false);
  const [phase, setPhase] = useState<"enter" | "show" | "exit">("enter");

  useEffect(() => {
    if (!achievement) return;

    setVisible(true);
    setPhase("enter");

    const t1 = setTimeout(() => setPhase("show"), 500);
    const t2 = setTimeout(() => setPhase("exit"), 3500);
    const t3 = setTimeout(() => {
      setVisible(false);
      onClose();
    }, 4000);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [achievement, onClose]);

  if (!visible || !achievement) return null;

  const tierColors: Record<string, string> = {
    bronze: "#d97706",
    silver: "#94a3b8",
    gold: "#f59e0b",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[var(--color-card)] border border-[var(--color-border)] w-full max-w-sm mx-4 p-6 text-center"
        style={{
          transform: phase === "enter" ? "scale(0.5)" : "scale(1)",
          opacity: phase === "exit" ? 0 : 1,
          transition: "all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)",
        }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          <X size={16} />
        </button>

        {/* Icon */}
        <div
          className="text-6xl mb-4"
          style={{
            transform: phase === "enter" ? "scale(0) rotate(-30deg)" : "scale(1) rotate(0deg)",
            transition: "transform 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s",
          }}
        >
          {achievement.icon}
        </div>

        {/* Title */}
        <h2 className="text-xl font-bold text-[var(--color-text)] mb-2">
          🎉 成就解锁！
        </h2>
        <p
          className="text-lg font-bold mb-3"
          style={{ color: tierColors[achievement.tier] || "#f59e0b" }}
        >
          {achievement.name}
        </p>
        <p className="text-sm text-[var(--color-text-muted)]">
          {achievement.description}
        </p>

        <div className="mt-4 pt-4 border-t border-[var(--color-surface)]">
          <p className="text-[10px] text-[var(--color-text-muted)]">
            继续学习，解锁更多成就！
          </p>
        </div>
      </div>
    </div>
  );
}
