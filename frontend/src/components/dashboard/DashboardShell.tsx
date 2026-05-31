'use client';

// 导入 React 类型与 Next.js 路由/搜索参数钩子
import { ReactNode } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

// 标签页标识联合类型 —— 定义所有可用的仪表盘页面
type TabId = 'overview' | 'analytics' | 'errors' | 'calendar' | 'achievements' | 'plan' | 'quality' | 'graph' | 'progress' | 'stats' | 'study';

// 标签页配置接口
interface Tab {
  id: TabId;
  label: string;
  icon: string;
}

// 完整标签页配置列表 —— 每个标签页包含 ID、中文标签和图标
const TABS: Tab[] = [
  { id: 'overview', label: '概览', icon: '📊' },
  { id: 'analytics', label: '学情', icon: '📈' },
  { id: 'errors', label: '错题', icon: '📝' },
  { id: 'graph', label: '图谱', icon: '🧠' },
  { id: 'calendar', label: '日历', icon: '📅' },
  { id: 'achievements', label: '成就', icon: '🏆' },
  { id: 'plan', label: '计划', icon: '🎯' },
  { id: 'progress', label: '进度', icon: '📋' },
  { id: 'quality', label: '质量', icon: '🛡️' },
  { id: 'stats', label: '统计', icon: '📉' },
  { id: 'study', label: '自习', icon: '📖' },
];

// 仪表盘外壳组件属性接口
interface DashboardShellProps {
  children: ReactNode;
  activeTab: TabId;
}

// 仪表盘外壳组件 —— 提供顶部 Tab 导航栏和内容区域的布局
export default function DashboardShell({ children, activeTab }: DashboardShellProps) {
  const router = useRouter();

  // 切换标签页 —— 更新 URL 查询参数并导航到对应仪表盘页面
  const switchTab = (tabId: TabId) => {
    const params = new URLSearchParams();
    if (tabId !== 'overview') params.set('tab', tabId);
    const qs = params.toString();
    router.push(`/dashboard${qs ? `?${qs}` : ''}`, { scroll: false });
  };

  return (
    // 全屏容器，使用 CSS 变量背景色
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Tab 导航栏 */}
      <div className="sticky top-0 z-30 bg-[var(--color-bg)] border-b border-[var(--color-border)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          {/* 水平滚动标签列表 */}
          <div className="flex items-center gap-0 overflow-x-auto scrollbar-hide">
            {TABS.map((tab) => {
              const isActive = tab.id === activeTab;
              return (
                // 每个标签按钮 —— 点击切换对应页面
                <button
                  key={tab.id}
                  onClick={() => switchTab(tab.id)}
                  className={`
                    relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium whitespace-nowrap
                    transition-colors cursor-pointer select-none
                    ${isActive
                      ? 'text-[var(--color-accent)]'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                    }
                  `}
                >
                  <span className="text-base">{tab.icon}</span>
                  <span className="hidden sm:inline">{tab.label}</span>
                  {/* 当前激活标签的底部指示条 */}
                  {isActive && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-[var(--color-accent)] rounded-full active:scale-[0.97] transition-transform" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tab 内容区域 */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {children}
      </div>
    </div>
  );
}

// 导出标签页配置和类型，供外部使用
export { TABS, type TabId };
