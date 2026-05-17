"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { ZoomIn, ZoomOut, Maximize2, Info, X } from "lucide-react";
import Card from "@/components/ui/Card";

interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  subject: string;
  mastery: number;
  description: string;
}

interface GraphEdge {
  from: string;
  to: string;
  label: string;
}

const nodes: GraphNode[] = [
  {
    id: "calc-basics",
    label: "极限与连续",
    x: 400,
    y: 80,
    subject: "高等数学",
    mastery: 90,
    description: "函数极限的定义、极限运算法则、连续函数的性质。",
  },
  {
    id: "calc-deriv",
    label: "导数与微分",
    x: 250,
    y: 220,
    subject: "高等数学",
    mastery: 78,
    description: "导数的定义、求导法则、隐函数求导、参数方程求导。",
  },
  {
    id: "calc-integral",
    label: "积分学",
    x: 550,
    y: 220,
    subject: "高等数学",
    mastery: 65,
    description: "不定积分、定积分、牛顿-莱布尼茨公式。",
  },
  {
    id: "linear-algebra",
    label: "矩阵与行列式",
    x: 100,
    y: 370,
    subject: "线性代数",
    mastery: 72,
    description: "矩阵运算、行列式计算、逆矩阵。",
  },
  {
    id: "eigenvalue",
    label: "特征值与特征向量",
    x: 250,
    y: 450,
    subject: "线性代数",
    mastery: 55,
    description: "特征多项式、特征值计算、对角化。",
  },
  {
    id: "vectors",
    label: "向量与空间解析",
    x: 550,
    y: 370,
    subject: "大学物理",
    mastery: 80,
    description: "向量代数、空间直线与平面方程。",
  },
  {
    id: "em-field",
    label: "电磁场理论",
    x: 550,
    y: 500,
    subject: "大学物理",
    mastery: 48,
    description: "麦克斯韦方程组、电磁波。",
  },
  {
    id: "probability",
    label: "概率与分布",
    x: 400,
    y: 550,
    subject: "概率论",
    mastery: 62,
    description: "随机变量、常见概率分布、期望与方差。",
  },
];

const edges: GraphEdge[] = [
  { from: "calc-basics", to: "calc-deriv", label: "基础" },
  { from: "calc-basics", to: "calc-integral", label: "基础" },
  { from: "calc-deriv", to: "linear-algebra", label: "工具" },
  { from: "calc-integral", to: "vectors", label: "应用" },
  { from: "linear-algebra", to: "eigenvalue", label: "扩展" },
  { from: "vectors", to: "em-field", label: "理论" },
  { from: "calc-integral", to: "probability", label: "基础" },
  { from: "vectors", to: "probability", label: "工具" },
];

