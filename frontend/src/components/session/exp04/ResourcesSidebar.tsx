"use client";

import { useState } from "react";

type ResourceKey = "book" | "video" | "note" | "mindmap" | "web";

interface ResourceItem {
  key: ResourceKey;
  icon: string;
  label: string;
  sublabel: string;
}

const RESOURCES: ResourceItem[] = [
  { key: "book", icon: "📖", label: "Book", sublabel: "计算机网络（第 7 版）" },
  { key: "video", icon: "🎬", label: "Video", sublabel: "TCP 三次握手深入" },
  { key: "note", icon: "📝", label: "Note", sublabel: "TCP 笔记" },
  { key: "mindmap", icon: "🧩", label: "Mind", sublabel: "三次握手" },
  { key: "web", icon: "🌐", label: "RFC", sublabel: "RFC 793" },
];

export default function ResourcesSidebar() {
  const [active, setActive] = useState<ResourceKey>("web");

  return (
    <div className="rs-root">
      <div className="rs-header">Resources</div>
      <div className="rs-list">
        {RESOURCES.map((r) => (
          <button
            key={r.key}
            className={`rs-item ${active === r.key ? "active" : ""}`}
            onClick={() => setActive(r.key)}
          >
            <span className="rs-icon">{r.icon}</span>
            <div className="rs-info">
              <div className="rs-label">{r.label}</div>
              <div className="rs-sublabel">{r.sublabel}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
