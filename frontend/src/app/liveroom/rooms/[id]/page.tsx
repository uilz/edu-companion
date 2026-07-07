"use client";

/**
 * LanguageRoom 房间详情页 — 实时语音房间主界面
 * 依据 docs/modules/language-room/overview.md + ADR 0004
 *
 * 布局：
 *  - 顶部: 房间标题 + 状态 + 控制
 *  - 左侧: 实时转写区
 *  - 中部: 语音通话占位（LiveKit）+ 场景提示
 *  - 右侧: 参与者 + 词汇便签 + AI 角色 + 文字辅助
 *  - 底部: 错误标记 / 录音控制
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  Mic, MicOff, Users, MessageSquare, Plus, Sparkles, StickyNote,
  AlertCircle, Loader2, Settings, X, BookOpen, Volume2, History,
  ScrollText, Send, Edit3, Trash2,
} from "lucide-react";
import {
  liveroomService,
  LanguageRoom, RoomParticipant, RoomTranscript, RoomScenario,
  AIPersona, InvasivenessConfig, RoomMessage, HelperType, MessageType,
  InvasivenessLevel, CorrectionTendency,
  HELPER_TYPE_LABELS, INVASIVENESS_LABELS, CORRECTION_TENDENCY_LABELS,
} from "@/lib/api/liveroom-api";

export default function RoomDetailPage() {
  const router = useRouter();
  const params = useParams();
  const roomId = params.id as string;

  const [room, setRoom] = useState<LanguageRoom | null>(null);
  const [participants, setParticipants] = useState<RoomParticipant[]>([]);
  const [transcripts, setTranscripts] = useState<RoomTranscript[]>([]);
  const [messages, setMessages] = useState<RoomMessage[]>([]);
  const [scenarios, setScenarios] = useState<RoomScenario[]>([]);
  const [personas, setPersonas] = useState<AIPersona[]>([]);
  const [helperConfig, setHelperConfig] = useState<InvasivenessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showVocabPanel, setShowVocabPanel] = useState(false);
  const [showHelperPanel, setShowHelperPanel] = useState(false);
  const [showMessagePanel, setShowMessagePanel] = useState(false);
  const [showParticipantPanel, setShowParticipantPanel] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingId, setRecordingId] = useState<string | null>(null);

  const transcriptRef = useRef<HTMLDivElement>(null);

  // 加载房间
  const loadRoom = useCallback(async () => {
    try {
      const r = await liveroomService.getRoom(roomId);
      setRoom(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }, [roomId]);

  // 加载参与者
  const loadParticipants = useCallback(async () => {
    try {
      const ps = await liveroomService.listParticipants(roomId);
      setParticipants(ps);
    } catch (e) { /* silent */ }
  }, [roomId]);

  // 加载转写
  const loadTranscripts = useCallback(async () => {
    try {
      const ts = await liveroomService.listTranscripts(roomId, { only_user: true, limit: 100 });
      setTranscripts(ts.reverse()); // 时间正序
    } catch (e) { /* silent */ }
  }, [roomId]);

  // 加载消息
  const loadMessages = useCallback(async () => {
    try {
      const ms = await liveroomService.listMessages(roomId);
      setMessages(ms);
    } catch (e) { /* silent */ }
  }, [roomId]);

  // 加载场景/角色
  useEffect(() => {
    if (!roomId) return;
    setLoading(true);
    Promise.all([
      liveroomService.listScenarios({ limit: 20 }).catch(() => []),
      liveroomService.listPersonas({ limit: 20 }).catch(() => []),
    ]).then(([ss, ps]) => {
      setScenarios(ss);
      setPersonas(ps);
    }).finally(() => setLoading(false));
  }, [roomId]);

  useEffect(() => {
    loadRoom();
    loadParticipants();
    loadTranscripts();
    loadMessages();
    liveroomService.getHelperConfig(roomId).then(setHelperConfig).catch(() => null);
  }, [roomId, loadRoom, loadParticipants, loadTranscripts, loadMessages]);

  // 轮询转写（模拟实时）
  useEffect(() => {
    const t = setInterval(() => {
      loadTranscripts();
    }, 5000);
    return () => clearInterval(t);
  }, [loadTranscripts]);

  // 自动滚动
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [transcripts]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin" />
      </div>
    );
  }

  if (error || !room) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle size={28} className="mx-auto text-danger mb-2" />
          <div className="text-sm text-danger">{error || "房间不存在"}</div>
          <button
            onClick={() => router.push("/liveroom")}
            className="mt-3 text-xs text-success hover:underline"
          >
            返回房间列表
          </button>
        </div>
      </div>
    );
  }

  const isOwner = room.owner_id === (typeof window !== "undefined" ? localStorage.getItem("current_user_id") || "" : "");

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-7xl mx-auto px-4 py-4 sm:py-6">
        {/* 顶部 */}
        <RoomHeader
          room={room}
          isOwner={isOwner}
          onLeave={async () => {
            if (!confirm("确认退出房间？")) return;
            await liveroomService.leaveRoom(roomId);
            router.push("/liveroom");
          }}
          onEnd={async () => {
            if (!confirm("确认结束房间（仅房主可执行）？所有参与者将被关闭。")) return;
            await liveroomService.endRoom(roomId);
            router.push("/liveroom");
          }}
          onReview={() => router.push(`/liveroom/review/${roomId}`)}
        />

        {/* 错误提示 */}
        {error && (
          <div className="mb-4 px-4 py-3 border border-danger/30 bg-danger/10 text-sm text-danger rounded flex items-center gap-2">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {/* 三列布局 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* 左: 转写区 */}
          <div className="lg:col-span-5">
            <TranscriptPanel
              transcripts={transcripts}
              participants={participants}
              transcriptRef={transcriptRef}
              onMarkError={async (transcriptId, errorType) => {
                try {
                  await liveroomService.markError(roomId, {
                    transcript_id: transcriptId,
                    error_type: errorType,
                  });
                  await loadTranscripts();
                } catch (e: unknown) {
                  alert(e instanceof Error ? e.message : "操作失败");
                }
              }}
              onCaptureVocab={async (transcriptId, text) => {
                try {
                  await liveroomService.captureVocabulary(roomId, {
                    word: text,
                    transcript_id: transcriptId,
                  });
                  await loadTranscripts();
                } catch (e: unknown) {
                  alert(e instanceof Error ? e.message : "操作失败");
                }
              }}
            />
          </div>

          {/* 中: 语音通话 + 场景 */}
          <div className="lg:col-span-4 space-y-4">
            <VoiceRoomPanel
              roomId={roomId}
              participants={participants}
              isRecording={isRecording}
              onToggleRecording={async () => {
                if (isRecording && recordingId) {
                  await liveroomService.stopRecording(roomId, recordingId);
                  setIsRecording(false);
                  setRecordingId(null);
                } else {
                  const r = await liveroomService.startRecording(roomId);
                  setIsRecording(true);
                  setRecordingId(r.recording_id);
                }
              }}
            />
            <ScenarioPanel
              room={room}
              scenarios={scenarios}
              isOwner={isOwner}
              onChangeScenario={async (scenarioId) => {
                await liveroomService.changeScenario(roomId, scenarioId);
                await loadRoom();
              }}
            />
          </div>

          {/* 右: 参与者 / 词汇 / AI / 消息 */}
          <div className="lg:col-span-3 space-y-3">
            <ToggleButton
              icon={<Users size={14} />}
              label="参与者"
              count={participants.filter((p) => !p.left_at).length}
              active={showParticipantPanel}
              onClick={() => setShowParticipantPanel(!showParticipantPanel)}
            />
            <ToggleButton
              icon={<Sparkles size={14} />}
              label="AI 辅助"
              active={showHelperPanel}
              onClick={() => setShowHelperPanel(!showHelperPanel)}
            />
            <ToggleButton
              icon={<StickyNote size={14} />}
              label="词汇便签"
              active={showVocabPanel}
              onClick={() => setShowVocabPanel(!showVocabPanel)}
            />
            <ToggleButton
              icon={<MessageSquare size={14} />}
              label="文字辅助"
              count={messages.length}
              active={showMessagePanel}
              onClick={() => setShowMessagePanel(!showMessagePanel)}
            />

            {showParticipantPanel && (
              <ParticipantPanel
                participants={participants}
                isOwner={isOwner}
                onMute={async (userId, muted) => {
                  try {
                    await liveroomService.muteParticipant(roomId, userId, muted);
                    await loadParticipants();
                  } catch (e: unknown) {
                    alert(e instanceof Error ? e.message : "操作失败");
                  }
                }}
                onAddPersona={async (personaId) => {
                  try {
                    await liveroomService.addAIPersona(roomId, personaId);
                    await loadParticipants();
                  } catch (e: unknown) {
                    alert(e instanceof Error ? e.message : "操作失败");
                  }
                }}
                personas={personas}
              />
            )}
            {showHelperPanel && (
              <HelperPanel
                config={helperConfig}
                onUpdate={async (cfg) => {
                  await liveroomService.updateHelperConfig(roomId, cfg);
                  const c = await liveroomService.getHelperConfig(roomId);
                  setHelperConfig(c);
                }}
                onInvoke={async (helperType, query) => {
                  const r = await liveroomService.invokeAIHelper(roomId, {
                    helper_type: helperType,
                    query,
                  });
                  return r;
                }}
              />
            )}
            {showVocabPanel && (
              <VocabPanel
                transcripts={transcripts}
                onCapture={async (word, translation, context) => {
                  await liveroomService.captureVocabulary(roomId, {
                    word, translation, context_sentence: context,
                  });
                }}
              />
            )}
            {showMessagePanel && (
              <MessagePanel
                messages={messages}
                onPost={async (text, type) => {
                  await liveroomService.postMessage(roomId, { text, message_type: type });
                  await loadMessages();
                }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════
// 子组件
// ════════════════════════════════════════════════

function RoomHeader({
  room, isOwner, onLeave, onEnd, onReview,
}: {
  room: LanguageRoom;
  isOwner: boolean;
  onLeave: () => void;
  onEnd: () => void;
  onReview: () => void;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
      <div>
        <h1 className="text-xl font-semibold text flex items-center gap-2">
          <Volume2 size={20} />
          {room.name}
        </h1>
        <div className="text-xs text-muted mt-0.5 flex items-center gap-2 flex-wrap">
          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
            room.status === "active" ? "bg-success/20 text-success" : "bg-surface text-muted"
          }`}>
            {room.status === "active" ? "进行中" : "已结束"}
          </span>
          <span>· {room.participant_count}/{room.max_participants} 人</span>
          {room.is_recording_enabled && <span>· 录音开启</span>}
          {isOwner && <span className="text-success">· 你是房主</span>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onReview}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border border rounded-md hover:bg-surface"
        >
          <History size={13} /> 会话回顾
        </button>
        {isOwner && room.status === "active" && (
          <button
            onClick={onEnd}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border border-danger/30 text-danger rounded-md hover:bg-danger/10"
          >
            结束房间
          </button>
        )}
        <button
          onClick={onLeave}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border border rounded-md hover:bg-surface"
        >
          <X size={13} /> 退出
        </button>
      </div>
    </div>
  );
}

function TranscriptPanel({
  transcripts, participants, transcriptRef, onMarkError, onCaptureVocab,
}: {
  transcripts: RoomTranscript[];
  participants: RoomParticipant[];
  transcriptRef: React.RefObject<HTMLDivElement>;
  onMarkError: (transcriptId: string, errorType: "grammar" | "vocabulary" | "pronunciation" | "coherence") => void;
  onCaptureVocab: (transcriptId: string, text: string) => void;
}) {
  return (
    <div className="border border bg-surface rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border flex items-center justify-between">
        <div className="text-sm font-medium flex items-center gap-1.5">
          <Volume2 size={14} /> 实时转写
        </div>
        <div className="text-xs text-muted">{transcripts.length} 段</div>
      </div>
      <div
        ref={transcriptRef}
        className="h-96 overflow-y-auto p-3 space-y-2"
      >
        {transcripts.length === 0 && (
          <div className="text-center text-xs text-muted py-10">
            暂无转写。LiveKit 推流后将自动显示。
          </div>
        )}
        {transcripts.map((t) => {
          const p = participants.find((x) => x.id === t.participant_id);
          return (
            <div
              key={t.id}
              className={`text-sm px-3 py-2 rounded-md border ${
                t.is_error
                  ? "border-danger/20 bg-danger/10"
                  : "border bg-page"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <div className="text-[10px] font-mono text-muted">
                  {p?.role_label || p?.user_id?.slice(0, 8) || "匿名"}
                  {t.language && <span className="ml-1.5">[{t.language}]</span>}
                </div>
                <div className="text-[10px] text-muted">
                  {t.started_at ? new Date(t.started_at).toLocaleTimeString("zh-CN", { hour12: false }) : ""}
                </div>
              </div>
              <div className="text">{t.text}</div>
              <div className="mt-1.5 flex items-center gap-1 flex-wrap">
                <button
                  onClick={() => onMarkError(t.id, "grammar")}
                  className="text-[10px] px-1.5 py-0.5 border border-danger/20 text-danger rounded hover:bg-danger/10"
                >
                  标为语法错误
                </button>
                <button
                  onClick={() => onMarkError(t.id, "vocabulary")}
                  className="text-[10px] px-1.5 py-0.5 border border-warning/20 text-warning rounded hover:bg-warning/10"
                >
                  词汇
                </button>
                <button
                  onClick={() => onCaptureVocab(t.id, t.text.slice(0, 30))}
                  className="text-[10px] px-1.5 py-0.5 border border-success/20 text-success rounded hover:bg-success/10"
                >
                  <Plus size={9} className="inline" /> 词汇便签
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function VoiceRoomPanel({
  roomId, participants, isRecording, onToggleRecording,
}: {
  roomId: string;
  participants: RoomParticipant[];
  isRecording: boolean;
  onToggleRecording: () => void;
}) {
  const [token, setToken] = useState<string | null>(null);
  const [tokenUrl, setTokenUrl] = useState<string>("");
  useEffect(() => {
    liveroomService.issueToken(roomId).then((t) => {
      setToken(t.token);
      setTokenUrl(t.url);
    }).catch(() => null);
  }, [roomId]);

  return (
    <div className="border border bg-surface rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border flex items-center justify-between">
        <div className="text-sm font-medium flex items-center gap-1.5">
          <Mic size={14} /> 语音房间
        </div>
        <button
          onClick={onToggleRecording}
          className={`text-[10px] px-2 py-0.5 rounded ${
            isRecording
              ? "bg-danger/20 text-danger"
              : "border border text-muted"
          }`}
        >
          {isRecording ? "● 录音中" : "开始录音"}
        </button>
      </div>
      <div className="p-4">
        {/* LiveKit 占位区 (实际集成 LiveKit React SDK) */}
        <div className="aspect-video rounded-md border-2 border-dashed border flex items-center justify-center text-xs text-muted bg-page">
          {token ? (
            <div className="text-center">
              <Mic size={28} className="mx-auto mb-2 text-success" />
              <div>LiveKit 已连接</div>
              <div className="text-[10px] mt-1 opacity-70">{tokenUrl}</div>
              <div className="text-[10px] opacity-50">({participants.length} 人在线)</div>
            </div>
          ) : (
            <div className="text-center">
              <Loader2 size={20} className="mx-auto mb-2 animate-spin" />
              <div>正在连接 LiveKit...</div>
            </div>
          )}
        </div>
        <div className="mt-3 text-[10px] text-muted text-center">
          注: 完整 LiveKit SDK 集成需要前端安装 @livekit/components-react
        </div>
      </div>
    </div>
  );
}

function ScenarioPanel({
  room, scenarios, isOwner, onChangeScenario,
}: {
  room: LanguageRoom;
  scenarios: RoomScenario[];
  isOwner: boolean;
  onChangeScenario: (scenarioId: string) => void;
}) {
  const current = scenarios.find((s) => s.id === room.scenario_id);
  return (
    <div className="border border bg-surface rounded-lg overflow-hidden">
      <div className="px-4 py-2 border-b border">
        <div className="text-sm font-medium flex items-center gap-1.5">
          <ScrollText size={14} /> 场景提示
        </div>
      </div>
      <div className="p-3">
        {current ? (
          <div>
            <div className="text-sm font-medium">{current.name}</div>
            {current.prompt_text && (
              <div className="mt-1.5 text-xs px-2.5 py-1.5 bg-success/10 border border-success/20 text-success rounded">
                {current.prompt_text}
              </div>
            )}
            {current.target_goals?.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-xs text-muted">
                {current.target_goals.map((g, i) => (
                  <li key={i} className="flex items-start gap-1">
                    <span>• {g}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="text-xs text-muted text-center py-2">
            未选择场景
          </div>
        )}
        {isOwner && scenarios.length > 0 && (
          <div className="mt-3 border-t border pt-2">
            <select
              onChange={(e) => e.target.value && onChangeScenario(e.target.value)}
              className="w-full text-xs border border rounded px-2 py-1.5 bg-page"
              defaultValue=""
            >
              <option value="" disabled>切换场景...</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
}

function ToggleButton({
  icon, label, count, active, onClick,
}: {
  icon: React.ReactNode;
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between px-3 py-2 border rounded-md text-sm ${
        active
          ? "bg-success/10 border-success/30 text-success"
          : "border bg-surface hover:bg-surface-hover"
      }`}
    >
      <div className="flex items-center gap-1.5">
        {icon}
        {label}
      </div>
      {count !== undefined && (
        <span className="text-[10px] px-1.5 py-0.5 bg-white border border rounded">
          {count}
        </span>
      )}
    </button>
  );
}

function ParticipantPanel({
  participants, isOwner, onMute, onAddPersona, personas,
}: {
  participants: RoomParticipant[];
  isOwner: boolean;
  onMute: (userId: string, muted: boolean) => void;
  onAddPersona: (personaId: string) => void;
  personas: AIPersona[];
}) {
  return (
    <div className="border border bg-surface rounded-lg p-3 space-y-2">
      <div className="text-xs font-medium text-muted">参与者</div>
      {participants.filter((p) => !p.left_at).map((p) => (
        <div key={p.id} className="flex items-center justify-between px-2 py-1.5 border border rounded text-xs">
          <div className="flex items-center gap-1.5 min-w-0">
            {p.participant_type === "ai_companion" ? (
              <Sparkles size={11} className="text-accent flex-shrink-0" />
            ) : (
              <Users size={11} className="text-success flex-shrink-0" />
            )}
            <div className="truncate">
              {p.role_label || p.user_id.slice(0, 8)}
              {p.is_owner && <span className="ml-1 text-success text-[9px]">房主</span>}
            </div>
            {p.is_muted && <MicOff size={10} className="text-danger" />}
          </div>
          {isOwner && p.participant_type === "human" && !p.is_owner && (
            <button
              onClick={() => onMute(p.user_id, !p.is_muted)}
              className="text-[10px] text-muted hover:text-danger"
            >
              {p.is_muted ? "解除" : "静音"}
            </button>
          )}
        </div>
      ))}
      {isOwner && personas.length > 0 && (
        <div className="pt-2 border-t border">
          <div className="text-[10px] text-muted mb-1.5">邀请 AI 角色</div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {personas.slice(0, 5).map((p) => (
              <button
                key={p.id}
                onClick={() => onAddPersona(p.id)}
                className="w-full text-left px-2 py-1 border border-accent/20 rounded text-[10px] hover:bg-accent/10"
              >
                <Sparkles size={9} className="inline text-accent" /> {p.name}
                <span className="text-muted ml-1">({p.target_language})</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HelperPanel({
  config, onUpdate, onInvoke,
}: {
  config: InvasivenessConfig | null;
  onUpdate: (cfg: Partial<InvasivenessConfig>) => Promise<void>;
  onInvoke: (helperType: HelperType, query: string) => Promise<{ response: string }>;
}) {
  const [query, setQuery] = useState("");
  const [helperType, setHelperType] = useState<HelperType>("grammar");
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!config) {
    return (
      <div className="border border bg-surface rounded-lg p-3 text-xs text-center text-muted">
        加载配置中...
      </div>
    );
  }

  return (
    <div className="border border bg-surface rounded-lg p-3 space-y-2">
      <div className="text-xs font-medium">AI 辅助配置（用户主动）</div>
      <div className="text-[10px] text-muted">
        关键设计: AI 纠错 = 用户主动选择, 非 AI 评判
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span>侵入度</span>
          <select
            value={config.invasiveness_level}
            onChange={(e) => onUpdate({ invasiveness_level: e.target.value as InvasivenessLevel })}
            className="text-[10px] border border rounded px-1.5 py-0.5"
          >
            {(["low", "medium", "high"] as const).map((l) => (
              <option key={l} value={l}>{INVASIVENESS_LABELS[l]}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span>纠错倾向</span>
          <select
            value={config.correction_tendency}
            onChange={(e) => onUpdate({ correction_tendency: e.target.value as CorrectionTendency })}
            className="text-[10px] border border rounded px-1.5 py-0.5"
          >
            {(["none", "occasional", "proactive"] as const).map((l) => (
              <option key={l} value={l}>{CORRECTION_TENDENCY_LABELS[l]}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="pt-2 border-t border space-y-1.5">
        <div className="text-[10px] text-muted">召唤辅助者</div>
        <select
          value={helperType}
          onChange={(e) => setHelperType(e.target.value as HelperType)}
          className="w-full text-[10px] border border rounded px-1.5 py-1"
        >
          {(["grammar", "vocabulary", "sentence_pattern"] as const).map((t) => (
            <option key={t} value={t}>{HELPER_TYPE_LABELS[t]}</option>
          ))}
        </select>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="提问..."
          className="w-full text-[10px] border border rounded px-1.5 py-1 bg-page"
        />
        <button
          onClick={async () => {
            if (!query.trim()) return;
            setLoading(true);
            try {
              const r = await onInvoke(helperType, query);
              setResponse(r.response);
            } catch (e: unknown) {
              setResponse(`错误: ${e instanceof Error ? e.message : "未知错误"}`);
            } finally {
              setLoading(false);
            }
          }}
          disabled={loading || !query.trim()}
          className="w-full text-[10px] py-1 bg-success text-white rounded hover:bg-success disabled:opacity-50"
        >
          {loading ? <Loader2 size={10} className="inline animate-spin" /> : "召唤"}
        </button>
        {response && (
          <div className="text-[10px] px-2 py-1.5 bg-info/10 border border-info/20 text-info rounded">
            {response}
          </div>
        )}
      </div>
    </div>
  );
}

function VocabPanel({
  transcripts, onCapture,
}: {
  transcripts: RoomTranscript[];
  onCapture: (word: string, translation: string, context: string) => Promise<void>;
}) {
  const [word, setWord] = useState("");
  const [translation, setTranslation] = useState("");
  return (
    <div className="border border bg-surface rounded-lg p-3 space-y-1.5">
      <div className="text-xs font-medium">词汇便签</div>
      <div className="text-[10px] text-muted">
        复用 FlashCard 数据卡 (cross_module_source=language_room)
      </div>
      <input
        value={word}
        onChange={(e) => setWord(e.target.value)}
        placeholder="单词"
        className="w-full text-xs border border rounded px-2 py-1 bg-page"
      />
      <input
        value={translation}
        onChange={(e) => setTranslation(e.target.value)}
        placeholder="翻译"
        className="w-full text-xs border border rounded px-2 py-1 bg-page"
      />
      <button
        onClick={async () => {
          if (!word.trim()) return;
          await onCapture(word, translation, "");
          setWord(""); setTranslation("");
        }}
        className="w-full text-xs py-1 bg-success text-white rounded hover:bg-success"
      >
        <Plus size={11} className="inline" /> 添加
      </button>
    </div>
  );
}

function MessagePanel({
  messages, onPost,
}: {
  messages: RoomMessage[];
  onPost: (text: string, type: MessageType) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [type, setType] = useState<MessageType>("text");
  return (
    <div className="border border bg-surface rounded-lg p-3 space-y-1.5">
      <div className="text-xs font-medium">文字辅助</div>
      <div className="text-[10px] text-muted">
        复用 ExplainCard 浮卡
      </div>
      <select
        value={type}
        onChange={(e) => setType(e.target.value as MessageType)}
        className="w-full text-[10px] border border rounded px-1.5 py-1"
      >
        <option value="text">文本</option>
        <option value="link">链接</option>
        <option value="spelling">拼写</option>
        <option value="note">笔记</option>
      </select>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="补充说明..."
        className="w-full text-xs border border rounded px-2 py-1 bg-page h-16 resize-none"
      />
      <button
        onClick={async () => {
          if (!text.trim()) return;
          await onPost(text, type);
          setText("");
        }}
        className="w-full text-xs py-1 bg-success text-white rounded hover:bg-success"
      >
        <Send size={11} className="inline" /> 发送
      </button>
      <div className="space-y-1 max-h-24 overflow-y-auto">
        {messages.slice(0, 5).map((m) => (
          <div key={m.id} className="text-[10px] px-1.5 py-1 bg-info/10 border border-info/20 rounded">
            <span className="text-[9px] text-info">[{m.message_type || "text"}]</span> {m.content || m.text}
          </div>
        ))}
      </div>
    </div>
  );
}
