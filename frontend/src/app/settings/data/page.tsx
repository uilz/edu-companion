"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Database, Trash2, Download, Loader2, ChevronLeft,
  BookOpen, MessageSquare, GitGraph, FileText, Brain,
  AlertTriangle, RefreshCw,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { StatCard } from "@/components/ui/StatCard";

// ── 类型 ──
interface OverviewData {
  partitions: number;
  domains: number;
  topics: number;
  conversations: number;
  knowledge_graphs: number;
  graph_nodes: number;
  graph_edges: number;
  practice_sessions?: number;
  question_banks?: number;
  questions?: number;
  explain_cards?: number;
  messages?: number;
  materials?: number;
}

interface PartitionItem {
  partition: {
    id: string;
    name: string;
  };
  domain_count: number;
  topic_count: number;
  conversation_count: number;
}

interface GraphItem {
  dir_id: string;
  partition_name: string;
  name: string;
  version: number;
  node_count: number;
  edge_count: number;
}

interface SessionItem {
  id: string;
  status: string;
  total_count: number;
  score?: number;
  created_at: string;
  started_at: string;
}

interface CardItem {
  id: string;
  bank_id?: string;
  front_text?: string;
  selected_text?: string;
  depth?: number;
  collapsed?: boolean;
  status?: string;
  created_at?: string;
}

interface MaterialItem {
  material_id?: string;
  id?: string;
  file_name?: string;
  original_name?: string;
  file_type?: string;
  mime_type?: string;
  status?: string;
  processing_status?: string;
  created_at?: string;
}

type Tab = "overview" | "partitions" | "graphs" | "sessions" | "cards" | "materials";

// ── 格式化函数 ──
function fmtDate(d?: string) { return d?.slice(0, 16).replace("T", " ") || "-"; }

