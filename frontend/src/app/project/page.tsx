"use client";

// ============================================================
//  Project List — 项目工作台首页
// ============================================================

import { useState } from "react";
import Link from "next/link";
import {
  Plus,
  Folder,
  Search,
  Loader2,
  Trash2,
  Edit3,
  Archive,
  Clock,
  Tag,
  FileText,
  ChevronRight,
  CheckCircle2,
  Circle,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { useUserData } from "@/hooks/useUserData";

// ── 类型 ──

interface Project {
  id: string;
  name: string;
  description: string | null;
  status: string;
  tags: string[];
  node_count: number;
  completed_node_count: number;
  template_id: string | null;
  created_at: string;
  updated_at: string;
}

interface Template {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  is_system: boolean;
}

// ── 工具 ──

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 16).replace("T", " ");
}

function getCompletionColor(rate: number): string {
  if (rate >= 0.8) return "text-green-500";
  if (rate >= 0.4) return "text-amber-500";
  return "text-ink-secondary";
}

// ── 主组件 ──

export default function ProjectListPage() {
  // 任务 #49：统一使用 useUserData 自动等待 AuthContext，
  // 避免「useCurrentUserId 隐藏 authLoading 导致 useEffect 死锁」问题。
  // 列表数据（项目 + 模板）并行加载，一次性提供 projects/templates。
  // 注：authedFetch 返回 Response，需手动解析 JSON（不要写成 authedFetch<T>(...)）
  const {
    data: projects,
    loading,
    refetch: loadProjects,
  } = useUserData<{ projects: Project[]; templates: Template[] }>(async () => {
    const [projRes, tplRes] = await Promise.all([
      authedFetch(`${API_BASE}/api/projects/`),
      authedFetch(`${API_BASE}/api/projects/_templates/all`),
    ]);
    const [projJson, tplJson] = await Promise.all([
      projRes.json(),
      tplRes.json(),
    ]);
    return {
      projects: projJson.projects || [],
      templates: tplJson.templates || [],
    };
  });
  const templates = projects?.templates ?? [];
  const projectList = projects?.projects ?? [];
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [showFromTemplate, setShowFromTemplate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newProject, setNewProject] = useState({
    name: "",
    description: "",
    template_id: "",
    template_version: 1,
    tags: "",
  });
  const [fromTemplate, setFromTemplate] = useState({
    template_id: "",
    name: "",
  });

  const filtered = projectList.filter((p) => {
    if (filterStatus !== "all" && p.status !== filterStatus) return false;
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const handleCreate = async () => {
    if (!newProject.name.trim()) return;
    setCreating(true);
    try {
      await authedFetch(`${API_BASE}/api/projects/`, {
        method: "POST",
        body: JSON.stringify({
          name: newProject.name,
          description: newProject.description || null,
          template_id: newProject.template_id || null,
          template_version: newProject.template_id ? newProject.template_version : null,
          tags: newProject.tags
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      setShowCreate(false);
      setNewProject({ name: "", description: "", template_id: "", template_version: 1, tags: "" });
      loadProjects();
    } catch (e) {
      console.error(e);
      alert(`创建失败: ${e}`);
    } finally {
      setCreating(false);
    }
  };

  const handleCreateFromTemplate = async () => {
    if (!fromTemplate.template_id || !fromTemplate.name.trim()) return;
    setCreating(true);
    try {
      const res = await authedFetch(
        `${API_BASE}/api/projects/from-template`,
        {
          method: "POST",
          body: JSON.stringify({
            template_id: fromTemplate.template_id,
            name: fromTemplate.name,
            placeholder_values: {},
          }),
        },
      );
      const json = await res.json();
      setShowFromTemplate(false);
      setFromTemplate({ template_id: "", name: "" });
      if (json?.id) {
        window.location.href = `/project/${json.id}`;
        return;
      }
      loadProjects();
    } catch (e) {
      console.error(e);
      alert(`创建失败: ${e}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定要删除这个项目吗？相关节点、版本、关联都会一并删除。")) return;
    try {
      await authedFetch(`${API_BASE}/api/projects/${id}`, { method: "DELETE" });
      loadProjects();
    } catch (e) {
      console.error(e);
    }
  };

  const handleArchive = async (p: Project) => {
    const newStatus = p.status === "archived" ? "active" : "archived";
    try {
      await authedFetch(`${API_BASE}/api/projects/${p.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      loadProjects();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-full p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary tracking-tight flex items-center gap-2">
            <Folder className="text-[var(--color-accent)]" size={26} />
            项目工作台
          </h1>
          <p className="text-sm text-ink-secondary mt-1">
            长期主题性研究的工作台 — 树形大纲、字段级版本、@引用、跨模块输出
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setShowFromTemplate(true)}
            className="px-4 py-2 rounded-lg border border-divider text-ink-primary hover:bg-surface-hover transition flex items-center gap-2 whitespace-nowrap"
          >
            <FileText size={16} /> 从模板创建
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 transition flex items-center gap-2 whitespace-nowrap"
          >
            <Plus size={16} /> 新建项目
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-secondary" size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索项目..."
            className="w-full pl-10 pr-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary placeholder:text-ink-secondary focus:border-[var(--color-accent)] outline-none"
          />
        </div>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
        >
          <option value="all">全部状态</option>
          <option value="active">进行中</option>
          <option value="archived">已归档</option>
          <option value="completed">已完成</option>
        </select>
        <Link
          href="/project/templates"
          className="px-3 py-2 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-surface-hover transition text-sm flex items-center gap-1 whitespace-nowrap"
        >
          管理模板 <ChevronRight size={14} />
        </Link>
      </div>

      {/* Project Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-ink-secondary">
          <Loader2 className="animate-spin" size={24} />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-ink-secondary">
          <Folder size={48} className="mx-auto mb-3 opacity-50" />
          <p>暂无项目。点击"新建项目"开始构建你的第一个工作台。</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p) => {
            const completionRate =
              p.node_count > 0 ? p.completed_node_count / p.node_count : 0;
            return (
              <div
                key={p.id}
                className="rounded-xl border border-divider bg-surface p-4 hover:border-[var(--color-accent)] transition group"
              >
                <div className="flex items-start justify-between mb-2">
                  <Link
                    href={`/project/${p.id}`}
                    className="text-lg font-semibold text-ink-primary hover:text-[var(--color-accent)] transition flex-1 truncate"
                  >
                    {p.name}
                  </Link>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
                    <button
                      onClick={() => handleArchive(p)}
                      className="p-1.5 rounded text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
                      title={p.status === "archived" ? "恢复" : "归档"}
                    >
                      <Archive size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="p-1.5 rounded text-ink-secondary hover:text-red-500 hover:bg-surface-hover"
                      title="删除"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {p.description && (
                  <p className="text-sm text-ink-secondary line-clamp-2 mb-3 min-h-[2.5em]">
                    {p.description}
                  </p>
                )}

                {p.tags && p.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {p.tags.slice(0, 3).map((t) => (
                      <span
                        key={t}
                        className="px-2 py-0.5 text-xs rounded bg-surface-hover text-ink-secondary flex items-center gap-1"
                      >
                        <Tag size={10} /> {t}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between text-xs text-ink-secondary">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <Circle size={10} />
                      {p.node_count} 节点
                    </span>
                    <span className="flex items-center gap-1">
                      <CheckCircle2 size={10} className={getCompletionColor(completionRate)} />
                      {p.completed_node_count} 完成
                    </span>
                  </div>
                  <span className="flex items-center gap-1">
                    <Clock size={10} />
                    {formatDate(p.updated_at)}
                  </span>
                </div>

                {p.node_count > 0 && (
                  <div className="mt-2 h-1 bg-surface-hover rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[var(--color-accent)] transition-all"
                      style={{ width: `${completionRate * 100}%` }}
                    />
                  </div>
                )}

                <div className="mt-2 text-xs text-ink-secondary">
                  状态: <span className="text-ink-primary">{p.status}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-ink-primary mb-4 flex items-center gap-2">
              <Plus size={18} /> 新建项目
            </h2>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  项目名称 <span className="text-red-500">*</span>
                </label>
                <input
                  value={newProject.name}
                  onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                  placeholder="例如：苏东坡主题研究"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">描述</label>
                <textarea
                  value={newProject.description}
                  onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">标签（逗号分隔）</label>
                <input
                  value={newProject.tags}
                  onChange={(e) => setNewProject({ ...newProject, tags: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                  placeholder="例如：古代文学, 苏东坡, 人物"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 rounded-lg text-ink-secondary hover:text-ink-primary"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newProject.name.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {creating && <Loader2 className="animate-spin" size={14} />}
                创建
              </button>
            </div>
          </div>
        </div>
      )}

      {/* From Template Modal */}
      {showFromTemplate && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-page rounded-xl border border-divider w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-ink-primary mb-4">从模板创建</h2>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-ink-secondary block mb-1">选择模板</label>
                <select
                  value={fromTemplate.template_id}
                  onChange={(e) => setFromTemplate({ ...fromTemplate, template_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                >
                  <option value="">-- 请选择 --</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.is_system ? "[系统] " : ""}
                      {t.name}
                      {t.category ? ` (${t.category})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  项目名称 <span className="text-red-500">*</span>
                </label>
                <input
                  value={fromTemplate.name}
                  onChange={(e) => setFromTemplate({ ...fromTemplate, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                  placeholder="我的项目..."
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <button
                onClick={() => setShowFromTemplate(false)}
                className="px-4 py-2 rounded-lg text-ink-secondary hover:text-ink-primary"
              >
                取消
              </button>
              <button
                onClick={handleCreateFromTemplate}
                disabled={creating || !fromTemplate.template_id || !fromTemplate.name.trim()}
                className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {creating && <Loader2 className="animate-spin" size={14} />}
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
