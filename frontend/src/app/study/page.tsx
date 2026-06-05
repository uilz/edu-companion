// 客户端组件声明
"use client";

import {
  BookOpen, CheckCircle2, Circle, RefreshCw, Loader2,
  Clock, Target, TrendingUp, AlertCircle, ChevronRight, Zap,
} from "lucide-react";
import Card from "@/components/ui/Card";
import { useStudyPlan } from "@/hooks/study/useStudyPlan";

// 学习计划页面：AI 自适应学习规划 + 进度追踪 + 智能建议
export default function StudyPage() {
  const {
    planItems, planMeta, progress, suggestions, loading, generating, error,
    handleGenerate, handleComplete, completionRate, habitLabel,
  } = useStudyPlan();

  // 加载状态
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* 页面头部 */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight">
              学习规划
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              第 {planMeta?.week_number ?? "?"} 周 · 
              {planMeta ? ` ${habitLabel[planMeta.habit_level] || planMeta.habit_level}` : ""}
              {planMeta && ` · 准确率 ${(planMeta.recent_accuracy * 100).toFixed(0)}%`}
            </p>
          </div>
          <button onClick={handleGenerate} disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 active:scale-[0.97] transition-opacity disabled:opacity-50">
            {generating ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            {planItems.length ? "刷新计划" : "生成计划"}
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mb-6 px-4 py-3 border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] flex items-center gap-2">
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {/* 空状态 */}
        {!planItems.length && !loading && (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 border border-[var(--color-border)] flex items-center justify-center">
              <BookOpen size={28} className="text-[var(--color-text-muted)]" />
            </div>
            <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">还没有学习计划</h2>
            <p className="text-sm text-[var(--color-text-muted)] max-w-sm mx-auto mb-6">
              基于你的知识掌握情况和前置依赖关系，AI 会为你生成个性化的学习计划
            </p>
            <button onClick={handleGenerate} disabled={generating}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 active:scale-[0.97] transition-opacity">
              {generating ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
              生成我的学习计划
            </button>
          </div>
        )}

        {/* 计划内容 */}
        {planItems.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {/* 进度概览卡片 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 border border-[var(--color-border)] bg-[var(--color-card)]">
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><Target size={12} />完成进度</div>
                  <div className="text-lg font-semibold text-[var(--color-text)]">{(completionRate * 100).toFixed(0)}%</div>
                </div>
                <div className="p-3 border border-[var(--color-border)] bg-[var(--color-card)]">
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><CheckCircle2 size={12} />已完成</div>
                  <div className="text-lg font-semibold text-[var(--color-text)]">{progress?.completed_tasks ?? 0}</div>
                </div>
                <div className="p-3 border border-[var(--color-border)] bg-[var(--color-card)]">
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><BookOpen size={12} />待完成</div>
                  <div className="text-lg font-semibold text-[var(--color-text)]">{(progress?.total_tasks ?? 0) - (progress?.completed_tasks ?? 0)}</div>
                </div>
                <div className="p-3 border border-[var(--color-border)] bg-[var(--color-card)]">
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] mb-1"><Clock size={12} />预计时间</div>
                  <div className="text-lg font-semibold text-[var(--color-text)]">{planMeta?.estimated_total_minutes ?? 0} min</div>
                </div>
              </div>

              {/* 任务列表 */}
              <div className="space-y-2">
                {planItems.map((item) => (
                  <div key={item.task_id}
                    className={`flex items-center gap-3 p-3 border border-[var(--color-border)] bg-[var(--color-card)] transition-all ${item.completed ? "opacity-60" : "hover:border-[var(--color-accent)]/30"}`}>
                    <button onClick={() => !item.completed && handleComplete(item.task_id)}
                      className="flex-shrink-0 text-[var(--color-text-muted)] hover:text-[#22c55e] transition-colors">
                      {item.completed ? <CheckCircle2 size={16} className="text-[#22c55e]" /> : <Circle size={16} />}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-[var(--color-text)]">{item.title}</div>
                      <div className="text-xs text-[var(--color-text-muted)] mt-0.5 truncate">{item.description}</div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-[10px] px-1.5 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)]">
                        {item.difficulty > 3 ? "较难" : item.difficulty > 2 ? "适中" : "简单"}
                      </span>
                      <span className="text-xs text-[var(--color-text-muted)]">{item.estimated_minutes} min</span>
                      <ChevronRight size={12} className="text-[var(--color-text-muted)]" />
                    </div>
                  </div>
                ))}
              </div>

              {/* 学习建议 */}
              {suggestions?.suggestion && (
                <div className="p-4 border border-[var(--color-border)] bg-[var(--color-card)]">
                  <div className="flex items-start gap-3">
                    <TrendingUp size={16} className="text-[var(--color-accent)] mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{suggestions.suggestion}</p>
                  </div>
                </div>
              )}
            </div>

            {/* 侧边栏 */}
            <div className="space-y-4">
              {/* AI 建议：紧急 */}
              {suggestions?.urgent && suggestions.urgent.length > 0 && (
                <Card title="🔥 紧急补强">
                  <div className="space-y-1.5">
                    {suggestions.urgent.slice(0, 4).map((s) => (
                      <div key={s.skill_id} className="text-xs text-[var(--color-text-muted)] px-2 py-1 border-l-2 border-[#ef4444]">
                        {s.label} <span className="text-[#ef4444]">({(s.p_known * 100).toFixed(0)}%)</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* AI 建议：巩固 */}
              {suggestions?.building && suggestions.building.length > 0 && (
                <Card title="📈 巩固提升">
                  <div className="space-y-1.5">
                    {suggestions.building.slice(0, 4).map((s) => (
                      <div key={s.skill_id} className="text-xs text-[var(--color-text-muted)] px-2 py-1 border-l-2 border-[#22c55e]">
                        {s.label} <span className="text-[#22c55e]">({(s.p_known * 100).toFixed(0)}%)</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* AI 建议：新课 */}
              {suggestions?.new_topic && suggestions.new_topic.length > 0 && (
                <Card title="🔭 新知识">
                  <div className="space-y-1.5">
                    {suggestions.new_topic.slice(0, 3).map((s) => (
                      <div key={s.skill_id} className="text-xs text-[var(--color-text-muted)] px-2 py-1 border-l-2 border-[var(--color-accent)]">
                        {s.label}
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
