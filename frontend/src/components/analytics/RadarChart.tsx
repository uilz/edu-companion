"use client";

import { useState, useEffect } from "react";
import { Loader2, Target } from "lucide-react";
import Card from "@/components/ui/Card";
import { knowledgeNodesApi, type KnowledgeNode } from "@/lib/api/knowledge-tree-api";
import { useCurrentUserId } from "@/hooks/useCurrentUserId";

// ── Types ──

interface GraphNode {
  id: string;
  label: string;
  subject: string;
  mastery: number;        // 0-100
  mastery_level: string;
  can_practice: boolean;
  blocked_by: string[];
  attempt_count: number;
}

interface GraphData {
  nodes: GraphNode[];
  subjects: string[];
}

// ── Mastery color ──
function masteryColor(mastery: number): string {
  if (mastery >= 80) return "#22c55e";
  if (mastery >= 50) return "var(--color-warning)";
  if (mastery >= 20) return "#f97316";
  return "var(--color-error)";
}

function masteryLevelLabel(mastery: number): string {
  if (mastery >= 80) return "已掌握";
  if (mastery >= 50) return "发展中";
  if (mastery >= 20) return "初学";
  if (mastery > 0) return "薄弱";
  return "未接触";
}

// ── Radar Chart SVG ──

function RadarSVG({
  nodes,
  onSelect,
  selectedId,
}: {
  nodes: GraphNode[];
  onSelect: (id: string | null) => void;
  selectedId: string | null;
}) {
  const w = 400, h = 400;
  const cx = w / 2, cy = h / 2;
  const maxR = 150;
  const levels = 3;

  if (nodes.length < 3) {
    return (
      <div className="flex items-center justify-center h-[400px] text-xs text-[var(--color-text-muted)]">
        需要 ≥3 个知识点才能绘制雷达图
      </div>
    );
  }

  const n = nodes.length;
  const angleStep = (2 * Math.PI) / n;
  const startAngle = -Math.PI / 2; // start from top

  // Helper: polar → cartesian
  const polar = (i: number, r: number) => ({
    x: cx + r * Math.cos(startAngle + i * angleStep),
    y: cy + r * Math.sin(startAngle + i * angleStep),
  });

  // Levels (rings)
  const rings = Array.from({ length: levels }, (_, li) => {
    const r = (maxR * (li + 1)) / levels;
    return nodes.map((_, i) => polar(i, r));
  });

  // Mastery polygon
  const masteryPoints = nodes.map((node, i) => {
    const r = Math.max(4, (node.mastery / 100) * maxR); // min 4px so 0% still visible
    return polar(i, r);
  });

  // Axis lines + labels
  const axes = nodes.map((node, i) => {
    const outer = polar(i, maxR + 22);
    const labelR = maxR + 38;
    const label = polar(i, labelR);
    return { node, outer, label };
  });

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full max-w-md mx-auto"
      style={{ fontFamily: "inherit" }}
    >
      {/* Rings */}
      {rings.map((ring, li) => (
        <polygon
          key={li}
          points={ring.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={0.5}
        />
      ))}

      {/* Ring labels */}
      {rings[rings.length - 1].map((_, i) => {
        if (i !== 0) return null;
        return (
          <g key="ring-labels">
            {[1, 2, 3].map((lvl) => {
              const p = polar(0, (maxR * lvl) / levels);
              return (
                <text
                  key={lvl}
                  x={p.x + 6}
                  y={p.y - 2}
                  fill="var(--color-text-muted)"
                  fontSize={8}
                >
                  {Math.round((lvl / levels) * 100)}%
                </text>
              );
            })}
          </g>
        );
      })}

      {/* Axis lines */}
      {axes.map(({ outer }, i) => {
        const origin = polar(i, 0);
        return (
          <line
            key={i}
            x1={origin.x}
            y1={origin.y}
            x2={outer.x}
            y2={outer.y}
            stroke="var(--color-border)"
            strokeWidth={0.5}
            strokeDasharray="3,3"
          />
        );
      })}

      {/* Mastery polygon fill */}
      <polygon
        points={masteryPoints.map((p) => `${p.x},${p.y}`).join(" ")}
        fill="var(--color-accent)"
        opacity={0.12}
      />

      {/* Mastery polygon stroke */}
      <polygon
        points={masteryPoints.map((p) => `${p.x},${p.y}`).join(" ")}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth={2}
        strokeLinejoin="round"
      />

      {/* Node dots */}
      {nodes.map((node, i) => {
        const p = masteryPoints[i];
        const isSel = selectedId === node.id;
        return (
          <g
            key={node.id}
            onClick={(e) => {
              e.stopPropagation();
              onSelect(isSel ? null : node.id);
            }}
            style={{ cursor: "pointer" }}
          >
            <circle
              cx={p.x}
              cy={p.y}
              r={isSel ? 7 : 5}
              fill={masteryColor(node.mastery)}
              stroke={isSel ? "#fff" : "transparent"}
              strokeWidth={2}
              style={{ transition: "all 0.2s" }}
            />
            <title>
              {node.label} — {node.mastery}% ({masteryLevelLabel(node.mastery)})
            </title>
          </g>
        );
      })}

      {/* Labels */}
      {axes.map(({ node, label }) => (
        <text
          key={node.id}
          x={label.x}
          y={label.y}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="var(--color-text-secondary)"
          fontSize={9}
          fontWeight={500}
        >
          {node.label.length > 6 ? node.label.slice(0, 5) + "…" : node.label}
        </text>
      ))}
    </svg>
  );
}