const subjectColors: Record<string, string> = {
  "高等数学": "#0066FF",
  "线性代数": "#22c55e",
  "大学物理": "#f59e0b",
  "概率论": "#a855f7",
};

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as Element).tagName === "rect") {
      setIsPanning(true);
      panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isPanning) return;
      setPan({
        x: e.clientX - panStart.current.x,
        y: e.clientY - panStart.current.y,
      });
    },
    [isPanning]
  );

  const handleMouseUp = () => setIsPanning(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((z) => Math.min(2, Math.max(0.3, z + delta)));
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-8">
          知识图谱
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Graph area */}
          <div className="lg:col-span-3">
            <div className="border border-[#262626] bg-[#0d0d0d] overflow-hidden relative">
              {/* Controls */}
              <div className="absolute top-4 right-4 z-10 flex gap-1">
                <button
                  onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
                  className="w-8 h-8 flex items-center justify-center bg-[#1a1a1a] border border-[#262626] text-[#a3a3a3] hover:text-white transition-colors"
                >
                  <ZoomIn size={14} />
                </button>
                <button
                  onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}
                  className="w-8 h-8 flex items-center justify-center bg-[#1a1a1a] border border-[#262626] text-[#a3a3a3] hover:text-white transition-colors"
                >
                  <ZoomOut size={14} />
                </button>
                <button
                  onClick={resetView}
                  className="w-8 h-8 flex items-center justify-center bg-[#1a1a1a] border border-[#262626] text-[#a3a3a3] hover:text-white transition-colors"
                >
                  <Maximize2 size={14} />
                </button>
              </div>

              <svg
                ref={svgRef}
                className="w-full"
                viewBox="0 0 700 620"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                style={{ cursor: isPanning ? "grabbing" : "grab" }}
              >
                <g transform={`translate(${pan.x / 2},${pan.y / 2}) scale(${zoom})`}>
                  {/* Edges */}
                  {edges.map((edge) => {
                    const fromNode = nodes.find((n) => n.id === edge.from)!;
                    const toNode = nodes.find((n) => n.id === edge.to)!;
                    const midX = (fromNode.x + toNode.x) / 2;
                    const midY = (fromNode.y + toNode.y) / 2;
                    return (
                      <g key={`${edge.from}-${edge.to}`}>
                        <line
                          x1={fromNode.x}
                          y1={fromNode.y}
                          x2={toNode.x}
                          y2={toNode.y}
                          stroke="#262626"
                          strokeWidth={1.5}
                        />
                        <text
                          x={midX}
                          y={midY - 6}
                          textAnchor="middle"
                          fill="#525252"
                          fontSize={10}
                        >
                          {edge.label}
                        </text>
                      </g>
                    );
                  })}

                  {/* Nodes */}
                  {nodes.map((node) => {
                    const isSelected = selectedNode?.id === node.id;
                    const color = subjectColors[node.subject] || "#737373";
                    return (
                      <g
                        key={node.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedNode(isSelected ? null : node);
                        }}
                        style={{ cursor: "pointer" }}
                      >
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={isSelected ? 28 : 24}
                          fill={isSelected ? color : "#0d0d0d"}
                          stroke={color}
                          strokeWidth={isSelected ? 2.5 : 1.5}
                          style={{ transition: "all 0.2s" }}
                        />
                        <text
                          x={node.x}
                          y={node.y + 1}
                          textAnchor="middle"
                          dominantBaseline="middle"
                          fill={isSelected ? "#ffffff" : color}
                          fontSize={10}
                          fontWeight={600}
                        >
                          {node.label.slice(0, 4)}
                        </text>
                        {/* Mastery indicator ring */}
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={30}
                          fill="none"
                          stroke={color}
                          strokeWidth={1}
                          strokeDasharray={`${(node.mastery / 100) * 189} 189`}
                          strokeDashoffset={-47}
                          opacity={0.4}
                        />
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Legend */}
            <Card title="图例">
              <div className="space-y-2.5">
                {Object.entries(subjectColors).map(([subject, color]) => (
                  <div key={subject} className="flex items-center gap-2.5 text-sm">
                    <div
                      className="w-3 h-3 flex-shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-[#a3a3a3]">{subject}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-3 border-t border-[#1a1a1a] text-xs text-[#525252]">
                圆环表示掌握进度
              </div>
            </Card>

            {/* Node detail */}
            {selectedNode ? (
              <Card title="知识点详情">
                <div className="space-y-3">
                  <div>
                    <div className="text-lg font-bold text-white">
                      {selectedNode.label}
                    </div>
                    <div className="text-xs text-[#737373] mt-0.5">
                      {selectedNode.subject}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-[#737373] mb-1">掌握度</div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-[#1a1a1a] h-2">
                        <div
                          className="h-full"
                          style={{
                            width: `${selectedNode.mastery}%`,
                            backgroundColor: subjectColors[selectedNode.subject],
                          }}
                        />
                      </div>
                      <span className="text-sm text-white font-medium">
                        {selectedNode.mastery}%
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-[#737373] mb-1">描述</div>
                    <div className="text-sm text-[#a3a3a3] leading-relaxed">
                      {selectedNode.description}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-[#737373] mb-1">前置知识</div>
                    <div className="flex flex-wrap gap-1.5">
                      {edges
                        .filter((e) => e.to === selectedNode.id)
                        .map((e) => {
                          const fromNode = nodes.find((n) => n.id === e.from);
                          return (
                            <span
                              key={e.from}
                              onClick={() => fromNode && setSelectedNode(fromNode)}
                              className="text-xs px-2 py-1 border border-[#262626] text-[#a3a3a3] hover:border-[#525252] hover:text-white cursor-pointer transition-colors"
                            >
                              {fromNode?.label}
                            </span>
                          );
                        })}
                      {edges.filter((e) => e.to === selectedNode.id).length === 0 && (
                        <span className="text-xs text-[#525252]">无</span>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            ) : (
              <Card>
                <div className="text-center py-4">
                  <Info size={20} className="text-[#525252] mx-auto mb-2" />
                  <div className="text-sm text-[#737373]">点击节点查看详情</div>
                </div>
              </Card>
            )}

            {/* Stats */}
            <Card title="统计">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#737373]">知识点</span>
                  <span className="text-white font-medium">{nodes.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737373]">关联数</span>
                  <span className="text-white font-medium">{edges.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#737373]">平均掌握</span>
                  <span className="text-white font-medium">
                    {Math.round(nodes.reduce((s, n) => s + n.mastery, 0) / nodes.length)}%
                  </span>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}