// ── 组件 ──
export default function DataManagementPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [partitions, setPartitions] = useState<PartitionItem[]>([]);
  const [graphs, setGraphs] = useState<GraphItem[]>([]);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  // ── 加载概览 ──
  const fetchOverview = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await authedFetch(`/api/data/overview`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setOverview(data.overview);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  // ── 加载分区 ──
  const fetchPartitions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/data/partitions`);
      const data = await res.json();
      setPartitions(data.partitions || []);
    } catch {} finally { setLoading(false); }
  }, []);

  // ── 加载知识图谱 ──
  const fetchGraphs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/data/knowledge-graphs`);
      const data = await res.json();
      setGraphs(data.knowledge_graphs || []);
    } catch {} finally { setLoading(false); }
  }, []);

  // ── 加载练习会话 ──
  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/data/practice-sessions`);
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch {} finally { setLoading(false); }
  }, []);

  // ── 加载解释卡片 ──
  const fetchCards = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/data/explain-cards`);
      const data = await res.json();
      setCards(data.cards || []);
    } catch {} finally { setLoading(false); }
  }, []);

  // ── 加载材料 ──
  const fetchMaterials = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/data/materials`);
      const data = await res.json();
      setMaterials(data.materials || []);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  useEffect(() => {
    if (tab === "partitions") fetchPartitions();
    else if (tab === "graphs") fetchGraphs();
    else if (tab === "sessions") fetchSessions();
    else if (tab === "cards") fetchCards();
    else if (tab === "materials") fetchMaterials();
  }, [tab, fetchPartitions, fetchGraphs, fetchSessions, fetchCards, fetchMaterials]);

  // ── 删除操作 ──
  const handleDeletePartition = async (id: string) => {
    if (!confirm("确定删除该分区及其所有子数据（领域、专题、对话、知识图谱）？此操作不可撤销！")) return;
    setDeleting(id);
    try {
      await authedFetch(`/api/data/partition/${id}`, { method: "DELETE" });
      fetchPartitions();
      fetchOverview();
    } catch {} finally { setDeleting(null); }
  };

  const handleDeleteGraph = async (id: string) => {
    if (!confirm("确定删除该知识图谱？")) return;
    setDeleting(id);
    try {
      await authedFetch(`/api/data/knowledge-graph/${id}`, { method: "DELETE" });
      fetchGraphs();
      fetchOverview();
    } catch {} finally { setDeleting(null); }
  };

  const handleDeleteSession = async (id: string) => {
    if (!confirm("确定删除该练习会话？")) return;
    setDeleting(id);
    try {
      await authedFetch(`/api/data/practice-session/${id}`, { method: "DELETE" });
      fetchSessions();
      fetchOverview();
    } catch {} finally { setDeleting(null); }
  };

  const handleDeleteCard = async (id: string) => {
    if (!confirm("确定删除该解释卡片？")) return;
    setDeleting(id);
    try {
      await authedFetch(`/api/data/explain-card/${id}`, { method: "DELETE" });
      fetchCards();
      fetchOverview();
    } catch {} finally { setDeleting(null); }
  };

  // ── 导出 ──
  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await authedFetch(`/api/data/export`, { method: "POST" });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `edu-companion-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {} finally { setExporting(false); }
  };

  // ── 标签按钮 ──
  const tabBtn = (key: Tab, label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setTab(key)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
        tab === key
          ? "bg-accent text-white"
          : "text-muted hover:text hover:bg-surface"
      }`}
    >
      {icon}{label}
    </button>
  );

  return (
    <main className="min-h-screen bg-page">
      <div className="max-w-5xl mx-auto px-6 py-10">
        {/* 头部 */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/settings" className="p-1.5 rounded-md hover:bg-surface transition-colors">
            <ChevronLeft size={18} className="text-muted" />
          </Link>
          <h1 className="text-2xl font-semibold text">学习数据管理</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-warning/20 dark:bg-warning/10 text-warning dark:text-warning font-medium">
            高阶功能
          </span>
        </div>

        {/* 操作栏 */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-1 flex-wrap">
            {tabBtn("overview", "概览", <Database size={13} />)}
            {tabBtn("partitions", "分区", <BookOpen size={13} />)}
            {tabBtn("graphs", "知识图谱", <GitGraph size={13} />)}
            {tabBtn("sessions", "练习会话", <Brain size={13} />)}
            {tabBtn("cards", "解释卡片", <MessageSquare size={13} />)}
            {tabBtn("materials", "材料", <FileText size={13} />)}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchOverview}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs text-muted hover:text hover:bg-surface transition-colors">
              <RefreshCw size={12} />刷新
            </button>
            <button onClick={handleExport} disabled={exporting}
              className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs bg-accent text-white hover:opacity-90 disabled:opacity-50 transition-all">
              {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
              {exporting ? "导出中..." : "导出全部数据"}
            </button>
          </div>
        </div>

        {/* 内容区 */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={20} className="animate-spin text-muted" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center py-20 gap-2 text-sm text-error">
            <AlertTriangle size={16} />{error}
          </div>
        ) : (
          <div className="space-y-4">
            {/* 概览 */}
            {tab === "overview" && overview && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard colorScheme="indigo" label="分区" value={overview.partitions} icon={<BookOpen size={16} />} />
                  <StatCard colorScheme="indigo" label="领域" value={overview.domains} icon={<GitGraph size={16} />} />
                  <StatCard colorScheme="indigo" label="专题" value={overview.topics} icon={<FileText size={16} />} />
                  <StatCard colorScheme="indigo" label="对话" value={overview.conversations} icon={<MessageSquare size={16} />} />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard label="知识图谱" value={overview.knowledge_graphs} colorScheme="purple" icon={<GitGraph size={16} />} />
                  <StatCard label="图谱节点" value={overview.graph_nodes} colorScheme="purple" icon={<GitGraph size={16} />} />
                  <StatCard label="图谱边" value={overview.graph_edges} colorScheme="purple" icon={<GitGraph size={16} />} />
                  <StatCard label="练习会话" value={overview.practice_sessions ?? "-"} colorScheme="green" icon={<Brain size={16} />} />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard label="题库" value={overview.question_banks ?? "-"} colorScheme="amber" icon={<FileText size={16} />} />
                  <StatCard label="题目" value={overview.questions ?? "-"} colorScheme="amber" icon={<FileText size={16} />} />
                  <StatCard label="解释卡片" value={overview.explain_cards ?? "-"} colorScheme="rose" icon={<MessageSquare size={16} />} />
                  <StatCard label="消息" value={overview.messages ?? "-"} colorScheme="indigo" icon={<MessageSquare size={16} />} />
                </div>
              </div>
            )}

            {/* 分区列表 */}
            {tab === "partitions" && (
              <DataTable
                columns={["分区名称", "领域数", "专题数", "对话数", "操作"]}
                empty="暂无分区数据"
              >
                {partitions.map((p) => (
                  <tr key={p.partition?.id} className="border-b border hover:bg-surface/50 transition-colors">
                    <td className="px-4 py-3 text-sm font-medium">{p.partition?.name || "未知"}</td>
                    <td className="px-4 py-3 text-sm text-center">{p.domain_count}</td>
                    <td className="px-4 py-3 text-sm text-center">{p.topic_count}</td>
                    <td className="px-4 py-3 text-sm text-center">{p.conversation_count}</td>
                    <td className="px-4 py-3 text-center">
                      <button onClick={() => handleDeletePartition(p.partition?.id)}
                        disabled={deleting === p.partition?.id}
                        className="p-1.5 rounded text-muted hover:text-error hover:bg-error/10 transition-colors disabled:opacity-50"
                        title="删除分区">
                        {deleting === p.partition?.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}

            {/* 知识图谱列表 */}
            {tab === "graphs" && (
              <DataTable
                columns={["所属分区", "图谱名称", "版本", "节点数", "边数", "操作"]}
                empty="暂无知识图谱"
              >
                {graphs.map((g) => (
                  <tr key={g.dir_id} className="border-b border hover:bg-surface/50 transition-colors">
                    <td className="px-4 py-3 text-sm font-medium">{g.partition_name}</td>
                    <td className="px-4 py-3 text-sm">{g.name}</td>
                    <td className="px-4 py-3 text-sm text-center">v{g.version}</td>
                    <td className="px-4 py-3 text-sm text-center">{g.node_count}</td>
                    <td className="px-4 py-3 text-sm text-center">{g.edge_count}</td>
                    <td className="px-4 py-3 text-center">
                      <button onClick={() => handleDeleteGraph(g.dir_id)}
                        disabled={deleting === g.dir_id}
                        className="p-1.5 rounded text-muted hover:text-error hover:bg-error/10 transition-colors disabled:opacity-50"
                        title="删除图谱">
                        {deleting === g.dir_id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}

            {/* 练习会话列表 */}
            {tab === "sessions" && (
              <DataTable
                columns={["ID", "状态", "题数", "得分", "创建时间", "操作"]}
                empty="暂无练习会话"
              >
                {sessions.map((s) => (
                  <tr key={s.id} className="border-b border hover:bg-surface/50 transition-colors">
                    <td className="px-4 py-3 text-xs font-mono truncate max-w-[120px]">{s.id}</td>
                    <td className="px-4 py-3 text-sm text-center">
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${s.status === "completed" ? "bg-success/20 dark:bg-success/10 text-success" : "bg-warning/20 dark:bg-warning/10 text-warning"}`}>
                        {s.status === "completed" ? "已完成" : s.status === "active" ? "进行中" : s.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-center">{s.total_count}</td>
                    <td className="px-4 py-3 text-sm text-center">{s.score != null ? `${s.score}%` : "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted">{fmtDate(s.created_at)}</td>
                    <td className="px-4 py-3 text-center">
                      <button onClick={() => handleDeleteSession(s.id)}
                        disabled={deleting === s.id}
                        className="p-1.5 rounded text-muted hover:text-error hover:bg-error/10 transition-colors disabled:opacity-50"
                        title="删除">
                        {deleting === s.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}

            {/* 解释卡片列表 */}
            {tab === "cards" && (
              <DataTable
                columns={["ID", "选中文本", "深度", "折叠", "操作"]}
                empty="暂无解释卡片"
              >
                {cards.map((c) => (
                  <tr key={c.id} className="border-b border hover:bg-surface/50 transition-colors">
                    <td className="px-4 py-3 text-xs font-mono truncate max-w-[100px]">{c.id}</td>
                    <td className="px-4 py-3 text-sm truncate max-w-[200px]">{c.selected_text || "-"}</td>
                    <td className="px-4 py-3 text-sm text-center">{c.depth}</td>
                    <td className="px-4 py-3 text-sm text-center">{c.collapsed ? "是" : "否"}</td>
                    <td className="px-4 py-3 text-center">
                      <button onClick={() => handleDeleteCard(c.id)}
                        disabled={deleting === c.id}
                        className="p-1.5 rounded text-muted hover:text-error hover:bg-error/10 transition-colors disabled:opacity-50"
                        title="删除">
                        {deleting === c.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                      </button>
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}

            {/* 材料列表 */}
            {tab === "materials" && (
              <DataTable
                columns={["ID", "文件名", "类型", "状态", "创建时间"]}
                empty="暂无材料"
              >
                {materials.map((m) => (
                  <tr key={m.material_id || m.id} className="border-b border hover:bg-surface/50 transition-colors">
                    <td className="px-4 py-3 text-xs font-mono truncate max-w-[100px]">{m.material_id || m.id}</td>
                    <td className="px-4 py-3 text-sm font-medium">{m.file_name || m.original_name || "-"}</td>
                    <td className="px-4 py-3 text-sm text-center">{m.file_type || m.mime_type || "-"}</td>
                    <td className="px-4 py-3 text-sm text-center">{m.status || m.processing_status || "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted">{fmtDate(m.created_at)}</td>
                  </tr>
                ))}
              </DataTable>
            )}
          </div>
        )}
      </div>
    </main>
  );
}



// ── 数据表格 ──
function DataTable({ columns, empty, children }: { columns: string[]; empty: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-surface border-b border">
              {columns.map((col, i) => (
                <th key={i} className="px-4 py-2.5 text-xs font-medium text-muted text-left">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-divider">
            {React.Children.count(children) === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-muted">
                  {empty}
                </td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}