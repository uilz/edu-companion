"use client";

/**
 * FlashCard 统计面板
 * 依据 docs/modules/flashcard/overview.md §8
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart3, BookOpen, Calendar, TrendingUp, Brain, Activity,
  RefreshCw, ChevronLeft, AlertCircle, Loader2, Tag, Layers,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import Card, { CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Progress } from "@/components/ui/Progress";
import { flashcardService, FlashCardStats, CARD_TYPE_LABELS, CARD_SOURCE_LABELS, STATUS_LABELS } from "@/lib/api/flashcard-api";

export default function FlashCardStatsPage() {
  const router = useRouter();
  const [stats, setStats] = useState<FlashCardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await flashcardService.getStats();
      setStats(data);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="container mx-auto p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="container mx-auto p-6 max-w-2xl">
        <Card>
          <CardContent className="p-12 text-center">
            <AlertCircle className="w-12 h-12 mx-auto text-red-500 mb-3" />
            <div className="text-lg font-medium mb-2">加载失败</div>
            <div className="text-sm text-muted-foreground mb-4">{error}</div>
            <Button onClick={load}>重试</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => router.push("/flashcard")}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <BarChart3 className="w-6 h-6" />
              统计面板
            </h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            卡片分布、FSRS 调度参数与复习预测
          </p>
        </div>
        <Button variant="outline" onClick={load}>
          <RefreshCw className="w-4 h-4 mr-1" />
          刷新
        </Button>
      </div>

      {/* 顶部统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <BookOpen className="w-3.5 h-3.5" /> 卡片总量
            </div>
            <div className="text-3xl font-bold mt-1">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Calendar className="w-3.5 h-3.5" /> 今日到期
            </div>
            <div className="text-3xl font-bold mt-1 text-orange-500">{stats.due_today}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Calendar className="w-3.5 h-3.5" /> 7天内到期
            </div>
            <div className="text-3xl font-bold mt-1">{stats.due_7d}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <TrendingUp className="w-3.5 h-3.5" /> 平均稳定性
            </div>
            <div className="text-3xl font-bold mt-1">{stats.average_stability.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground mt-1">天</div>
          </CardContent>
        </Card>
      </div>

      {/* FSRS 调度参数 */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="w-5 h-5" />
            FSRS 调度参数
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <TrendingUp className="w-4 h-4" /> 平均稳定性 (S)
              </div>
              <div className="text-2xl font-bold">{stats.average_stability.toFixed(2)} 天</div>
              <Progress value={Math.min(100, (stats.average_stability / 30) * 100)} className="mt-2" />
              <div className="text-xs text-muted-foreground mt-1">0-30 天范围</div>
            </div>
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <Brain className="w-4 h-4" /> 平均难度 (D)
              </div>
              <div className="text-2xl font-bold">{stats.average_difficulty.toFixed(2)} / 10</div>
              <Progress value={stats.average_difficulty * 10} className="mt-2" />
              <div className="text-xs text-muted-foreground mt-1">1=最简单, 10=最难</div>
            </div>
            <div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <Activity className="w-4 h-4" /> 平均遗忘速率 (F)
              </div>
              <div className="text-2xl font-bold">{(stats.average_forgetting_rate * 100).toFixed(0)}%</div>
              <Progress value={stats.average_forgetting_rate * 100} className="mt-2" />
              <div className="text-xs text-muted-foreground mt-1">遗忘速率与难度正相关</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 分布: 类型 / 来源 / 状态 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <DistributionCard
          title="按类型"
          icon={<Layers className="w-5 h-5" />}
          data={stats.by_type}
          labels={CARD_TYPE_LABELS as any}
          total={stats.total}
        />
        <DistributionCard
          title="按来源"
          icon={<Tag className="w-5 h-5" />}
          data={stats.by_source}
          labels={CARD_SOURCE_LABELS as any}
          total={stats.total}
        />
        <DistributionCard
          title="按状态"
          icon={<BookOpen className="w-5 h-5" />}
          data={stats.by_status}
          labels={STATUS_LABELS as any}
          total={stats.total}
        />
      </div>

      {/* 说明 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">系统边界</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-1">
          <p>• FlashCard 不维护独立的"掌握度"概念 — 状态归 <code>CognitiveNode.Belief</code></p>
          <p>• FSRS 计算的是**材料的下次复习时间**, 不是知识点的状态</p>
          <p>• 复习事件通过事件流以小权重 (0.1) 回写 Belief, 与练习错题、对话等数据源协同融合</p>
        </CardContent>
      </Card>
    </div>
  );
}

// ── 分布卡片 ──

function DistributionCard({
  title, icon, data, labels, total,
}: {
  title: string;
  icon: React.ReactNode;
  data: Record<string, number>;
  labels: Record<string, string>;
  total: number;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {entries.length === 0 ? (
          <div className="text-sm text-muted-foreground">暂无数据</div>
        ) : entries.map(([k, v]) => {
          const pct = total > 0 ? (v / total) * 100 : 0;
          return (
            <div key={k} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>{labels[k] || k}</span>
                <span className="text-muted-foreground">
                  {v} ({pct.toFixed(0)}%)
                </span>
              </div>
              <Progress value={pct} className="h-1.5" />
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
