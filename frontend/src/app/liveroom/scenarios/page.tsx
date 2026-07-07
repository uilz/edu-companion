"use client";

/**
 * LanguageRoom 场景管理页
 * 依据 docs/modules/language-room/overview.md + ADR 0004 决策 9
 * 场景与项目平行, 不互相包含
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ScrollText, ArrowLeft, Plus, Loader2, Trash2 } from "lucide-react";
import { liveroomService, RoomScenario, ScenarioCategory } from "@/lib/api/liveroom-api";

export default function ScenariosPage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<RoomScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // 创建表单
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ScenarioCategory>("daily");
  const [promptText, setPromptText] = useState("");
  const [targetGoals, setTargetGoals] = useState("");

  useEffect(() => {
    setLoading(true);
    liveroomService.listScenarios({ limit: 50 })
      .then(setScenarios)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const s = await liveroomService.createScenario({
        name, description, category, prompt_text: promptText,
        target_goals: targetGoals.split("\n").filter((g) => g.trim()),
      });
      setScenarios([s, ...scenarios]);
      setShowCreate(false);
      setName(""); setDescription(""); setPromptText(""); setTargetGoals("");
    } catch (e: any) {
      alert(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/liveroom")}
              className="p-1.5 hover:bg-surface rounded"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <h1 className="text-xl font-semibold flex items-center gap-2">
                <ScrollText size={20} /> 场景库
              </h1>
              <p className="text-xs text-muted mt-0.5">
                决策 9: 场景与项目平行, 不互相包含
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-success text-white rounded-md hover:bg-success"
          >
            <Plus size={14} /> 新建场景
          </button>
        </div>

        {showCreate && (
          <div className="mb-6 border border bg-surface rounded-lg p-4 space-y-3">
            <div className="text-sm font-medium">新建场景</div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="场景名称 (例: 咖啡馆点餐)"
              className="w-full text-sm px-3 py-2 border border rounded bg-page"
            />
            <div className="flex gap-2">
              {(["daily", "academic", "business"] as ScenarioCategory[]).map((c) => (
                <button
                  key={c}
                  onClick={() => setCategory(c)}
                  className={`px-3 py-1.5 text-xs border rounded ${
                    category === c
                      ? "bg-success/10 border-success/30 text-success"
                      : "border"
                  }`}
                >
                  {c === "daily" ? "日常" : c === "academic" ? "学术" : "商务"}
                </button>
              ))}
            </div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="场景描述 (可选)"
              className="w-full text-sm px-3 py-2 border border rounded bg-page h-16 resize-none"
            />
            <textarea
              value={promptText}
              onChange={(e) => setPromptText(e.target.value)}
              placeholder="浮动提示词 (例: 尝试用三个新形容词)"
              className="w-full text-sm px-3 py-2 border border rounded bg-page h-14 resize-none"
            />
            <textarea
              value={targetGoals}
              onChange={(e) => setTargetGoals(e.target.value)}
              placeholder="目标任务 (一行一个)"
              className="w-full text-sm px-3 py-2 border border rounded bg-page h-20 resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={creating}
                className="px-4 py-1.5 text-sm bg-success text-white rounded hover:bg-success"
              >
                {creating ? <Loader2 size={12} className="inline animate-spin" /> : "创建"}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-1.5 text-sm border border rounded"
              >
                取消
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-muted" />
          </div>
        ) : scenarios.length === 0 ? (
          <div className="border border-dashed border rounded-lg p-10 text-center text-sm text-muted">
            暂无场景。点击"新建场景"创建第一个
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {scenarios.map((s) => (
              <div
                key={s.id}
                className="border border bg-surface rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="font-medium text-sm">{s.name}</div>
                  {s.is_system ? (
                    <span className="text-[10px] px-1.5 py-0.5 bg-info/10 text-info border border-info/20 rounded">
                      系统
                    </span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 bg-success/10 text-success border border-success/20 rounded">
                      自定义
                    </span>
                  )}
                </div>
                {s.description && (
                  <p className="text-xs text-muted mb-2 line-clamp-2">
                    {s.description}
                  </p>
                )}
                {s.prompt_text && (
                  <div className="text-[10px] px-2 py-1 bg-success/10 border border-success/20 text-success rounded mb-2">
                    {s.prompt_text}
                  </div>
                )}
                <div className="text-[10px] text-muted flex items-center justify-between">
                  <span>分类: {s.category || "未分类"}</span>
                  {s.target_goals?.length > 0 && (
                    <span>{s.target_goals.length} 个目标</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
