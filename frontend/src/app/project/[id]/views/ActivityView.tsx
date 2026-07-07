"use client";

// ============================================================
//  ActivityView — 活动流 (Task #89 重写 Timeline)
// ============================================================

import { useEffect, useState } from "react";
import { Edit3, Flag, Link2, Clock } from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { ProjectViewProps, formatDate } from "../types";

interface ActivityEvent {
  id: string;
  ts: string;
  icon: React.ReactNode;
  color: string;
  title: string;
  detail: string;
  onClick?: () => void;
}

interface MilestoneRow {
  id: string;
  milestone_name: string;
  marked_at: string;
}

export function ActivityView({
  nodes,
  onOpenNode,
  projectId,
}: ProjectViewProps & { projectId: string }) {
  const [milestones, setMilestones] = useState<MilestoneRow[]>([]);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await authedFetch(`${API_BASE}/api/projects/${projectId}/milestones`);
        if (cancelled) return;
        const json = await res.json();
        setMilestones(json.milestones || []);
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // 节点编辑/完成事件
  const nodeEvents: ActivityEvent[] = nodes
    .filter((n) => n.updated_at)
    .sort(
      (a, b) =>
        new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime(),
    )
    .slice(0, 30)
    .map<ActivityEvent>((n) => ({
      id: `node-${n.id}`,
      ts: n.updated_at,
      icon: n.completed_at ? (
        <Flag size={14} className="text-success" />
      ) : (
        <Edit3 size={14} className="text-info" />
      ),
      color: n.completed_at ? "border-l-green-500" : "border-l-blue-500",
      title: n.completed_at ? `完成节点: ${n.title}` : `编辑节点: ${n.title}`,
      detail: `${formatDate(n.updated_at)} · v${n.version}`,
      onClick: () => onOpenNode(n),
    }));

  // 里程碑事件
  const milestoneEvents: ActivityEvent[] = milestones.map<ActivityEvent>((m) => ({
    id: `m-${m.id}`,
    ts: m.marked_at,
    icon: <Flag size={14} className="text-warning" />,
    color: "border-l-amber-500",
    title: `里程碑: ${m.milestone_name}`,
    detail: formatDate(m.marked_at),
  }));

  // 引用事件 (linked_node_ids 非空)
  const refEvents: ActivityEvent[] = nodes
    .filter((n) => (n.linked_node_ids || []).length > 0)
    .map<ActivityEvent>((n) => ({
      id: `ref-${n.id}`,
      ts: n.updated_at,
      icon: <Link2 size={14} className="text-accent" />,
      color: "border-l-purple-500",
      title: `建立关联: ${n.title} → ${n.linked_node_ids.length} 节点`,
      detail: formatDate(n.updated_at),
      onClick: () => onOpenNode(n),
    }));

  // 合并按时间倒序
  const all: ActivityEvent[] = [...nodeEvents, ...milestoneEvents, ...refEvents]
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())
    .slice(0, 50);

  if (all.length === 0) {
    return (
      <div>
        <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider mb-3">
          活动流
        </h3>
        <div className="text-center text-ink-secondary py-20 border border-dashed border-divider rounded-lg">
          <Clock size={40} className="mx-auto mb-3 opacity-50" />
          <p>暂无活动。开始编辑节点或标记里程碑后会显示在此。</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
          活动流
        </h3>
        <span className="text-xs text-ink-secondary">
          节点编辑 / 完成 / 里程碑 / 引用 事件，按时间倒序
        </span>
      </div>
      <div className="relative pl-6 border-l-2 border-divider space-y-3">
        {all.map((ev) => (
          <button
            key={ev.id}
            onClick={ev.onClick}
            disabled={!ev.onClick}
            className={`w-full text-left p-3 rounded-lg bg-surface border border-divider ${
              ev.onClick ? "hover:border-accent cursor-pointer" : "cursor-default"
            } border-l-4 ${ev.color} transition`}
          >
            <div className="flex items-center gap-2 text-xs text-ink-secondary mb-1">
              {ev.icon}
              <span>{ev.title}</span>
            </div>
            <div className="text-xs text-ink-secondary ml-6">{ev.detail}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
