"use client";

import { useState } from "react";
import { Target, Plus, Loader2, Trash2, Edit3, CheckCircle2 } from "lucide-react";
import { useGoals, PlanGoal } from "@/hooks/planning/usePlanning";
import { api } from "@/lib/api/api";
import Card from "@/components/ui/Card";

const MODULE_LABELS: Record<string, string> = {
  project: "项目",
  flashcard: "卡片",
  practice: "练习",
  reading: "阅读",
  language_room: "语言房",
};

const METRIC_LABELS: Record<string, string> = {
  node_count: "节点数",
  card_count: "卡片数",
  practice_count: "练习数",
  duration_minutes: "时长(分钟)",
};

const STATUS_LABELS: Record<string, string> = {
  active: "进行中",
  completed: "已完成",
  abandoned: "已放弃",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-info/20 text-info",
  completed: "bg-success/20 text-success",
  abandoned: "bg-surface text-muted",
};

interface CreateForm {
  title: string;
  description: string;
  target_module: "project" | "flashcard" | "practice" | "reading" | "language_room";
  target_metric: "node_count" | "card_count" | "practice_count" | "duration_minutes";
  target_value: number;
  deadline: string;
}

const EMPTY_FORM: CreateForm = {
  title: "",
  description: "",
  target_module: "flashcard",
  target_metric: "card_count",
  target_value: 100,
  deadline: "",
};

export default function GoalsPage() {
  const { goals, loading, reload, create, update } = useGoals();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingStatus, setEditingStatus] = useState<"active" | "completed" | "abandoned">("active");
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!form.title.trim()) return;
    try {
      await create({
        title: form.title,
        description: form.description,
        target_module: form.target_module,
        target_metric: form.target_metric,
        target_value: form.target_value,
        deadline: form.deadline || undefined,
      });
      setForm(EMPTY_FORM);
      setShowCreate(false);
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : "创建目标失败");
    }
  };

  const handleStatusUpdate = async (id: string) => {
    try {
      await update(id, { status: editingStatus });
      setEditingId(null);
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : "更新目标状态失败");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-page">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10 text-center">
          <div className="p-4 border border-danger/20 bg-danger/10 rounded-lg text-danger mb-4">
            {error}
          </div>
          <button
            onClick={() => { setError(null); reload(); }}
            className="px-4 py-2 rounded-lg bg-accent text-white hover:opacity-90 text-sm"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text tracking-tight flex items-center gap-2">
              <Target size={20} /> 目标管理
            </h1>
            <p className="text-sm text-muted mt-1">
              手动设定长期目标，进度由对应模块实际数据自动更新
            </p>
          </div>
          <button
            onClick={() => setShowCreate((s) => !s)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-accent text-white hover:opacity-90"
          >
            <Plus size={14} /> 新建目标
          </button>
        </div>

        {showCreate && (
          <Card title="新建目标" className="mb-6">
            <div className="space-y-3">
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="目标标题…"
                className="w-full px-3 py-2 text-sm border border bg-page"
              />
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="说明（可选）"
                rows={2}
                className="w-full px-3 py-2 text-sm border border bg-page"
              />
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <select
                  value={form.target_module}
                  onChange={(e) => setForm({ ...form, target_module: e.target.value as CreateForm["target_module"] })}
                  className="px-3 py-2 text-sm border border bg-page"
                >
                  {Object.entries(MODULE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <select
                  value={form.target_metric}
                  onChange={(e) => setForm({ ...form, target_metric: e.target.value as CreateForm["target_metric"] })}
                  className="px-3 py-2 text-sm border border bg-page"
                >
                  {Object.entries(METRIC_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min={1}
                  value={form.target_value}
                  onChange={(e) => setForm({ ...form, target_value: Number(e.target.value) })}
                  placeholder="目标值"
                  className="px-3 py-2 text-sm border border bg-page"
                />
                <input
                  type="date"
                  value={form.deadline}
                  onChange={(e) => setForm({ ...form, deadline: e.target.value })}
                  className="px-3 py-2 text-sm border border bg-page"
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCreate}
                  disabled={!form.title.trim()}
                  className="px-4 py-2 text-sm bg-accent text-white hover:opacity-90 disabled:opacity-50"
                >
                  创建
                </button>
                <button
                  onClick={() => {
                    setShowCreate(false);
                    setForm(EMPTY_FORM);
                  }}
                  className="px-4 py-2 text-sm border border"
                >
                  取消
                </button>
              </div>
            </div>
          </Card>
        )}

        {goals.length === 0 ? (
          <Card>
            <div className="text-center py-12">
              <Target size={40} className="mx-auto mb-3 text-muted" />
              <div className="text-sm text-muted">还没有目标</div>
              <div className="text-xs text-muted mt-1">
                点击右上角"新建目标"开始
              </div>
            </div>
          </Card>
        ) : (
          <div className="space-y-3">
            {goals.map((g) => (
              <GoalRow
                key={g.id}
                goal={g}
                editing={editingId === g.id}
                editingStatus={editingStatus}
                setEditingStatus={setEditingStatus}
                onEdit={() => {
                  setEditingId(g.id);
                  setEditingStatus(g.status as "active" | "completed" | "abandoned");
                }}
                onSaveStatus={() => handleStatusUpdate(g.id)}
                onCancelEdit={() => setEditingId(null)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface GoalRowProps {
  goal: PlanGoal;
  editing: boolean;
  editingStatus: "active" | "completed" | "abandoned";
  setEditingStatus: (s: "active" | "completed" | "abandoned") => void;
  onEdit: () => void;
  onSaveStatus: () => void;
  onCancelEdit: () => void;
}

function GoalRow({ goal, editing, editingStatus, setEditingStatus, onEdit, onSaveStatus, onCancelEdit }: GoalRowProps) {
  const pct = Math.round((goal.progress_pct || 0) * 100);
  return (
    <Card>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="text-base font-semibold text">{goal.title}</h3>
            <span className={`text-xs px-1.5 py-0.5 ${STATUS_COLORS[goal.status] || "bg-surface"}`}>
              {STATUS_LABELS[goal.status] || goal.status}
            </span>
          </div>
          {goal.description && (
            <div className="text-sm text-muted mb-2">{goal.description}</div>
          )}
          <div className="text-xs text-muted flex items-center gap-3 flex-wrap">
            <span>模块: {MODULE_LABELS[goal.target_module] || goal.target_module}</span>
            <span>指标: {METRIC_LABELS[goal.target_metric] || goal.target_metric}</span>
            <span>目标: {goal.target_value}</span>
            {goal.deadline && <span>截止: {goal.deadline}</span>}
          </div>
          <div className="mt-3 w-full bg-surface border border h-2">
            <div
              className="h-full bg-accent"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="text-xs text-muted mt-1">
            进度: {goal.current_value || 0} / {goal.target_value} ({pct}%)
          </div>
        </div>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <select
                value={editingStatus}
                onChange={(e) => setEditingStatus(e.target.value as "active" | "completed" | "abandoned")}
                className="px-2 py-1 text-sm border border bg-page"
              >
                <option value="active">进行中</option>
                <option value="completed">已完成</option>
                <option value="abandoned">已放弃</option>
              </select>
              <button
                onClick={onSaveStatus}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs bg-accent text-white"
              >
                <CheckCircle2 size={12} /> 保存
              </button>
              <button
                onClick={onCancelEdit}
                className="px-3 py-1.5 text-xs border border"
              >
                取消
              </button>
            </>
          ) : (
            <button
              onClick={onEdit}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs border border hover:bg-surface"
            >
              <Edit3 size={12} /> 状态
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}
