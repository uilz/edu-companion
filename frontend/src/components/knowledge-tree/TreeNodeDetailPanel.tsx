"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  X,
  Brain,
  Trash2,
  BookOpen,
  StickyNote,
  Layers,
  Calendar,
  Link as LinkIcon,
  Plus,
  Loader2,
  AlertCircle,
} from "lucide-react";
import type {
  TreeNode,
  CognitiveNodeView,
  SourceRef,
  NodeMaterialsResponse,
} from "@/lib/api/knowledge-trees-api";
import { flashcardService } from "@/lib/api/flashcard-api";
import { readingService } from "@/lib/api/reading-api";
import { createPracticeSession, listBanks } from "@/lib/api/practice-api";
import { createPlanItem } from "@/hooks/planning/usePlanning";
import type { V7Bank } from "@/lib/api/practice-api";

interface TreeNodeDetailPanelProps {
  node: TreeNode;
  treeId: string;
  materials: NodeMaterialsResponse["materials"] | null;
  materialsLoading: boolean;
  materialsError: string | null;
  onLoadMaterials: () => void;
  onAddSourceRef: (sourceRef: SourceRef) => Promise<boolean>;
  onClose: () => void;
  onDelete: () => void;
  onLinkCognitive: () => void;
}

function formatTime(value?: number | string | null): string {
  if (!value) return "";
  try {
    const d = typeof value === "number" ? new Date(value * 1000) : new Date(value);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function truncate(text: string, max = 80) {
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function CognitiveViewCard({ cv }: { cv: CognitiveNodeView }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-muted text-xs">掌握度</span>
        <span className="text-xs font-medium" style={{ color: cv.display_color }}>
          {Math.round(cv.proficiency * 100)}%
        </span>
      </div>
      <div className="h-1.5 bg-page rounded-full overflow-hidden border border">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${cv.proficiency * 100}%`, background: cv.display_color }}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">紧迫度</div>
          <div className="font-medium">{Math.round(cv.urgency * 100)}%</div>
        </div>
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">不确定性</div>
          <div className="font-medium">{Math.round(cv.uncertainty * 100)}%</div>
        </div>
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">停滞天数</div>
          <div className="font-medium">{cv.stagnation_days} 天</div>
        </div>
        <div className="bg-page p-2 rounded-lg border border">
          <div className="text-muted text-[10px]">下次行动</div>
          <div className="font-medium">{cv.next_action_type}</div>
        </div>
      </div>
      {cv.display_glow && (
        <div className="text-[10px] text-amber-400 bg-amber-400/10 px-2 py-1.5 rounded-lg border border-amber-400/20">
          ⚠️ 不确定性较高，建议复习
        </div>
      )}
    </div>
  );
}

function SourceRefItem({ ref }: { ref: SourceRef }) {
  return (
    <div className="flex items-center gap-2 text-xs px-2 py-1.5 rounded-lg bg-page border border hover:border-accent/30">
      <LinkIcon size={10} className="text-muted" />
      <span className="capitalize text-muted">{ref.module}</span>
      <span className="truncate font-mono">{ref.id.slice(-8)}</span>
    </div>
  );
}

function MaterialSection({
  title,
  icon: Icon,
  count,
  children,
  createLabel,
  onCreate,
  disabled,
}: {
  title: string;
  icon: React.ElementType;
  count: number;
  children: React.ReactNode;
  createLabel: string;
  onCreate: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[10px] font-medium text-muted uppercase tracking-wide">
          <Icon size={12} />
          {title}
          <span className="text-accent">({count})</span>
        </div>
        <button
          onClick={onCreate}
          disabled={disabled}
          className="inline-flex items-center gap-1 px-2 py-1 text-[10px] rounded-md bg-accent/10 text-accent hover:bg-accent/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <Plus size={10} /> {createLabel}
        </button>
      </div>
      {children}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <div className="text-xs text-muted bg-page p-3 rounded-lg border border">{text}</div>;
}

function CardItem({ title, meta, subtitle }: { title: string; meta?: string; subtitle?: string }) {
  return (
    <div className="px-3 py-2 rounded-lg bg-page border border hover:border-accent/30 transition-colors">
      <div className="text-xs text line-clamp-2">{title}</div>
      {subtitle && <div className="text-[10px] text-muted mt-1 line-clamp-1">{subtitle}</div>}
      {meta && <div className="text-[10px] text-muted mt-1">{meta}</div>}
    </div>
  );
}

function Dialog({
  open,
  onClose,
  title,
  children,
  onConfirm,
  confirmDisabled,
  confirmText = "创建",
  loading,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  onConfirm: () => void;
  confirmDisabled?: boolean;
  confirmText?: string;
  loading?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
      <div className="bg-surface border border rounded-xl p-5 w-80 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text">{title}</h3>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-hover">
            <X size={14} className="text-muted" />
          </button>
        </div>
        <div className="space-y-3">{children}</div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-3 py-1.5 text-xs border border rounded-lg text-muted hover:bg-surface-hover disabled:opacity-50"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={confirmDisabled || loading}
            className="px-3 py-1.5 text-xs bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateFlashcardDialog({
  open,
  onClose,
  cognitiveIds,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  cognitiveIds: string[];
  onCreated: (id: string) => Promise<void>;
}) {
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setFront("");
      setBack("");
    }
  }, [open]);

  const handleConfirm = async () => {
    if (!front.trim() || cognitiveIds.length === 0) return;
    setLoading(true);
    try {
      const card = await flashcardService.create({
        type: 1,
        source: "manual",
        front_text: front.trim(),
        back_text: back.trim(),
        linked_node_ids: cognitiveIds,
      });
      await onCreated(card.id);
      onClose();
    } catch (e: any) {
      alert(e.message || "创建闪卡失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="创建闪卡"
      confirmDisabled={!front.trim()}
      loading={loading}
      onConfirm={handleConfirm}
    >
      <textarea
        value={front}
        onChange={(e) => setFront(e.target.value)}
        placeholder="正面（问题/概念）"
        rows={3}
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent resize-none"
      />
      <textarea
        value={back}
        onChange={(e) => setBack(e.target.value)}
        placeholder="背面（答案/解释）"
        rows={3}
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent resize-none"
      />
    </Dialog>
  );
}

function CreateReadingNoteDialog({
  open,
  onClose,
  treeNodeId,
  cognitiveIds,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  treeNodeId: string;
  cognitiveIds: string[];
  onCreated: (id: string) => Promise<void>;
}) {
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setFront("");
      setBack("");
      setContext("");
    }
  }, [open]);

  const handleConfirm = async () => {
    if (!front.trim() || cognitiveIds.length === 0) return;
    setLoading(true);
    try {
      const card = await readingService.createNote({
        material_id: treeNodeId,
        front_text: front.trim(),
        back_text: back.trim(),
        back_context: context.trim(),
        linked_node_ids: cognitiveIds,
        tags: ["reading_note"],
      });
      await onCreated(card.id);
      onClose();
    } catch (e: any) {
      alert(e.message || "创建阅读笔记失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="创建阅读笔记"
      confirmDisabled={!front.trim()}
      loading={loading}
      onConfirm={handleConfirm}
    >
      <textarea
        value={front}
        onChange={(e) => setFront(e.target.value)}
        placeholder="我的问题"
        rows={2}
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent resize-none"
      />
      <textarea
        value={back}
        onChange={(e) => setBack(e.target.value)}
        placeholder="我的回应"
        rows={2}
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent resize-none"
      />
      <textarea
        value={context}
        onChange={(e) => setContext(e.target.value)}
        placeholder="关键论述（可选）"
        rows={2}
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent resize-none"
      />
    </Dialog>
  );
}

function CreatePracticeDialog({
  open,
  onClose,
  cognitiveIds,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  cognitiveIds: string[];
  onCreated: (id: string) => Promise<void>;
}) {
  const [banks, setBanks] = useState<V7Bank[]>([]);
  const [banksLoading, setBanksLoading] = useState(false);
  const [bankId, setBankId] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setBankId("");
    setCount(5);
    setBanksLoading(true);
    listBanks()
      .then((items) => {
        setBanks(items || []);
        if (items?.length) setBankId(items[0].id);
      })
      .catch(() => setBanks([]))
      .finally(() => setBanksLoading(false));
  }, [open]);

  const handleConfirm = async () => {
    if (!bankId || cognitiveIds.length === 0) return;
    setLoading(true);
    try {
      const session = await createPracticeSession(bankId, {
        cognitive_node_ids: cognitiveIds,
        count,
      });
      await onCreated(session.session_id);
      onClose();
    } catch (e: any) {
      alert(e.message || "创建练习会话失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="创建练习会话"
      confirmDisabled={!bankId}
      loading={loading || banksLoading}
      onConfirm={handleConfirm}
    >
      {banks.length === 0 && !banksLoading ? (
        <div className="text-xs text-muted">暂无可用题库，请先在练习模块创建题库。</div>
      ) : (
        <select
          value={bankId}
          onChange={(e) => setBankId(e.target.value)}
          className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
        >
          {banks.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.question_count} 题)
            </option>
          ))}
        </select>
      )}
      <div className="flex items-center gap-3">
        <label className="text-xs text-muted">题目数量</label>
        <input
          type="number"
          min={1}
          max={50}
          value={count}
          onChange={(e) => setCount(Math.max(1, Math.min(50, parseInt(e.target.value || "1", 10))))}
          className="flex-1 px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
        />
      </div>
    </Dialog>
  );
}

function CreatePlanDialog({
  open,
  onClose,
  treeNodeId,
  cognitiveIds,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  treeNodeId: string;
  cognitiveIds: string[];
  onCreated: (id: string) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [minutes, setMinutes] = useState(30);
  const [priority, setPriority] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setMinutes(30);
      setPriority(0);
    }
  }, [open]);

  const handleConfirm = async () => {
    if (!title.trim() || cognitiveIds.length === 0) return;
    setLoading(true);
    try {
      const item = await createPlanItem({
        source_module: "manual",
        target_type: "knowledge_tree_node",
        target_ref_id: treeNodeId,
        title: title.trim(),
        description: description.trim(),
        estimated_minutes: minutes,
        priority,
        linked_node_ids: cognitiveIds,
      });
      await onCreated(item.id);
      onClose();
    } catch (e: any) {
      alert(e.message || "创建计划项失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="创建计划项"
      confirmDisabled={!title.trim()}
      loading={loading}
      onConfirm={handleConfirm}
    >
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="标题"
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="描述（可选）"
        rows={2}
        className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent resize-none"
      />
      <div className="flex items-center gap-3">
        <label className="text-xs text-muted whitespace-nowrap">预估分钟</label>
        <input
          type="number"
          min={0}
          value={minutes}
          onChange={(e) => setMinutes(Math.max(0, parseInt(e.target.value || "0", 10)))}
          className="flex-1 px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
        />
      </div>
      <div className="flex items-center gap-3">
        <label className="text-xs text-muted whitespace-nowrap">优先级 0-5</label>
        <input
          type="number"
          min={0}
          max={5}
          value={priority}
          onChange={(e) => setPriority(Math.max(0, Math.min(5, parseInt(e.target.value || "0", 10))))}
          className="flex-1 px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
        />
      </div>
    </Dialog>
  );
}

export default function TreeNodeDetailPanel({
  node,
  treeId,
  materials,
  materialsLoading,
  materialsError,
  onLoadMaterials,
  onAddSourceRef,
  onClose,
  onDelete,
  onLinkCognitive,
}: TreeNodeDetailPanelProps) {
  const cv = node.cognitive_view;
  const [activeTab, setActiveTab] = useState<"cognitive" | "materials">("cognitive");

  const [flashOpen, setFlashOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [practiceOpen, setPracticeOpen] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);

  const cognitiveIds = useMemo(() => {
    if (node.linked_cognitive_node_ids && node.linked_cognitive_node_ids.length > 0) {
      return node.linked_cognitive_node_ids;
    }
    if (cv?.cognitive_node_id) return [cv.cognitive_node_id];
    return [];
  }, [node, cv]);

  useEffect(() => {
    if (activeTab === "materials" && !materials && !materialsLoading && !materialsError) {
      onLoadMaterials();
    }
  }, [activeTab, materials, materialsLoading, materialsError, onLoadMaterials]);

  const handleCreated = async (sourceRef: SourceRef) => {
    await onAddSourceRef(sourceRef);
    onLoadMaterials();
  };

  const flashcards = materials?.flashcards || [];
  const annotations = materials?.reading?.annotations || [];
  const notes = materials?.reading?.notes || [];
  const sessions = materials?.practice?.sessions || [];
  const errors = materials?.practice?.errors || [];
  const planItems = materials?.planning || [];

  const noCognitive = cognitiveIds.length === 0;

  return (
    <div className="h-full flex flex-col bg-surface border-l border">
      <div className="flex items-center justify-between px-4 py-3 border-b border">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg">{node.emoji || "📄"}</span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text truncate">{node.label}</div>
            <div className="text-[10px] text-muted uppercase tracking-wide">{node.node_type}</div>
          </div>
        </div>
        <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-hover">
          <X size={14} className="text-muted" />
        </button>
      </div>

      <div className="flex border-b border">
        {[
          { id: "cognitive" as const, label: "认知视图", icon: Brain },
          { id: "materials" as const, label: "材料聚合", icon: Layers },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium transition-colors ${
              activeTab === tab.id ? "text-accent bg-accent/5 border-b-2 border-accent" : "text-muted hover:text"
            }`}
          >
            <tab.icon size={12} /> {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {node.brief && (
          <div className="text-xs text-muted leading-relaxed bg-page p-3 rounded-lg border border">
            {node.brief}
          </div>
        )}

        {activeTab === "cognitive" && (
          <div className="space-y-3">
            <div className="text-[10px] font-medium text-muted uppercase tracking-wide">关联认知节点</div>
            {cv ? (
              <CognitiveViewCard cv={cv} />
            ) : (
              <div className="text-xs text-muted bg-page p-4 rounded-lg border border text-center">
                未关联认知节点
              </div>
            )}
            <button
              onClick={onLinkCognitive}
              className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs bg-accent text-white rounded-lg hover:opacity-90"
            >
              <Brain size={12} /> {cv ? "切换认知节点" : "关联认知节点"}
            </button>
          </div>
        )}

        {activeTab === "materials" && (
          <div className="space-y-5">
            {noCognitive && (
              <div className="flex items-start gap-2 text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 p-3 rounded-lg">
                <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />
                <span>当前节点未关联认知节点，材料创建功能已禁用。请先关联认知节点。</span>
              </div>
            )}

            <div className="space-y-2">
              <div className="text-[10px] font-medium text-muted uppercase tracking-wide">来源引用</div>
              {node.source_refs && node.source_refs.length > 0 ? (
                <div className="space-y-1.5">
                  {node.source_refs.map((ref, idx) => (
                    <SourceRefItem key={`${ref.module}-${ref.id}-${idx}`} ref={ref} />
                  ))}
                </div>
              ) : (
                <EmptyHint text="暂无来源引用" />
              )}
            </div>

            {materialsLoading && (
              <div className="flex items-center justify-center py-6 gap-2 text-xs text-muted">
                <Loader2 size={14} className="animate-spin" /> 加载材料中…
              </div>
            )}

            {materialsError && (
              <div className="text-xs text-danger bg-danger/10 border border-danger/20 p-3 rounded-lg">
                {materialsError}
              </div>
            )}

            {!materialsLoading && materials && (
              <>
                <MaterialSection
                  title="闪卡"
                  icon={BookOpen}
                  count={flashcards.length}
                  createLabel="创建闪卡"
                  onCreate={() => setFlashOpen(true)}
                  disabled={noCognitive}
                >
                  {flashcards.length === 0 ? (
                    <EmptyHint text="暂无闪卡" />
                  ) : (
                    <div className="space-y-1.5">
                      {flashcards.slice(0, 5).map((card) => (
                        <CardItem
                          key={card.id}
                          title={truncate(card.front_text)}
                          meta={`${card.status || "pending"} · ${formatTime(card.created_at)}`}
                        />
                      ))}
                    </div>
                  )}
                </MaterialSection>

                <MaterialSection
                  title="阅读标注"
                  icon={StickyNote}
                  count={annotations.length}
                  createLabel="创建标注"
                  onCreate={() => alert("阅读标注需在阅读材料内创建")}
                  disabled
                >
                  {annotations.length === 0 ? (
                    <EmptyHint text="暂无阅读标注" />
                  ) : (
                    <div className="space-y-1.5">
                      {annotations.slice(0, 5).map((a) => (
                        <CardItem
                          key={a.id}
                          title={truncate(a.text || a.note || "标注")}
                          meta={`${a.intent} · ${formatTime(a.created_at)}`}
                          subtitle={a.material_id}
                        />
                      ))}
                    </div>
                  )}
                </MaterialSection>

                <MaterialSection
                  title="阅读笔记"
                  icon={StickyNote}
                  count={notes.length}
                  createLabel="创建笔记"
                  onCreate={() => setNoteOpen(true)}
                  disabled={noCognitive}
                >
                  {notes.length === 0 ? (
                    <EmptyHint text="暂无阅读笔记" />
                  ) : (
                    <div className="space-y-1.5">
                      {notes.slice(0, 5).map((note) => (
                        <CardItem
                          key={note.id}
                          title={truncate(note.front_text)}
                          meta={formatTime(note.created_at)}
                        />
                      ))}
                    </div>
                  )}
                </MaterialSection>

                <MaterialSection
                  title="练习"
                  icon={Brain}
                  count={sessions.length + errors.length}
                  createLabel="创建练习"
                  onCreate={() => setPracticeOpen(true)}
                  disabled={noCognitive}
                >
                  {sessions.length === 0 && errors.length === 0 ? (
                    <EmptyHint text="暂无练习会话与错题" />
                  ) : (
                    <div className="space-y-1.5">
                      {sessions.slice(0, 3).map((s) => (
                        <CardItem
                          key={s.session_id}
                          title={`${s.bank_name || s.bank_id} · ${s.session_type}`}
                          meta={`${s.status} · ${s.question_count} 题 · ${formatTime(s.created_at)}`}
                        />
                      ))}
                      {errors.slice(0, 3).map((err) => (
                        <CardItem
                          key={err.question_id}
                          title={truncate(err.stem)}
                          meta={`错 ${err.wrong_count} 次 · 掌握 ${err.mastered ? "是" : "否"}`}
                        />
                      ))}
                    </div>
                  )}
                </MaterialSection>

                <MaterialSection
                  title="计划"
                  icon={Calendar}
                  count={planItems.length}
                  createLabel="创建计划"
                  onCreate={() => setPlanOpen(true)}
                  disabled={noCognitive}
                >
                  {planItems.length === 0 ? (
                    <EmptyHint text="暂无计划项" />
                  ) : (
                    <div className="space-y-1.5">
                      {planItems.slice(0, 5).map((item) => (
                        <CardItem
                          key={item.id}
                          title={item.title}
                          meta={`${item.status} · ${item.estimated_minutes} 分钟 · ${formatTime(item.scheduled_for)}`}
                        />
                      ))}
                    </div>
                  )}
                </MaterialSection>
              </>
            )}
          </div>
        )}
      </div>

      <div className="p-3 border-t border">
        <button
          onClick={onDelete}
          className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs border border-danger text-danger rounded-lg hover:bg-danger/10"
        >
          <Trash2 size={12} /> 删除节点
        </button>
      </div>

      <CreateFlashcardDialog
        open={flashOpen}
        onClose={() => setFlashOpen(false)}
        cognitiveIds={cognitiveIds}
        onCreated={(id) => handleCreated({ module: "flashcard", id })}
      />
      <CreateReadingNoteDialog
        open={noteOpen}
        onClose={() => setNoteOpen(false)}
        treeNodeId={node.id}
        cognitiveIds={cognitiveIds}
        onCreated={(id) => handleCreated({ module: "reading", id })}
      />
      <CreatePracticeDialog
        open={practiceOpen}
        onClose={() => setPracticeOpen(false)}
        cognitiveIds={cognitiveIds}
        onCreated={(id) => handleCreated({ module: "practice", id })}
      />
      <CreatePlanDialog
        open={planOpen}
        onClose={() => setPlanOpen(false)}
        treeNodeId={node.id}
        cognitiveIds={cognitiveIds}
        onCreated={(id) => handleCreated({ module: "planning", id })}
      />
    </div>
  );
}
