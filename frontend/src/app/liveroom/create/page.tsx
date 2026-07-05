"use client";

/**
 * LanguageRoom 创建房间页
 * 依据 docs/modules/language-room/overview.md + ADR 0004
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Mic, ArrowLeft, Plus, Loader2, AlertCircle, UserCircle2, Headphones } from "lucide-react";
import { liveroomService, RoomType, ROOM_TYPE_LABELS, LanguageRoom, RoomScenario, AIPersona } from "@/lib/api/liveroom-api";

// STT 语言 — 至少 3 选 1 (ADR 待修复 2: 当前需用户主动配置每房间 STT 语言)
const STT_LANGUAGES = [
  { value: "en", label: "英语" },
  { value: "zh", label: "中文" },
  { value: "es", label: "西班牙语" },
] as const;
type STTLanguage = typeof STT_LANGUAGES[number]["value"];

// 3 档纠错倾向 (ADR 决策 6: 用户主动选择)
const CORRECTION_LEVELS = [
  { value: "none", label: "不纠错" },
  { value: "occasional", label: "偶尔纠错" },
  { value: "proactive", label: "主动纠错" },
] as const;
type CorrectionLevel = typeof CORRECTION_LEVELS[number]["value"];

export default function CreateRoomPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [roomType, setRoomType] = useState<RoomType>("1v1");
  const [maxParticipants, setMaxParticipants] = useState(2);
  const [scenarioId, setScenarioId] = useState("");
  const [isRecordingEnabled, setIsRecordingEnabled] = useState(false);
  const [isTranscriptEnabled, setIsTranscriptEnabled] = useState(true);
  const [aiIntrusionLevel, setAiIntrusionLevel] = useState<"low" | "medium" | "high">("low");
  // 4 新增字段 (Task #65)
  const [aiCompanionPersonaId, setAiCompanionPersonaId] = useState("");
  const [aiAssistantPersonaId, setAiAssistantPersonaId] = useState("");
  const [sttLanguage, setSttLanguage] = useState<STTLanguage>("en");
  const [errorCorrectionLevel, setErrorCorrectionLevel] = useState<CorrectionLevel>("none");
  const [scenarios, setScenarios] = useState<RoomScenario[]>([]);
  const [personas, setPersonas] = useState<AIPersona[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    liveroomService.listScenarios({ limit: 30 }).then(setScenarios).catch(() => []);
    liveroomService.listPersonas({ limit: 50 }).then(setPersonas).catch(() => []);
  }, []);

  // 房间类型变更时调整 maxParticipants
  useEffect(() => {
    const maxMap: Record<RoomType, number> = { "1v1": 2, small: 5, medium: 10, large: 20 };
    setMaxParticipants(maxMap[roomType]);
  }, [roomType]);

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("请输入房间名");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      // 4 新增字段存到 settings dict (后端 schema 已支持 settings: dict)
      const settings: Record<string, unknown> = {
        stt_language: sttLanguage,
        error_correction_level: errorCorrectionLevel,
      };
      if (aiCompanionPersonaId) settings.ai_companion_persona_id = aiCompanionPersonaId;
      if (aiAssistantPersonaId) settings.ai_assistant_persona_id = aiAssistantPersonaId;

      const room: LanguageRoom = await liveroomService.createRoom({
        name,
        room_type: roomType,
        max_participants: maxParticipants,
        scenario_id: scenarioId,
        is_recording_enabled: isRecordingEnabled,
        is_transcript_enabled: isTranscriptEnabled,
        ai_intrusion_level: aiIntrusionLevel,
        settings,
      } as any);
      router.push(`/liveroom/rooms/${room.id}`);
    } catch (e: any) {
      setError(e.message || "创建失败");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* 头部 */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.push("/liveroom")}
            className="p-1.5 hover:bg-[var(--color-card)] rounded"
          >
            <ArrowLeft size={18} />
          </button>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Plus size={20} /> 创建实时语音房间
          </h1>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 border border-red-300 bg-red-50 text-sm text-red-700 rounded flex items-center gap-2">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        <div className="space-y-4 border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-5">
          {/* 房间名 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)]">房间名 *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例: 咖啡馆点餐练习"
              className="w-full mt-1 px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
            />
          </div>

          {/* 房间类型 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)]">房间类型</label>
            <div className="grid grid-cols-4 gap-2 mt-1">
              {(["1v1", "small", "medium", "large"] as RoomType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setRoomType(t)}
                  className={`px-3 py-2 text-xs border rounded ${
                    roomType === t
                      ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                      : "border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                  }`}
                >
                  {ROOM_TYPE_LABELS[t]}
                </button>
              ))}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
              决策 2: 仅邀请制, 不设公开房间
            </div>
          </div>

          {/* 场景 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)]">选择场景 (可选)</label>
            <select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
            >
              <option value="">不选 (自由对话)</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} {s.is_system ? "· 系统" : "· 自定义"}
                </option>
              ))}
            </select>
          </div>

          {/* 录音 */}
          <div className="space-y-1.5">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isRecordingEnabled}
                onChange={(e) => setIsRecordingEnabled(e.target.checked)}
              />
              <span>开启录音 (可选, 决策 10)</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isTranscriptEnabled}
                onChange={(e) => setIsTranscriptEnabled(e.target.checked)}
              />
              <span>开启实时转写</span>
            </label>
          </div>

          {/* AI 侵入度 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)]">AI 辅助者默认侵入度</label>
            <div className="grid grid-cols-3 gap-2 mt-1">
              {(["low", "medium", "high"] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => setAiIntrusionLevel(l)}
                  className={`px-3 py-2 text-xs border rounded ${
                    aiIntrusionLevel === l
                      ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                      : "border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                  }`}
                >
                  {l === "low" ? "低" : l === "medium" ? "中" : "高"}
                </button>
              ))}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
              用户可在房间内单独调整自己的侵入度
            </div>
          </div>

          {/* ── Task #65 新增 4 字段 ── */}

          {/* AI 同伴选择 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
              <UserCircle2 size={12} /> AI 同伴 (可选)
            </label>
            <select
              value={aiCompanionPersonaId}
              onChange={(e) => setAiCompanionPersonaId(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
            >
              <option value="">不选 (无 AI 同伴, 仅真人对话)</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.target_language} · {p.proficiency}
                  {p.is_system ? " (系统)" : ""}
                </option>
              ))}
            </select>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
              AI 同伴将作为 participant 加入房间 (decision 5: ai_companion)
            </div>
          </div>

          {/* AI 辅助者选择 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
              <Headphones size={12} /> AI 辅助者 (可选)
            </label>
            <select
              value={aiAssistantPersonaId}
              onChange={(e) => setAiAssistantPersonaId(e.target.value)}
              className="w-full mt-1 px-3 py-2 text-sm border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
            >
              <option value="">不选 (默认辅助者)</option>
              {personas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.target_language} · {p.proficiency}
                  {p.is_system ? " (系统)" : ""}
                </option>
              ))}
            </select>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
              AI 辅助者仅在用户个人侧边区显示, 不参与对话 (decision 5: ai_assistant)
            </div>
          </div>

          {/* STT 语言 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)]">STT 转写语言 (至少 3 选 1)</label>
            <div className="grid grid-cols-3 gap-2 mt-1">
              {STT_LANGUAGES.map((l) => (
                <button
                  key={l.value}
                  onClick={() => setSttLanguage(l.value)}
                  className={`px-3 py-2 text-xs border rounded ${
                    sttLanguage === l.value
                      ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                      : "border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
              ADR 待修复 2: 当前需用户主动配置每房间 STT 语言, 未做多语种自动切换
            </div>
          </div>

          {/* 3 档纠错倾向 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)]">AI 纠错倾向 (3 档)</label>
            <div className="grid grid-cols-3 gap-2 mt-1">
              {CORRECTION_LEVELS.map((l) => (
                <button
                  key={l.value}
                  onClick={() => setErrorCorrectionLevel(l.value)}
                  className={`px-3 py-2 text-xs border rounded ${
                    errorCorrectionLevel === l.value
                      ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                      : "border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1.5">
              ADR 决策 6: 用户主动选择, AI 默认不评判不纠错
            </div>
          </div>

          {/* 关键说明 */}
          <div className="text-[10px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-3 leading-relaxed">
            <strong>核心原则</strong>: 房间不评判、不主导、不强制流程。<br />
            AI 纠错 = 用户主动选择。转写数据按参与者各自存储 (隐私优先)。
          </div>

          <button
            onClick={handleCreate}
            disabled={creating}
            className="w-full py-2.5 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            {creating ? (
              <><Loader2 size={14} className="inline animate-spin mr-1" /> 创建中...</>
            ) : (
              <><Mic size={14} className="inline mr-1" /> 创建房间</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
