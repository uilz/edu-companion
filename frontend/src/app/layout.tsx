// 导入 Next.js 类型：Metadata（页面元数据）和 Viewport（视口配置）
import type { Metadata, Viewport } from 'next';
// 导入全局样式
import './globals.css';
// 导入应用外壳布局组件（导航栏/侧边栏等）
import AppShell from '@/components/layout/AppShell';
// 导入客户端 Providers 包裹组件（主题、状态管理等）
import ClientProviders from '@/components/layout/ClientProviders';

// 页面元数据配置：标题、描述、图标等（用于 SEO 和浏览器标签页展示）
export const metadata: Metadata = {
  title: '苹果果 - 个人知识体系',
  description: 'AI驱动的个人知识体系构建工具，助力自主学习',
  icons: {
    icon: '/favicon.ico',
  },
};

// 视口与页面缩放配置（移动端适配、主题色等）
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  themeColor: '#fbfaf7',
};

// 根布局组件 —— 包裹所有页面，提供全局 HTML 结构与 Providers
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // lang="zh-CN" 标明页面语言为简体中文
    // suppressHydrationWarning 避免服务端/客户端不一致时的 React 警告
    <html lang="zh-CN" suppressHydrationWarning>
      {/* antialiased 使字体渲染更平滑 */}
      <body className="antialiased">
        {/* ClientProviders 包裹 AppShell，确保客户端状态（主题/认证等）在渲染前可用 */}
        <ClientProviders>
          {/* AppShell 提供全局导航栏/侧边栏布局，内部渲染当前页面内容 */}
          <AppShell>{children}</AppShell>
        </ClientProviders>
      </body>
    </html>
  );
}
