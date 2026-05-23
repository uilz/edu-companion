'use client';

// React Hooks 和 Next.js 路由依赖
import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
// 导航子组件：底部导航栏 & 侧边栏
import BottomNav from './BottomNav';
import Sidebar from './Sidebar';

// AppShell 组件的属性接口：接收子节点作为内容区
interface AppShellProps {
  children: React.ReactNode;
}

/**
 * 自定义 Hook：响应式媒体查询
 * 监听指定的 CSS 媒体查询条件，返回布尔值表示是否匹配
 */
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);

    // 监听媒体查询状态变化
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    media.addEventListener('change', listener);

    // 清理：移除事件监听器
    return () => media.removeEventListener('change', listener);
  }, [query]);

  return matches;
}

// 全屏路由列表：这些页面自己管理布局，不使用主外壳包裹
const FULLSCREEN_ROUTES = ['/learn'];

/**
 * AppShell — 应用外壳布局组件
 * 根据设备类型（桌面端 / 移动端）和当前路由，渲染不同的导航与布局结构：
 * - 桌面端：侧边栏 + 左侧偏移的主体内容
 * - 移动端：底部导航栏 + 底部偏移的主体内容
 * - 全屏路由：仅渲染子内容与移动端底部导航，无主体容器包裹
 */
export default function AppShell({ children }: AppShellProps) {
  // 判断是否为桌面端（视口宽度 >= 768px）
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const pathname = usePathname();
  // 判断当前路由是否为全屏模式
  const isFullscreen = FULLSCREEN_ROUTES.some((r) => pathname?.startsWith(r));

  // 全屏路由：直接渲染子内容，不加 main 容器包裹
  if (isFullscreen) {
    return (
      <>
        {!isDesktop && <BottomNav />}
        {children}
      </>
    );
  }

  // 默认布局：侧边栏 / 底部导航 + 主体内容区
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* 桌面端：侧边栏 */}
      {isDesktop && <Sidebar />}

      {/* 移动端：底部导航栏 */}
      {!isDesktop && <BottomNav />}

      {/* 主体内容区域 */}
      <main
        className="min-h-screen transition-all duration-200"
        style={{
          // 桌面端留出侧边栏宽度，移动端留出底部导航高度
          paddingLeft: isDesktop ? 'var(--sidebar-width)' : '0',
          paddingBottom: !isDesktop ? 'var(--bottom-nav-height)' : '0',
        }}
      >
        <div className="swiss-container">{children}</div>
      </main>
    </div>
  );
}
