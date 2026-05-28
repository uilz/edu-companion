// 客户端组件标记 — 使用 React hooks 需要在浏览器端渲染
"use client";

// React hooks
import { useState, useEffect } from "react";
// 图标库 — 用于统计页面的各种图标展示
import { BarChart3, Target, Clock, TrendingUp, Loader2, Brain, MessageCircle } from "lucide-react";
// 通用卡片组件
import Card from "@/components/ui/Card";
import { API_BASE } from "@/lib/api";

// ──────────────────────────────────────────
// 练习统计数据接口 — 对应后端 /api/practice/stats 的响应结构
// ──────────────────────────────────────────
interface PracticeStats {
  user_id: string;
  total_questions: number;
  total_correct: number;
  accuracy: number;
  study_minutes: number;
  weak_skills: [string, number][];
  strong_skills: [string, number][];
}

// ──────────────────────────────────────────
// 单个技能知识状态接口 — CognitiveNode 知识追踪
// ──────────────────────────────────────────
interface SkillState {
  skill_id: string;
  label: string;
  mastery: number;
  attempts: number;
  trend: string;
}

// ──────────────────────────────────────────
// 知识状态整体数据接口 — skills 为 skill_id → SkillState 的映射
// ──────────────────────────────────────────
interface KnowledgeStateData {
  total_skills: number;
  skills: Record<string, SkillState>;
}

