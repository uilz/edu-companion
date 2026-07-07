"use client";

/**
 * LanguageRoom 主页 — 房间列表/入口
 * 依据 docs/modules/language-room/overview.md + ADR 0004
 *
 * 核心原则：
 *  - 不评判、不主导、不强制流程
 *  - 邀请制（无公开房间列表）
 *  - 数据归属 = 参与者各自存
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Mic, Users, Sparkles, Plus, Library, Loader2, AlertCircle, ScrollText } from "lucide-react";
import { liveroomService, LanguageRoom, RoomType, ROOM_TYPE_LABELS } from "@/lib/api/liveroom-api";
import { EntryCard } from "@/components/ui/EntryCard";
import { StatCard } from "@/components/ui/StatCard";

export default function LiveRoomPage() {
  const router = useRouter();
  const [rooms, setRooms] = useState<LanguageRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "ended">("all");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const items = await liveroomService.listRooms({ limit: 30 });
        setRooms(items);
      } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = rooms.filter((r) =>
    statusFilter === "all" ? true : r.status === statusFilter,
  );

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* 头部 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text tracking-tight flex items-center gap-2">
              <Mic size={22} /> 实时语音房间
            </h1>
            <p className="text-sm text-muted mt-1">
              场景化对话练习 · AI 角色 · 转写 · 错误标记 — 不评判、不主导
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/liveroom/scenarios")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border rounded-md hover:bg-surface"
            >
              <ScrollText size={14} /> 场景库
            </button>
            <button
              onClick={() => router.push("/liveroom/personas")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border rounded-md hover:bg-surface"
            >
              <Sparkles size={14} /> AI 角色
            </button>
            <button
              onClick={() => router.push("/liveroom/create")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-success text-white rounded-md hover:bg-success"
            >
              <Plus size={14} /> 创建房间
            </button>
          </div>
        </div>

        {/* 加载/错误 */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-muted" />
          </div>
        )}
        {error && (
          <div className="mb-6 px-4 py-3 border border-danger/30 bg-danger/10 text-sm text-danger flex items-center gap-2 rounded">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {/* 概览卡片 */}
        {!loading && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard label="总房间" value={String(rooms.length)} hint="我参与或创建的房间" />
            <StatCard
              label="进行中"
              value={String(rooms.filter((r) => r.status === "active").length)}
              hint="可加入或继续"
              color="text-success"
            />
            <StatCard
              label="已结束"
              value={String(rooms.filter((r) => r.status === "ended").length)}
              hint="可查看回顾"
            />
            <StatCard
              label="开启录音"
              value={String(rooms.filter((r) => r.is_recording_enabled).length)}
              hint="录音可选 (决策 10)"
            />
          </div>
        )}

        {/* 状态筛选 */}
        {!loading && rooms.length > 0 && (
          <div className="flex items-center gap-2 mb-4">
            {(["all", "active", "ended"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 text-xs rounded-md border ${
                  statusFilter === s
                    ? "bg-success/10 border-success/30 text-success"
                    : "border hover:bg-surface"
                }`}
              >
                {s === "all" ? "全部" : s === "active" ? "进行中" : "已结束"}
              </button>
            ))}
          </div>
        )}

        {/* 入口卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <EntryCard
            variant="button"
            icon={<Mic size={20} />}
            title="创建房间"
            description="设定场景与 AI 角色，邀请伙伴开始对话"
            onClick={() => router.push("/liveroom/create")}
            cta="创建新房间"
          />
          <EntryCard
            variant="button"
            icon={<Library size={20} />}
            title="场景库"
            description="系统预置和自定义场景模板 — 咖啡馆 / 学术 / 商务"
            onClick={() => router.push("/liveroom/scenarios")}
            cta="浏览场景"
          />
          <EntryCard
            variant="button"
            icon={<Sparkles size={20} />}
            title="AI 角色库"
            description="配置 AI 同伴和辅助者 — 纠错倾向 = 用户主动选择"
            onClick={() => router.push("/liveroom/personas")}
            cta="查看 AI 角色"
          />
        </div>

        {/* 房间列表 */}
        {!loading && filtered.length > 0 && (
          <div className="border border bg-surface rounded-lg p-5">
            <h2 className="text-sm font-semibold text-muted mb-3">我的房间</h2>
            <div className="space-y-2">
              {filtered.slice(0, 20).map((r) => (
                <button
                  key={r.id}
                  onClick={() => router.push(`/liveroom/rooms/${r.id}`)}
                  className="w-full flex items-center justify-between px-3 py-2 border border rounded-md hover:bg-surface-hover text-left"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-xs font-mono text-muted w-24 truncate">
                      {r.id.slice(0, 12)}
                    </div>
                    <div className="text-sm font-medium">{r.name}</div>
                    <div className="text-xs text-muted">
                      {ROOM_TYPE_LABELS[r.room_type] || r.room_type}
                    </div>
                    <div className="text-xs text-muted flex items-center gap-1">
                      <Users size={11} /> {r.participant_count}/{r.max_participants}
                    </div>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        r.status === "active"
                          ? "bg-success/20 text-success"
                          : "bg-surface text-muted"
                      }`}
                    >
                      {r.status === "active" ? "进行中" : "已结束"}
                    </span>
                  </div>
                  <div className="text-xs text-muted">
                    {r.started_at
                      ? new Date(r.started_at).toLocaleString("zh-CN", { hour12: false })
                      : "未开始"}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="border border-dashed border rounded-lg p-10 text-center text-sm text-muted">
            <Mic size={28} className="mx-auto mb-2 opacity-50" />
            <div>暂无房间</div>
            <div className="mt-1 text-xs">点击"创建房间"开始，或通过邀请链接加入</div>
          </div>
        )}
      </div>
    </div>
  );
}


