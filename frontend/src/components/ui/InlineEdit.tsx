import { useState, useEffect } from "react";
import { Check, X } from "lucide-react";

export function InlineEdit({ value, onConfirm, onCancel, placeholder = "名称" }: {
  value: string; onConfirm: (v: string) => void; onCancel: () => void; placeholder?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => { setV(value); }, [value]);
  return (
    <div className="flex items-center gap-1 px-2 py-1" onClick={(e) => e.stopPropagation()}>
      <input value={v} onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") onConfirm(v.trim() || value); if (e.key === "Escape") onCancel(); }}
        placeholder={placeholder}
        className="flex-1 text-xs bg-[var(--color-surface)] border border-[var(--color-accent)] rounded px-2 py-1 text-[var(--color-text)] outline-none min-w-0" autoFocus
        onFocus={(e) => e.target.select()} />
      <button onClick={() => onConfirm(v.trim() || value)} className="p-0.5 text-[var(--color-success)] hover:bg-[var(--color-surface)] rounded"><Check size={12} /></button>
      <button onClick={onCancel} className="p-0.5 text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] rounded"><X size={12} /></button>
    </div>
  );
}
