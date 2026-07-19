// ============================================================
// / — AppleGo Landing（Vision Layer 0）
// Demo6.0: connected to WorkspaceRuntime backend
// ============================================================

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Landing from "@/components/studio/Landing";
import SearchOverlay from "@/components/studio/SearchOverlay";
import {
  listWorkspaces,
  createWorkspace,
  enterWorkspace,
  getLandingMemory,
  searchWorkspace,
  type WorkspaceItem,
  type LandingMemory,
} from "@/lib/api/workspace-api";

const FALLBACK_MEMORY: LandingMemory = {
  workspaceName: "数学基础",
  topic: "ε-δ 定义",
  workspaceId: "",
  sessionId: null,
};

const FALLBACK_WS: WorkspaceItem[] = [
  {
    id: "math",
    icon: "M",
    name: "数学基础",
    activeCount: 1,
    completedCount: 2,
    color: "#5a8f6b",
    state: "active",
    dayCount: 0,
    createdAt: "",
  },
];

export default function RootPage() {
  const router = useRouter();

  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>(FALLBACK_WS);
  const [memory, setMemory] = useState<LandingMemory>(FALLBACK_MEMORY);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    Promise.all([listWorkspaces(), getLandingMemory()])
      .then(([ws, mem]) => {
        if (ws.length > 0) {
          setWorkspaces(ws);
        }
        if (mem) {
          setMemory(mem);
        }
      })
      .catch(() => {});
  }, []);

  const handleEnter = async (workspaceId: string, sessionId?: string) => {
    try {
      const result = await enterWorkspace(workspaceId);
      router.push(
        `/workspace/${workspaceId}?session=${result.sessionId}`
      );
    } catch {
      router.push(`/workspace/${workspaceId}`);
    }
  };

  const handleCreate = async (name: string) => {
    try {
      const ws = await createWorkspace(name);
      setWorkspaces((prev) => [ws, ...prev]);
      handleEnter(ws.id);
    } catch {
      // ignore
    }
  };

  const handleSearch = (query: string) => {
    setSearchOpen(true);
  };

  const doSearch = async (q: string) => {
    if (!q.trim()) return [];
    const results: { type: string; title: string; snippet: string; meta: string; badge: string }[] = [];
    for (const ws of workspaces) {
      const r = await searchWorkspace(ws.id, q);
      results.push(...r);
      if (results.length >= 10) break;
    }
    return results;
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
        onSearch={doSearch}
      />
    </>
  );
}
