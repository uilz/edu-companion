// ============================================================
// / — AppleGo Landing（Vision Layer 0）
// 展示：问候 + 记忆叙事 + CTA + 工作区列表 + 搜索
// ============================================================

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authedFetch } from "@/lib/api/api";
import Landing from "@/components/studio/Landing";
import SearchOverlay from "@/components/studio/SearchOverlay";
import type { WorkspaceItem, LandingMemory } from "@/components/studio/Landing";

// ── Types ──────────────────────────────────────────────────
interface BackendWorkspace {
  id: string;
  name: string;
  icon: string;
  active_sessions_count: number;
  completed_sessions_count: number;
}

interface SearchResult {
  type: string;
  title: string;
  snippet: string;
  meta: string;
  badge: string;
}

const DEFAULT_MEMORY: LandingMemory = {
  workspaceName: "数学基础",
  topic: "ε-δ 定义",
};

const DEFAULT_WORKSPACES: WorkspaceItem[] = [
  { id: "math", icon: "M", name: "数学基础", activeCount: 1, completedCount: 2 },
  { id: "network", icon: "N", name: "计算机网络", activeCount: 1, completedCount: 1 },
];

export default function RootPage() {
  const router = useRouter();

  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>(DEFAULT_WORKSPACES);
  const [memory, setMemory] = useState<LandingMemory>(DEFAULT_MEMORY);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    authedFetch("/api/workspaces")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: BackendWorkspace[] | null) => {
        if (data?.length) {
          setWorkspaces(
            data.map((w) => ({
              id: w.id,
              icon: w.icon,
              name: w.name,
              activeCount: w.active_sessions_count,
              completedCount: w.completed_sessions_count,
            })),
          );
        }
      })
      .catch(() => {});
  }, []);

  const handleEnter = (workspaceId: string) => {
    router.push(`/workspace/${workspaceId}`);
  };

  const handleSearch = (query: string) => {
    setSearchOpen(true);
  };

  return (
    <>
      <Landing
        workspaces={workspaces}
        memory={memory}
        onEnter={handleEnter}
        onSearch={handleSearch}
      />
      <SearchOverlay
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSearch={async (q: string) => {
          // Landing search: try all workspaces or generic search
          return [];
        }}
      />
    </>
  );
}
