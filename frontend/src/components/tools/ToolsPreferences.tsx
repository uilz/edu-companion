"use client";

import { useState } from "react";

// ── Types ──────────────────────────────────────────────────

interface PrefsState {
  quote: boolean;
  serif: boolean;
  source: boolean;
}

// ── Component ──────────────────────────────────────────────

interface Props {
  onClose: () => void;
}

export default function ToolsPreferences({ onClose }: Props) {
  const [prefs, setPrefs] = useState<PrefsState>({
    quote: true,
    serif: true,
    source: true,
  });

  const toggle = (key: keyof PrefsState) => {
    setPrefs((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="max-w-[560px] mx-auto px-5 py-6">
      {/* ── 氛围 ── */}
      <SectionTitle text="氛围" first />
      <div className="bg-surface rounded-[18px] overflow-hidden border border-divider-soft mb-5">
        <PrefRow
          label="首页一言"
          checked={prefs.quote}
          onChange={() => toggle("quote")}
        />
        <PrefRow
          label="信息源推送"
          checked={prefs.source}
          onChange={() => toggle("source")}
          last
        />
      </div>

      {/* ── 已订阅信息源 ── */}
      <SectionTitle text="已订阅信息源" />
      <SourceCard
        icon="📰"
        bg="bg-teal-500/10"
        name="每日数学"
        desc="每天一个小概念"
        defaultOn
      />
      <SourceCard
        icon="💡"
        bg="bg-purple-500/10"
        name="编程灵感"
        desc="每周三推送"
        defaultOn={false}
      />
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────

function SectionTitle({ text, first }: { text: string; first?: boolean }) {
  return (
    <p
      className={`text-[12px] font-semibold text-ink-muted uppercase tracking-wider mb-3 ${
        first ? "mt-0" : "mt-5"
      }`}
    >
      {text}
    </p>
  );
}

function PrefRow({
  label,
  checked,
  onChange,
  last,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
  last?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between px-5 py-4 ${
        !last ? "border-b border-divider-soft" : ""
      }`}
    >
      <span className="text-[15px]">{label}</span>
      <button
        onClick={onChange}
        className={`relative w-11 h-[26px] rounded-full transition-colors duration-200 ${
          checked ? "bg-[#34c759]" : "bg-[#e5e5ea]"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-[22px] h-[22px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
            checked ? "translate-x-[18px]" : ""
          }`}
        />
      </button>
    </div>
  );
}

function SourceCard({
  icon,
  bg,
  name,
  desc,
  defaultOn,
}: {
  icon: string;
  bg: string;
  name: string;
  desc: string;
  defaultOn: boolean;
}) {
  const [on, setOn] = useState(defaultOn);

  return (
    <div className="flex items-start gap-2.5 p-4 bg-surface rounded-md mb-2 border border-divider-soft">
      <div
        className={`w-8 h-8 rounded-lg grid place-items-center text-[15px] flex-shrink-0 ${bg}`}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[14px] font-semibold">{name}</div>
        <div className="text-[12px] text-ink-muted">{desc}</div>
      </div>
      <button
        onClick={() => setOn(!on)}
        className={`relative w-11 h-[26px] rounded-full transition-colors duration-200 flex-shrink-0 ${
          on ? "bg-[#34c759]" : "bg-[#e5e5ea]"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-[22px] h-[22px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
            on ? "translate-x-[18px]" : ""
          }`}
        />
      </button>
    </div>
  );
}