// ── Main component ──

export default function RadarChart() {
  const userId = useCurrentUserId();
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [subject, setSubject] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const fetchGraph = async (subj: string) => {
    if (!userId) return;
    setLoading(true);
    try {
      const json = await knowledgeNodesApi.list();
      const knodes: KnowledgeNode[] = json.nodes || [];
      // 按 domain 过滤
      const filtered = subj ? knodes.filter(n => n.level === "domain" && n.label === subj) : knodes;
      const domainNodes = knodes.filter(n => n.level === "domain");
      const subjects = Array.from(new Set(domainNodes.map(n => n.label)));

      const graphNodes: GraphNode[] = filtered.map(n => ({
        id: n.id,
        label: n.label,
        subject: n.level === "domain" ? n.label : (domainNodes.find(d => d.id === n.parent_id)?.label || ""),
        mastery: Math.round((n.mastery || 0) * 100),
        mastery_level: n.mastery_level || "未接触",
        can_practice: true,
        blocked_by: [],
        attempt_count: 0,
      }));

      setGraphData({ nodes: graphNodes, subjects });
    } catch (e) {
      setGraphData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph(subject);
  }, [subject]);

  const nodes = graphData?.nodes || [];
  // Take up to 8 nodes sorted by mastery (lowest first = most need attention)
  const displayNodes = [...nodes]
    .sort((a, b) => a.mastery - b.mastery)
    .slice(0, 8);

  const subjects = graphData?.subjects || [];
  const selectedNode = selectedId ? nodes.find((n) => n.id === selectedId) : null;

  if (loading) {
    return (
      <Card title="🎯 知识雷达图" className="!p-5">
        <div className="flex items-center justify-center py-12">
          <Loader2 size={20} className="animate-spin text-[var(--color-accent)]" />
        </div>
      </Card>
    );
  }

  if (nodes.length === 0) {
    return (
      <Card title="🎯 知识雷达图" className="!p-5">
        <p className="text-xs text-[var(--color-text-muted)] py-8 text-center">
          暂无知识图谱数据
        </p>
      </Card>
    );
  }

  return (
    <Card title="🎯 知识雷达图" className="!p-5">
      {/* Subject filter */}
      {subjects.length > 0 && (
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[10px] text-[var(--color-text-muted)]">学科:</span>
          <select
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              setSelectedId(null);
            }}
            className="text-[10px] px-2 py-1 border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] outline-none"
          >
            <option value="">全部</option>
            {subjects.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
            {displayNodes.length}/{nodes.length} 个知识点
          </span>
        </div>
      )}

      {/* Chart */}
      <RadarSVG
        nodes={displayNodes}
        onSelect={setSelectedId}
        selectedId={selectedId}
      />

      {/* Selected node detail */}
      {selectedNode && (
        <div className="mt-4 pt-3 border-t border-[var(--color-surface)]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-[var(--color-text)]">
              {selectedNode.label}
            </span>
            <span
              className="text-xs px-2 py-0.5"
              style={{
                color: masteryColor(selectedNode.mastery),
                border: `1px solid ${masteryColor(selectedNode.mastery)}`,
              }}
            >
              {selectedNode.mastery}% · {masteryLevelLabel(selectedNode.mastery)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] text-[var(--color-text-muted)]">
            <div>
              学科: <span className="text-[var(--color-text-secondary)]">{selectedNode.subject}</span>
            </div>
            <div>
              练习: <span className="text-[var(--color-text-secondary)]">{selectedNode.attempt_count} 次</span>
            </div>
            <div>
              状态:{" "}
              {selectedNode.can_practice ? (
                <span className="text-[#22c55e]">可练习</span>
              ) : (
                <span className="text-[#f97316]">前置未满足</span>
              )}
            </div>
            {selectedNode.blocked_by.length > 0 && (
              <div className="col-span-2">
                前置依赖:{" "}
                <span className="text-[var(--color-text-secondary)]">
                  {selectedNode.blocked_by.join(", ")}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--color-surface)] text-[9px] text-[var(--color-text-muted)]">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2" style={{ backgroundColor: "#22c55e" }} />
          已掌握 ≥80%
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2" style={{ backgroundColor: "var(--color-warning)" }} />
          发展中 ≥50%
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2" style={{ backgroundColor: "#f97316" }} />
          初学 ≥20%
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2" style={{ backgroundColor: "var(--color-error)" }} />
          薄弱 &lt;20%
        </span>
      </div>
    </Card>
  );
}
