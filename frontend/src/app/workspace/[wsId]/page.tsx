// ============================================================
// /workspace/[wsId] — AppleGo Studio Workspace
// Vision Studio Grid 5 区布局 + Workspace 级视图
// ============================================================

"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { authedFetch } from "@/lib/api/api";
import StudioLayout from "@/components/studio/StudioLayout";
import StudioHeader from "@/components/studio/StudioHeader";
import TimelineSidebar from "@/components/studio/TimelineSidebar";
import type { TimelineSection, TimelineItem } from "@/components/studio/TimelineSidebar";
import CanvasView from "@/components/studio/CanvasView";
import SearchOverlay from "@/components/studio/SearchOverlay";
import type { SearchResult } from "@/components/studio/SearchOverlay";
import type { WorkspaceItem } from "@/components/studio/Landing";
import { default as CompanionPanel } from "@/components/session/exp04/StudioCompanion";
import BottomDock from "@/components/session/exp04/BottomDock";
import type { ToolKey } from "@/components/session/exp04/BottomDock";

// ── Types ──────────────────────────────────────────────────

interface WorkspaceInfo {
  id: string;
  name: string;
  icon: string;
  total_sessions: number;
  active_sessions: number;
  overall_progress: number;
}

interface SessionSummary {
  id: string;
  title: string;
  description: string;
  stage: string;
  progress: number;
  estimated_minutes: number;
  status: string;
  created_at: string;
}

interface BackendTimelineGroup {
  date_label: string;
  items: Array<{
    type: string;
    title: string;
    meta: string;
    session_id?: string;
  }>;
}

interface BackendRoadmapStage {
  name: string;
  status: "done" | "active" | "next" | "future";
  desc: string;
  stats: string;
  badge: string;
}

interface BackendRoadmapData {
  title: string;
  overall_progress: number;
  stages: BackendRoadmapStage[];
}

interface BackendWorkspace {
  id: string;
  name: string;
  icon: string;
  active_sessions_count: number;
  completed_sessions_count: number;
}

// ── Helpers ────────────────────────────────────────────────

function toHeaderWorkspaceItem(w: BackendWorkspace): WorkspaceItem {
  return {
    id: w.id,
    name: w.name,
    icon: w.icon,
    activeCount: w.active_sessions_count,
    completedCount: w.completed_sessions_count,
  };
}

function toTimelineSections(groups: BackendTimelineGroup[]): TimelineSection[] {
  return groups.map((g) => ({
    dateLabel: g.date_label,
    sections: g.items.map((item): TimelineItem => ({
      type: item.type as TimelineItem["type"],
      title: item.title,
      meta: item.meta,
      sessionId: item.session_id,
      isActive: false,
      isStatic: !item.session_id,
    })),
  }));
}

// ── Page ───────────────────────────────────────────────────

