"use client";

// ============================================================
//  Templates Management — 模板管理
// ============================================================

import { useState } from "react";
import Link from "next/link";
import {
  ChevronLeft,
  Plus,
  Loader2,
  Trash2,
  FileText,
  Layers,
  Folder,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { useUserData } from "@/hooks/useUserData";

// ── 类型 ──

interface Template {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  structure: { nodes?: TemplateNode[] };
  placeholder_schema: Record<string, unknown> | null;
  is_system: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

interface TemplateNode {
  type: number;
  title: string;
  description?: string;
  nodes?: TemplateNode[];
  language?: string;
}

// ── 工具 ──

const CATEGORIES = [
  { value: "research", label: "主题研究" },
  { value: "math", label: "解题分析" },
  { value: "engineering", label: "项目实践" },
  { value: "reading", label: "长篇阅读" },
  { value: "training", label: "长期训练" },
];

const DEFAULT_STRUCTURE = {
  nodes: [
    {
      type: 1,
      title: "目标",
      description: "本项目要达成的目标",
      nodes: [],
    },
  ],
};

// ── 主组件 ──

export default function TemplatesPage() {
  // 任务 #49：统一使用 useUserData 自动等待 AuthContext，
  // 避免「useCurrentUserId 隐藏 authLoading 导致 useEffect 死锁」问题。
  // 注：authedFetch 返回 Response，需手动 .json()（不要写成 authedFetch<T>(...)）
  const {
    data: templatesData,
    loading,
    refetch: loadTemplates,
  } = useUserData<{ templates: Template[] }>(async () => {
    const res = await authedFetch(`${API_BASE}/api/projects/_templates/all`);
    const json = await res.json();
    return { templates: json.templates || [] };
  });
  const templates = templatesData?.templates ?? [];
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [newTemplate, setNewTemplate] = useState({
    name: "",
    description: "",
    category: "research",
    structure: JSON.stringify(DEFAULT_STRUCTURE, null, 2),
  });

  const filtered = templates.filter((t) => {
    if (filterCategory !== "all" && t.category !== filterCategory) return false;
    return true;
  });

  const handleCreate = async () => {
    if (!newTemplate.name.trim()) return;
    setCreating(true);
    try {
      let structure;
      try {
        structure = JSON.parse(newTemplate.structure);
      } catch {
        alert("结构 JSON 格式不正确");
        return;
      }
      await authedFetch(`${API_BASE}/api/projects/_templates`, {
        method: "POST",
        body: JSON.stringify({
          name: newTemplate.name,
          description: newTemplate.description || null,
          category: newTemplate.category,
          structure,
        }),
      });
      setShowCreate(false);
      setNewTemplate({
        name: "",
        description: "",
        category: "research",
        structure: JSON.stringify(DEFAULT_STRUCTURE, null, 2),
      });
      loadTemplates();
    } catch (e) {
      console.error(e);
      alert(`创建失败: ${e}`);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-full p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link
            href="/project"
            className="text-sm text-ink-secondary hover:text-ink-primary flex items-center gap-1 mb-2"
          >
            <ChevronLeft size={14} /> 返回项目列表
          </Link>
          <h1 className="text-2xl font-bold text-ink-primary tracking-tight flex items-center gap-2">
            <Layers className="text-[var(--color-accent)]" size={26} />
            模板管理
          </h1>
          <p className="text-sm text-ink-secondary mt-1">
            系统预置 + 个人模板。模板支持参数化与版本管理。
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 flex items-center gap-2"
        >
          <Plus size={16} /> 新建模板
        </button>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => setFilterCategory("all")}
          className={`px-3 py-1.5 rounded-lg text-sm ${
            filterCategory === "all"
              ? "bg-[var(--color-accent)] text-white"
              : "bg-surface text-ink-secondary hover:text-ink-primary"
          }`}
        >
          全部
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c.value}
            onClick={() => setFilterCategory(c.value)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              filterCategory === c.value
                ? "bg-[var(--color-accent)] text-white"
                : "bg-surface text-ink-secondary hover:text-ink-primary"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Templates List */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-ink-secondary">
          <Loader2 className="animate-spin" size={24} />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-ink-secondary">
          <Folder size={48} className="mx-auto mb-3 opacity-50" />
          <p>该分类下暂无模板</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((t) => {
            const nodeCount = countNodes(t.structure);
            return (
              <div
                key={t.id}
                className="rounded-xl border border-divider bg-surface p-4 hover:border-[var(--color-accent)] transition"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-lg font-semibold text-ink-primary flex-1 truncate">
                    {t.name}
                  </h3>
                  {t.is_system && (
                    <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-500">
                      系统
                    </span>
                  )}
                </div>
                {t.description && (
                  <p className="text-sm text-ink-secondary line-clamp-2 mb-3 min-h-[2.5em]">
                    {t.description}
                  </p>
                )}
                <div className="flex items-center gap-3 text-xs text-ink-secondary">
                  <span className="flex items-center gap-1">
                    <FileText size={12} /> {nodeCount} 节点
                  </span>
                  <span>v{t.version}</span>
                  {t.category && <span className="text-[var(--color-accent)]">{t.category}</span>}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <Link
                    href={`/project?template=${t.id}`}
                    className="text-xs text-[var(--color-accent)] hover:opacity-80"
                  >
                    从此模板创建项目 →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="p-4 border-b border-divider">
              <h2 className="text-lg font-semibold text-ink-primary">新建模板</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  名称 <span className="text-red-500">*</span>
                </label>
                <input
                  value={newTemplate.name}
                  onChange={(e) => setNewTemplate({ ...newTemplate, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">描述</label>
                <input
                  value={newTemplate.description}
                  onChange={(e) =>
                    setNewTemplate({ ...newTemplate, description: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">分类</label>
                <select
                  value={newTemplate.category}
                  onChange={(e) =>
                    setNewTemplate({ ...newTemplate, category: e.target.value })
                  }
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  结构（JSON）
                </label>
                <textarea
                  value={newTemplate.structure}
                  onChange={(e) =>
                    setNewTemplate({ ...newTemplate, structure: e.target.value })
                  }
                  rows={12}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-xs"
                />
                <p className="text-xs text-ink-secondary mt-1">
                  节点类型: 1=大纲 2=文本 3=数据表 4=对比 5=代码 6=附件 7=成果板
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 p-4 border-t border-divider">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 rounded-lg text-ink-secondary"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newTemplate.name.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {creating && <Loader2 className="animate-spin" size={14} />} 创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function countNodes(structure: { nodes?: TemplateNode[] }): number {
  let count = 0;
  const walk = (n?: TemplateNode[]) => {
    if (!n) return;
    for (const x of n) {
      count++;
      walk(x.nodes);
    }
  };
  walk(structure.nodes);
  return count;
}
