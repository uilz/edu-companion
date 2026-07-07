"use client";

/**
 * Reading 详情页 — 阅读会话（精读/略读/回顾三种模式）
 * 依据 docs/modules/reading/overview.md + ADR 0003
 */
import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import {
  BookOpen, Highlighter, MessageSquare, Save, Trash2, AlertCircle,
  ChevronLeft, Eye, EyeOff, Bell, Clock, CheckCircle2, X, Plus
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";
import {
  readingService,
  ReadingAnnotation, AnnotationColor, ReadingMode, MODE_LABELS,
  COLOR_LABELS, COLOR_HEX,
} from "@/lib/api/reading-api";

export default function ReadingMaterialPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const materialId = params?.id || "";
  const initialSessionId = search?.get("session") || "";

  const [session, setSession] = useState<any | null>(null);
  const [annotations, setAnnotations] = useState<ReadingAnnotation[]>([]);
  const [colorMeta, setColorMeta] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 标注创建
  const [showCreateAnn, setShowCreateAnn] = useState(false);
  const [newAnn, setNewAnn] = useState<{
    color: AnnotationColor;
    text: string;
    note: string;
    linked_node_id: string;
  }>({ color: "yellow", text: "", note: "", linked_node_id: "" });

  // 笔记创建
  const [showCreateNote, setShowCreateNote] = useState(false);
  const [newNote, setNewNote] = useState({
    front_text: "",
    back_text: "",
    back_context: "",
    linked_node_ids: "",
    tags: "",
  });

  // 回顾提醒
  const [reminderDays, setReminderDays] = useState<number | null>(null);
  const [showReminderConfirm, setShowReminderConfirm] = useState(false);

  const loadAll = useCallback(async () => {
    if (!materialId) return;
    setLoading(true);
    setError(null);
    try {
      // 启动或恢复会话
      let sess: any | null = null;
      if (initialSessionId) {
        try {
          sess = await readingService.getSession(initialSessionId);
        } catch {
          sess = null;
        }
      }
      if (!sess) {
        try {
          sess = await readingService.getActiveSession(materialId);
        } catch {
          sess = null;
        }
      }
      if (!sess) {
        sess = await readingService.startSession({ material_id: materialId, mode: "intensive" });
      }
      setSession(sess);
      const [annRes, meta] = await Promise.all([
        readingService.listAnnotations({ material_id: materialId, limit: 200 }),
        readingService.getColorFollowup().catch(() => null),
      ]);
      setAnnotations((annRes as any).items || []);
      setColorMeta(meta);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, [materialId, initialSessionId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // 切换模式
  const handleChangeMode = async (mode: ReadingMode) => {
    if (!session || session.mode === mode) return;
    try {
      const updated = await readingService.changeMode(session.id, mode);
      setSession(updated);
    } catch (e: any) {
      alert("切换模式失败: " + e.message);
    }
  };

  // 结束会话
  const handleEndSession = async () => {
    if (!session) return;
    if (!confirm("确定结束当前阅读会话？")) return;
    try {
      const ended = await readingService.endSession(session.id);
      setSession(ended);
      await loadAll();
    } catch (e: any) {
      alert("结束会话失败: " + e.message);
    }
  };

  // 创建标注
  const handleCreateAnnotation = async () => {
    if (!materialId) return;
    try {
      await readingService.createAnnotation({
        material_id: materialId,
        color: newAnn.color,
        text: newAnn.text,
        note: newAnn.note,
        linked_node_id: newAnn.linked_node_id || undefined,
        chunk_id: session?.id?.slice(0, 12) || "",
      });
      setShowCreateAnn(false);
      setNewAnn({ color: "yellow", text: "", note: "", linked_node_id: "" });
      const annRes = await readingService.listAnnotations({ material_id: materialId, limit: 200 });
      setAnnotations((annRes as any).items || []);
    } catch (e: any) {
      alert("创建标注失败: " + e.message);
    }
  };

  // 删除标注
  const handleDeleteAnnotation = async (id: string) => {
    if (!confirm("删除该标注？")) return;
    try {
      await readingService.deleteAnnotation(id);
      setAnnotations((prev) => prev.filter((a) => a.id !== id));
    } catch (e: any) {
      alert("删除失败: " + e.message);
    }
  };

  // 提取为 FlashCard
  const handleExtractToCard = async (id: string) => {
    try {
      await readingService.processAnnotation(id, "flashcard", `card_from_ann_${id}`);
      setAnnotations((prev) => prev.map((a) => (a.id === id ? { ...a, is_processed: true } : a)));
      alert("已标记为待处理 (实际卡片由用户从笔记功能创建)");
    } catch (e: any) {
      alert("操作失败: " + e.message);
    }
  };

  // 创建笔记 (FlashCard 反思型)
  const handleCreateNote = async () => {
    if (!materialId) return;
    const nodeIds = newNote.linked_node_ids
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (nodeIds.length === 0) {
      alert("请输入至少一个关联知识点 ID");
      return;
    }
    try {
      const card = await readingService.createNote({
        material_id: materialId,
        front_text: newNote.front_text,
        back_text: newNote.back_text,
        back_context: newNote.back_context,
        linked_node_ids: nodeIds,
        tags: newNote.tags.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean),
        session_id: session?.id || "",
      });
      setShowCreateNote(false);
      setNewNote({ front_text: "", back_text: "", back_context: "", linked_node_ids: "", tags: "" });
      alert(`笔记已创建 (FlashCard id: ${card.id})，将进入 FSRS 调度`);
      // 刷新会话
      if (session) {
        const sess = await readingService.getSession(session.id);
        setSession(sess);
      }
    } catch (e: any) {
      alert("创建笔记失败: " + e.message);
    }
  };

  // 设置回顾提醒
  const handleSetReminder = async (days: number) => {
    try {
      const res = await readingService.createReviewReminder({
        material_id: materialId,
        review_after_days: days,
      });
      setShowReminderConfirm(false);
      setReminderDays(days);
      alert(`已设置 ${days} 天后回顾 (PlanItem id: ${res.plan_item_id})`);
    } catch (e: any) {
      alert("设置提醒失败: " + e.message);
    }
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* 顶部 */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push("/reading")}
            className="text-muted hover:text"
          >
            <ChevronLeft size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold truncate">材料 {materialId.slice(0, 16)}</h1>
            <p className="text-xs text-muted">
              会话 {session?.id?.slice(0, 12) || "—"} ·{" "}
              {session?.ended_at ? "已结束" : "进行中"} · 标注 {annotations.length} ·{" "}
              笔记 {session?.notes_created || 0}
            </p>
          </div>

          {/* 模式切换 */}
          <div className="flex items-center border border rounded-md overflow-hidden">
            {(["intensive", "skim", "review"] as ReadingMode[]).map((m) => (
              <button
                key={m}
                onClick={() => handleChangeMode(m)}
                disabled={!session || session.ended_at}
                className={`px-3 py-1.5 text-xs ${
                  session?.mode === m
                    ? "bg-accent text-white"
                    : "hover:bg-surface-hover"
                }`}
              >
                {MODE_LABELS[m]}
              </button>
            ))}
          </div>

          {!session?.ended_at && (
            <button
              onClick={handleEndSession}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border rounded-md hover:bg-surface"
            >
              <CheckCircle2 size={14} /> 结束
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 border border-danger/30 bg-danger/10 text-sm text-danger rounded">
            <AlertCircle size={14} className="inline mr-1" /> {error}
          </div>
        )}

        {/* 主体两栏 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左：阅读区 */}
          <div className="lg:col-span-2 space-y-4">
            <div className="border border bg-surface rounded-lg p-5 min-h-[400px]">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-muted flex items-center gap-2">
                  <BookOpen size={14} /> 阅读区
                  <span className="text-xs font-normal text-muted">
                    ({MODE_LABELS[session?.mode as ReadingMode] || "—"})
                  </span>
                </h2>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowCreateAnn(true)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs border border rounded hover:bg-surface-hover"
                  >
                    <Highlighter size={12} /> 标注
                  </button>
                  <button
                    onClick={() => setShowCreateNote(true)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs border border rounded hover:bg-surface-hover"
                  >
                    <MessageSquare size={12} /> 写笔记
                  </button>
                </div>
              </div>
              <div className="text-sm text-muted leading-relaxed">
                <p className="mb-2">
                  这里是占位文本。实际生产中，file-management 提供的
                  <code className="px-1 mx-1 bg-surface-hover rounded">MaterialChunk</code>
                  内容会通过 RAG 检索或全量加载展示。
                </p>
                <p>
                  段落锚点用 <code className="px-1 bg-surface-hover rounded">chunk_id</code>，
                  不重建独立 ID。已掌握 / 薄弱知识点高亮由 <code className="px-1 bg-surface-hover rounded">reading_prefs</code> 控制。
                </p>
              </div>
            </div>

            {/* 元数据：模式偏好提示 */}
            <div className="border border bg-surface rounded-lg p-4 text-sm">
              <h3 className="text-sm font-semibold text-muted mb-2">会话统计</h3>
              <div className="grid grid-cols-3 gap-3">
                <MiniStat label="访问章节" value={String(session?.chapters_visited?.length || 0)} />
                <MiniStat label="关联节点" value={String(session?.linked_node_ids?.length || 0)} />
                <MiniStat label="持续时间" value={session?.duration_seconds ? `${Math.round(session.duration_seconds / 60)} 分钟` : "—"} />
              </div>
            </div>
          </div>

          {/* 右：标注侧栏 + 回顾 */}
          <div className="space-y-4">
            <div className="border border bg-surface rounded-lg p-4">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Highlighter size={14} /> 标注列表
                <span className="text-xs font-normal text-muted">
                  ({annotations.length})
                </span>
              </h3>
              {annotations.length === 0 ? (
                <p className="text-xs text-muted">还没有标注。点击 "标注" 创建第一条。</p>
              ) : (
                <div className="space-y-2 max-h-[400px] overflow-y-auto">
                  {annotations.map((a) => (
                    <div
                      key={a.id}
                      className="border border rounded p-2"
                      style={{ borderLeftWidth: 3, borderLeftColor: COLOR_HEX[a.color] }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{ backgroundColor: COLOR_HEX[a.color] + "22", color: COLOR_HEX[a.color] }}
                        >
                          {COLOR_LABELS[a.color]}
                        </span>
                        <div className="flex items-center gap-1">
                          {!a.is_processed && (
                            <button
                              onClick={() => handleExtractToCard(a.id)}
                              className="text-xs text-accent hover:underline"
                            >
                              提取
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteAnnotation(a.id)}
                            className="text-muted hover:text-danger"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </div>
                      {a.text && <p className="text-xs text line-clamp-2">{a.text}</p>}
                      {a.note && <p className="text-[10px] text-muted mt-1">{a.note}</p>}
                      {a.followup?.suggestion && (
                        <p className="text-[10px] text-muted mt-1 italic">
                          💡 {a.followup.suggestion}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 回顾提醒 */}
            <div className="border border bg-surface rounded-lg p-4">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Bell size={14} /> 回顾提醒
              </h3>
              {reminderDays ? (
                <div className="flex items-center gap-2 text-xs">
                  <Clock size={12} />
                  <span>{reminderDays} 天后回顾（由 PlanItem 调度）</span>
                </div>
              ) : (
                <>
                  <p className="text-xs text-muted mb-2">
                    设置后将通过 Planning 调度到日程
                  </p>
                  <div className="flex gap-1.5">
                    {[7, 30, 90].map((d) => (
                      <button
                        key={d}
                        onClick={() => handleSetReminder(d)}
                        className="px-2.5 py-1 text-xs border border rounded hover:bg-surface-hover"
                      >
                        {d} 天
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* 5 色映射元数据 */}
            {colorMeta?.color_followup && (
              <details className="border border bg-surface rounded-lg p-3 text-xs">
                <summary className="cursor-pointer font-medium">5 色 → 后续动作</summary>
                <div className="mt-2 space-y-1.5">
                  {Object.entries(colorMeta.color_followup).map(([k, v]: [string, any]) => (
                    <div key={k} className="flex items-start gap-1.5">
                      <div
                        className="w-3 h-3 rounded-sm mt-0.5 flex-shrink-0"
                        style={{ backgroundColor: COLOR_HEX[k as AnnotationColor] }}
                      />
                      <div>
                        <div className="font-medium">{v.label}</div>
                        <div className="text-muted">{v.suggestion}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        </div>
      </div>

      {/* 标注创建对话框 */}
      {showCreateAnn && (
        <Modal title="新建标注" onClose={() => setShowCreateAnn(false)}>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1">颜色（决定后续动作）</label>
              <div className="flex gap-2">
                {(Object.keys(COLOR_HEX) as AnnotationColor[]).map((c) => (
                  <button
                    key={c}
                    onClick={() => setNewAnn((p) => ({ ...p, color: c }))}
                    className={`w-8 h-8 rounded ${
                      newAnn.color === c ? "ring-2 ring-offset-1 ring-accent" : ""
                    }`}
                    style={{ backgroundColor: COLOR_HEX[c] }}
                    title={COLOR_LABELS[c]}
                  />
                ))}
              </div>
              {colorMeta?.color_followup?.[newAnn.color] && (
                <p className="text-xs text-muted mt-1">
                  💡 {colorMeta.color_followup[newAnn.color].suggestion}
                </p>
              )}
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">标注原文</label>
              <textarea
                value={newAnn.text}
                onChange={(e) => setNewAnn((p) => ({ ...p, text: e.target.value }))}
                rows={3}
                className="w-full px-3 py-2 text-sm border border rounded bg-surface"
                placeholder="选中的文字..."
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">批注</label>
              <textarea
                value={newAnn.note}
                onChange={(e) => setNewAnn((p) => ({ ...p, note: e.target.value }))}
                rows={2}
                className="w-full px-3 py-2 text-sm border border rounded bg-surface"
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">关联知识点 ID (可选)</label>
              <input
                value={newAnn.linked_node_id}
                onChange={(e) => setNewAnn((p) => ({ ...p, linked_node_id: e.target.value }))}
                className="w-full px-3 py-1.5 text-sm border border rounded bg-surface"
                placeholder="knowledge_node.id"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreateAnn(false)}
                className="px-3 py-1.5 text-sm border border rounded"
              >
                取消
              </button>
              <button
                onClick={handleCreateAnnotation}
                className="px-3 py-1.5 text-sm bg-accent text-white rounded"
              >
                创建
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* 笔记创建对话框 */}
      {showCreateNote && (
        <Modal title="写笔记 (FlashCard 反思型)" onClose={() => setShowCreateNote(false)}>
          <div className="space-y-3">
            <p className="text-xs text-muted">
              笔记三段式 → FlashCard 反思型 (card_type=7, source=reading_note)，自动进入 FSRS 调度。
            </p>
            <div>
              <label className="text-sm font-medium block mb-1">我的问题 (front_text)</label>
              <textarea
                value={newNote.front_text}
                onChange={(e) => setNewNote((p) => ({ ...p, front_text: e.target.value }))}
                rows={2}
                className="w-full px-3 py-2 text-sm border border rounded bg-surface"
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">关键论述 (back_context)</label>
              <textarea
                value={newNote.back_context}
                onChange={(e) => setNewNote((p) => ({ ...p, back_context: e.target.value }))}
                rows={3}
                className="w-full px-3 py-2 text-sm border border rounded bg-surface"
                placeholder="作者的核心观点/论据..."
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">我的回应 (back_text)</label>
              <textarea
                value={newNote.back_text}
                onChange={(e) => setNewNote((p) => ({ ...p, back_text: e.target.value }))}
                rows={3}
                className="w-full px-3 py-2 text-sm border border rounded bg-surface"
                placeholder="同意/反对/补充/关联自己的经验..."
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">关联知识点 (必填, 逗号分隔)</label>
              <input
                value={newNote.linked_node_ids}
                onChange={(e) => setNewNote((p) => ({ ...p, linked_node_ids: e.target.value }))}
                className="w-full px-3 py-1.5 text-sm border border rounded bg-surface"
                placeholder="node_abc, node_def"
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">标签 (可选, 逗号分隔)</label>
              <input
                value={newNote.tags}
                onChange={(e) => setNewNote((p) => ({ ...p, tags: e.target.value }))}
                className="w-full px-3 py-1.5 text-sm border border rounded bg-surface"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowCreateNote(false)}
                className="px-3 py-1.5 text-sm border border rounded"
              >
                取消
              </button>
              <button
                onClick={handleCreateNote}
                className="px-3 py-1.5 text-sm bg-accent text-white rounded inline-flex items-center gap-1"
              >
                <Save size={12} /> 保存
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center p-2 border border rounded">
      <div className="text-[10px] text-muted">{label}</div>
      <div className="text-sm font-semibold mt-0.5">{value}</div>
    </div>
  );
}

function Modal({ title, children, onClose }: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[90vh] overflow-auto bg-surface border border rounded-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="text-muted hover:text">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