export default function WorkspacePage() {
  const router = useRouter();
  const params = useParams<{ wsId: string }>();
  const wsId = params.wsId;

  const [workspace, setWorkspace] = useState<WorkspaceInfo | null>(null);
  const [workspaceList, setWorkspaceList] = useState<BackendWorkspace[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [timeline, setTimeline] = useState<TimelineSection[]>([]);
  const [roadmap, setRoadmap] = useState<BackendRoadmapData | null>(null);
  const [loading, setLoading] = useState(true);

  const [currentView, setCurrentView] = useState<"flow" | "sessions" | "plan">("flow");
  const [layoutMode, setLayoutMode] = useState<"explore" | "dialogue" | "focus">("explore");
  const [activeTool, setActiveTool] = useState<ToolKey | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [surfaceTab, setSurfaceTab] = useState("chat");

  // ── Fetch ──
  useEffect(() => {
    if (!wsId) return;
    setLoading(true);
    Promise.all([
      authedFetch(`/api/workspaces/${wsId}`).then((r) => (r.ok ? r.json() : null)),
      authedFetch(`/api/workspaces/${wsId}/sessions`).then((r) => (r.ok ? r.json() : [])),
      authedFetch(`/api/workspaces/${wsId}/timeline`).then((r) => (r.ok ? r.json() : [])),
      authedFetch(`/api/workspaces/${wsId}/roadmap`).then((r) => (r.ok ? r.json() : null)),
      authedFetch("/api/workspaces").then((r) => (r.ok ? r.json() : [])),
    ])
      .then(([ws, sess, tl, rm, wss]) => {
        if (ws) setWorkspace(ws);
        setSessions(sess || []);
        setTimeline(toTimelineSections(tl || []));
        if (rm) setRoadmap(rm);
        if (wss?.length) setWorkspaceList(wss);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [wsId]);

  // ── Current workspace as header item ──
  const currentWsItem: WorkspaceItem | null = useMemo(() => {
    const found = workspaceList.find((w) => w.id === wsId);
    return found ? toHeaderWorkspaceItem(found) : null;
  }, [workspaceList, wsId]);

  // ── Header workspace list ──
  const headerWsList: WorkspaceItem[] = useMemo(
    () => workspaceList.map(toHeaderWorkspaceItem),
    [workspaceList],
  );

  // ── Actions ──
  const handleBack = useCallback(() => router.push("/"), [router]);

  const handleWorkspaceChange = useCallback(
    (newWsId: string) => router.push(`/workspace/${newWsId}`),
    [router],
  );

  const handleOpenSession = useCallback(
    (sessionId: string) => router.push(`/session/${sessionId}`),
    [router],
  );

  const handleSearch = useCallback(
    async (query: string): Promise<SearchResult[]> => {
      if (!query.trim()) return [];
      try {
        const res = await authedFetch(
          `/api/workspaces/${wsId}/search?q=${encodeURIComponent(query)}`,
        );
        if (res.ok) {
          const data = await res.json();
          return data.map((item: any) => ({
            icon: item.type || "资源",
            title: item.title || "",
            snippet: item.snippet || "",
            meta: item.meta || "",
            badge: (item.badge || "资源") as SearchResult["badge"],
          }));
        }
      } catch (e) {
        console.error("search error", e);
      }
      return [];
    },
    [wsId],
  );

  const handleOpenTool = useCallback((tool: ToolKey) => {
    setActiveTool(tool);
    if (tool === "search") setSearchOpen(true);
  }, []);

  // ── Compute derived ──
  const missionLabel =
    currentView === "flow" ? "学习流" : currentView === "sessions" ? "会话列表" : "学习路线";
  const missionTitle = workspace?.name || "工作区";

  const activeSession = sessions.find((s) => s.status === "active");

  // ── Loading ──
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#f7f3ed]">
        <p className="text-[#a69c8f] text-sm">加载中…</p>
      </div>
    );
  }

  return (
    <>
      <StudioLayout layoutMode={layoutMode} setLayoutMode={setLayoutMode}
        header={
          <StudioHeader
            workspaces={headerWsList}
            currentWorkspace={currentWsItem}
            missionLabel={missionLabel}
            missionTitle={missionTitle}
            inSession={false}
            progress={workspace?.overall_progress || 0}
            layoutMode={layoutMode}
            onModeChange={setLayoutMode}
            onSearch={() => setSearchOpen(true)}
            onBack={handleBack}
            onWorkspaceChange={handleWorkspaceChange}
          />
        }
        sidebar={
          <TimelineSidebar timeline={timeline} onOpenSession={handleOpenSession} />
        }
        canvas={
          <CanvasView
            currentView={currentView}
            learningFlow={{
              todayProgress: activeSession
                ? { title: activeSession.title, desc: activeSession.description || "", pct: activeSession.progress, remainingMin: activeSession.estimated_minutes }
                : { title: "极限与连续", desc: "用 ε-δ 语言验证函数的连续性", pct: 42, remainingMin: 15 },
              aiGreeting: {
                message: "上次你停在 ε-δ 定义。我发现你不是不会，而是当尝试证明存在性的时候，容易把 δ 和 ε 的关系搞混。今天我们继续这里。",
                autoActions: ["已打开「高等数学」第 2 章", "Canvas 保留了你昨天的图", "聊天已回滚到昨天结束的位置"],
              },
              toolFlow: [
                { label: "划选文本", status: "done" as const },
                { label: "加入导图", status: "done" as const },
                { label: "生成练习", status: "active" as const },
                { label: "更新成长", status: "pending" as const },
              ],
              messages: [
                { id: "m1", role: "ai" as const, content: '好，先看一个简单的：<strong>f(x) = x 在 x=2</strong><br>要证明连续，我们得找 δ 使得当 |x-2| < δ 时 |f(x)-2| < ε。<br><strong>你觉得 δ 应该取什么？</strong>' },
                { id: "m2", role: "user" as const, content: "δ = ε 就行吧？因为 |x-2| 直接等于 |f(x)-2|" },
              ],
              activeSurfaceTab: surfaceTab,
              onSurfaceTabChange: setSurfaceTab,
              onViewSessions: () => setCurrentView("sessions"),
              onStartSession: () => {
                if (activeSession) handleOpenSession(activeSession.id);
              },
            }}
            sessionsList={{
              sessions: sessions.map((s) => ({
                id: s.id,
                name: s.title,
                desc: s.description || "",
                progress: s.progress,
                status: (s.status === "active" ? "active" : s.progress >= 100 ? "done" : "new") as "active" | "done" | "new",
                timeLabel: s.progress >= 100 ? "已完成" : s.status === "active" ? "进行中" : `预计 ${s.estimated_minutes}min`,
              })),
              onNewSession: () => alert("新建会话"),
              onOpenSession: handleOpenSession,
            }}
            planRoadmap={
              roadmap
                ? { title: roadmap.title, overallProgress: roadmap.overall_progress, stages: roadmap.stages as any }
                : undefined
            }
          />
        }
        companion={
          <CompanionPanel
            stage="chat"
            mode="normal"
            toolState={{}}
            messageCount={2}
            sessionTitle={workspace?.name}
          />
        }
        dock={
          <BottomDock activeTool={activeTool} onOpenTool={handleOpenTool} />
        }
      />
      <SearchOverlay open={searchOpen} onClose={() => setSearchOpen(false)} onSearch={handleSearch} />
    </>
  );
}
