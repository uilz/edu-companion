// 标记为客户端组件，可以使用 React 钩子和浏览器 API
'use client';

// 导入 Next.js 的 Link 组件用于客户端导航
import Link from 'next/link';
// 导入自定义的空状态组件，用于展示占位内容
import EmptyState from '@/components/ui/EmptyState';
// 集中导航配置 — 统一 404 跳链
import { HOME_PATH } from '@/lib/navConfig';

/**
 * 自定义 404 页面组件
 * 当用户访问不存在的路由时，Next.js 会自动渲染此页面
 */
export default function NotFound() {
  return (
    // 使用 EmptyState 组件展示友好的 404 提示信息
    <EmptyState
      icon="🔍"                                    // 页面图标
      title="页面未找到"                            // 主标题
      description="你访问的页面不存在或已被移除"       // 副标题说明
      action={
        // 提供返回首页的导航按钮 — 统一跳 HOME_PATH (/) 而非 /dashboard
        // 理由：HOME_PATH 是登录后落点、所有 Logo 点击的汇聚点、无需鉴权即可访问
        <Link
          href={HOME_PATH}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover active:scale-[0.97] transition-colors inline-block"
        >
          返回首页
        </Link>
      }
    />
  );
}
