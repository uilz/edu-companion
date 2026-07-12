"use client";

import { RotateCcw, Settings } from "lucide-react";
import { useSecretaryDashboard } from "@/hooks/useSecretaryDashboard";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import Card from "@/components/ui/Card";
import FocusCard from "./FocusCard";
import SmartStatsGrid from "./SmartStatsGrid";
import PendingPanel from "./PendingPanel";
import RecommendationCard from "./RecommendationCard";
import ActivityCard from "./ActivityCard";

export default function SecretaryDashboard() {
  const { data, loading, error, refetch } = useSecretaryDashboard();

  if (loading || !data) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 space-y-5">
        {/* Header */}
        <div className="flex items-end justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-[22px] font-semibold text-ink-primary tracking-tight">
              {data.greeting || "欢迎使用"}
            </h1>
            <p className="text-[13px] text-ink-secondary mt-1">
              {data.date || new Date().toLocaleDateString("zh-CN")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => refetch()}>
              <RotateCcw size={13} />
              刷新
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.location.href = "/secretary/settings"}>
              <Settings size={13} />
              设置
            </Button>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-lg border border-danger/20 bg-danger/5 text-sm text-danger">
            加载仪表盘失败，请稍后重试。
          </div>
        )}

        {/* 今日焦点 */}
        <FocusCard focus={data.focus} />

        {/* 智能统计卡 */}
        <SmartStatsGrid stats={data.stats} />

        {/* 双栏：待处理 + 推荐/活动 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-5">
            <Card>
              <PendingPanel
                items={data.pending.items}
                onChange={() => refetch()}
              />
            </Card>
          </div>
          <div className="space-y-5">
            <RecommendationCard recommendations={data.recommendations} />
            <ActivityCard
              activities={data.activities.items}
              onRefetch={() => refetch()}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-5 space-y-5">
        <div>
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-32 mt-2" />
        </div>
        <Skeleton className="h-32 w-full" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Skeleton className="h-96 lg:col-span-2" />
          <div className="space-y-5">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        </div>
      </div>
    </div>
  );
}
