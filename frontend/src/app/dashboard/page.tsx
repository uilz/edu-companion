'use client'; // 客户端组件，使用浏览器 API（URL 参数等）

// React / Next.js 核心导入
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';
import DashboardShell, { type TabId } from '@/components/dashboard/DashboardShell';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

/**
 * TabLoader - 标签页懒加载时的加载动画组件
 * 显示一个旋转的 accent 色加载图标
 */
function TabLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
    </div>
  );
}

// ----- 懒加载各标签页组件 -----
// 使用 next/dynamic 按需加载，减少首屏包体积
const OverviewTab = dynamic(() => import('@/components/dashboard/tabs/OverviewTab').then(m => m.OverviewTab), {
  loading: () => <TabLoader />,
});
const AnalyticsTab = dynamic(() => import('@/components/dashboard/tabs/AnalyticsTab').then(m => m.AnalyticsTab), {
  loading: () => <TabLoader />,
});
const ErrorsTab = dynamic(() => import('@/components/dashboard/tabs/ErrorsTab').then(m => m.ErrorsTab), {
  loading: () => <TabLoader />,
});
const CalendarTab = dynamic(() => import('@/components/dashboard/tabs/CalendarTab').then(m => m.CalendarTab), {
  loading: () => <TabLoader />,
});
const AchievementsTab = dynamic(() => import('@/components/dashboard/tabs/AchievementsTab').then(m => m.AchievementsTab), {
  loading: () => <TabLoader />,
});
const PlanTab = dynamic(() => import('@/components/dashboard/tabs/PlanTab').then(m => m.PlanTab), {
  loading: () => <TabLoader />,
});
const QualityTab = dynamic(() => import('@/components/dashboard/tabs/QualityTab').then(m => m.QualityTab), {
  loading: () => <TabLoader />,
});
const GraphTab = dynamic(() => import('@/components/dashboard/tabs/GraphTab').then(m => m.GraphTab), {
  loading: () => <TabLoader />,
});
const ProgressTab = dynamic(() => import('@/components/dashboard/tabs/ProgressTab').then(m => m.ProgressTab), {
  loading: () => <TabLoader />,
});
const StatsTab = dynamic(() => import('@/components/dashboard/tabs/StatsTab').then(m => m.StatsTab), {
  loading: () => <TabLoader />,
});

/**
 * TAB_COMPONENTS - TabId 到组件实例的映射表
 * 用于根据 URL 参数快速查找对应的标签页组件
 */
const TAB_COMPONENTS: Record<TabId, React.ComponentType> = {
  overview: OverviewTab,
  analytics: AnalyticsTab,
  errors: ErrorsTab,
  graph: GraphTab,
  calendar: CalendarTab,
  achievements: AchievementsTab,
  plan: PlanTab,
  progress: ProgressTab,
  quality: QualityTab,
  stats: StatsTab,
};

/**
 * DashboardContent - 仪表盘主内容区
 * 从 URL 查询参数中读取 ?tab=xxx，渲染对应的标签页组件
 * 若参数无效或缺失，默认显示 overview 标签页
 */
function DashboardContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab') as TabId | null;
  const activeTab: TabId = tabParam && TAB_COMPONENTS[tabParam] ? tabParam : 'overview';

  const TabComponent = TAB_COMPONENTS[activeTab];

  return (
    <DashboardShell activeTab={activeTab}>
      <ErrorBoundary>
        <TabComponent />
      </ErrorBoundary>
    </DashboardShell>
  );
}

/**
 * DashboardPage - 仪表盘页面入口（默认导出）
 * 使用 Suspense 包裹 DashboardContent，整体渲染前先显示全屏加载动画
 */
export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[var(--color-accent)]" />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