// ──────────────────────────────────────────
// 主组件：学习统计页面
// 展示练习概览卡片 + 薄弱/掌握知识点列表 + 知识画像（BKT+对话融合）
// ──────────────────────────────────────────
export default function StatsPage() {
  // 练习统计数据（总答题数、正确率、时长等）
  const [stats, setStats] = useState<PracticeStats | null>(null);
  // 技能知识状态数组（按 mastery 排序）
  const [knowledge, setKnowledge] = useState<SkillState[]>([]);
  // 加载状态
  const [loading, setLoading] = useState(true);

  // 页面挂载时并发请求练习统计和知识状态数据
  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/practice/stats`).then((r) => r.json()),
      fetch(`${API_BASE}/api/practice/knowledge/state`).then((r) => r.json()).catch(() => null),
    ])
      .then(([statsData, knowledgeData]) => {
        setStats(statsData.overview || statsData);
        // 如果有知识状态数据，提取 skills 并按 unified_mastery 降序排列
        if (knowledgeData?.skills) {
          const skills = Object.entries(knowledgeData.skills).map(([id, s]) => ({
            ...(s as SkillState),
            skill_id: id,
          }));
          skills.sort((a, b) => b.mastery - a.mastery);
          setKnowledge(skills);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // 加载中 — 显示旋转加载动画
  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)]">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
        </div>
      </main>
    );
  }

  // 数据加载完成 — 计算展示用的格式化数据
  // 正确率（百分比）、学习时长（小时+分钟）
  const accuracyPercent = stats?.accuracy != null ? (stats.accuracy * 100).toFixed(1) : null;
  const hours = stats?.study_minutes ? Math.floor(stats.study_minutes / 60) : 0;
  const minutes = stats?.study_minutes ? stats.study_minutes % 60 : 0;

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <h1 className="text-2xl font-bold text-[var(--color-text)] mb-6 tracking-tight">
          学习统计
        </h1>

        {/* 统计概览卡片 — 总答题、正确率、学习时长、知识画像追踪数 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {[
            {
              icon: <BarChart3 size={20} />, label: "总答题", value: `${stats?.total_questions ?? 0}`,
              sub: stats?.total_correct != null ? `正确 ${stats.total_correct}` : "",
            },
            {
              icon: <TrendingUp size={20} />, label: "正确率",
              value: `${accuracyPercent ?? "?"}%`,
              sub: accuracyPercent != null && parseInt(accuracyPercent) >= 80 ? "优秀"
                : accuracyPercent != null && parseInt(accuracyPercent) >= 60 ? "良好" : "需努力",
            },
            {
              icon: <Clock size={20} />, label: "学习时长",
              value: hours > 0 ? `${hours}h${minutes}m` : `${minutes}m`,
              sub: "累计时间",
            },
            {
              icon: <Brain size={20} />, label: "知识画像",
              value: `${knowledge.length}`,
              sub: "追踪技能",
            },
          ].map((card, i) => (
            <Card key={i}>
              <div className="text-[var(--color-accent)] mb-2">{card.icon}</div>
              <div className="text-2xl font-bold text-[var(--color-text)]">{card.value}</div>
              <div className="text-xs text-[var(--color-text-muted)]">{card.label} · {card.sub}</div>
            </Card>
          ))}
        </div>

        {/* 薄弱知识点 — 正确率较低的技能，按错误率排序展示 */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">
            🔴 薄弱知识点
          </h2>
          {stats?.weak_skills && stats.weak_skills.length > 0 ? (
            <div className="space-y-2">
              {stats.weak_skills.map(([skill, accuracy]) => (
                <div key={skill} className="flex items-center justify-between p-3 bg-[var(--color-surface)]">
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div className="h-full bg-[var(--color-error)] transition-all"
                        style={{ width: `${(accuracy * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">{(accuracy * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">暂无薄弱点数据</p>
          )}
        </div>

        {/* 掌握好的知识点 — 正确率较高的技能，绿色进度条展示 */}
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4">
            🟢 掌握好的知识点
          </h2>
          {stats?.strong_skills && stats.strong_skills.length > 0 ? (
            <div className="space-y-2">
              {stats.strong_skills.map(([skill, accuracy]) => (
                <div key={skill} className="flex items-center justify-between p-3 bg-[var(--color-surface)]">
                  <span className="text-sm text-[var(--color-text)]">{skill}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-1.5 bg-[var(--color-border)]">
                      <div className="h-full bg-[var(--color-success)] transition-all"
                        style={{ width: `${(accuracy * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)]">{(accuracy * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">多练几次就有了！</p>
          )}
        </div>

        {/* 知识画像 — CognitiveNode 技能掌握情况 */}
        {knowledge.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text)] mb-4 flex items-center gap-2">
              <MessageCircle size={16} className="text-[var(--color-accent)]" />
              知识画像
            </h2>
            <div className="space-y-2">
              {knowledge.map((sk) => {
                const masteryPercent = (sk.mastery * 100).toFixed(0);
                const isMastered = sk.mastery >= 0.8;
                const isLearning = sk.mastery >= 0.4 && sk.mastery < 0.8;
                const barColor = isMastered ? "bg-[#10b981]"
                  : isLearning ? "bg-[#3b82f6]" : "bg-[var(--color-text-muted)]";
                const status = isMastered ? "已掌握"
                  : isLearning ? "学习中" : "初学";
                const trendEmoji = sk.trend === "ascending" || sk.trend === "improving" ? "📈"
                  : sk.trend === "descending" || sk.trend === "volatile" ? "📉" : "";

                return (
                  <div key={sk.skill_id} className="p-3 bg-[var(--color-surface)]">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-medium text-[var(--color-text)] truncate flex-1">
                        {sk.label || sk.skill_id}
                      </span>
                      <div className="flex items-center gap-2 flex-shrink-0 text-[10px]">
                        <span className={`px-1.5 py-0.5 ${
                          isMastered ? "text-[#10b981] bg-[#10b981]/10"
                          : isLearning ? "text-[#3b82f6] bg-[#3b82f6]/10"
                          : "text-[var(--color-text-muted)] bg-[var(--color-border)]"
                        }`}>
                          {status}
                        </span>
                        <span className="text-[var(--color-text-muted)]">{masteryPercent}%</span>
                      </div>
                    </div>
                    <div className="w-full h-1.5 bg-[var(--color-border)] mb-1.5">
                      <div
                        className={`h-full ${barColor} transition-all`}
                        style={{ width: `${masteryPercent}%` }}
                      />
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-[var(--color-text-muted)]">
                      <span>📝 练习: {sk.attempts}次</span>
                      {trendEmoji && <span>{trendEmoji} {sk.trend}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 无知识画像数据时的占位提示 — 鼓励用户开始练习或对话 */}
        {knowledge.length === 0 && (
          <div className="text-center py-8 border border-[var(--color-border)]">
            <Brain size={28} className="text-[var(--color-text-muted)] mx-auto mb-3" />
            <p className="text-sm text-[var(--color-text-muted)]">
              知识画像将在练习和对话后自动生成
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
