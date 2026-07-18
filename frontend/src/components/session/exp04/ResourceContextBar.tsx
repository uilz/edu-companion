"use client";

import { RESOURCES, type ResourceKey } from "./ResourcesSidebar";

interface Props {
  resourceKey: ResourceKey | null;
  onClose: () => void;
}

const RESOURCE_MAP: Record<string, { icon: string; label: string; sublabel: string }> = {};
RESOURCES.forEach((r) => { RESOURCE_MAP[r.key] = r; });

export default function ResourceContextBar({ resourceKey, onClose }: Props) {
  if (!resourceKey || !RESOURCE_MAP[resourceKey]) return null;

  const r = RESOURCE_MAP[resourceKey];

  return (
    <div className="rcb-root">
      <span className="rcb-icon">{r.icon}</span>
      <div className="rcb-info">
        <span className="rcb-label">{r.label}</span>
        <span className="rcb-context">{r.sublabel}</span>
      </div>
      <button className="rcb-close" onClick={onClose} title="关闭资源上下文">✕</button>
    </div>
  );
}
