/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // output: "standalone",  // 临时注释，用 next start 正常启动
  async redirects() {
    return [
      // 首页 → 驾驶舱
      { source: '/', destination: '/dashboard', permanent: true },
      // 旧独立路由 → 统一统计页
      { source: '/stats', destination: '/analytics?tab=stats', permanent: true },
      { source: '/progress', destination: '/analytics?tab=stats', permanent: true },
      { source: '/calendar', destination: '/analytics?tab=calendar', permanent: true },
      { source: '/achievements', destination: '/analytics?tab=achievements', permanent: true },
      // 旧对话 → 学习空间
      { source: '/chat', destination: '/learn', permanent: true },
      // 旧图谱页 → 知识树独立页面
      { source: '/graph', destination: '/knowledge-tree', permanent: true },
      { source: '/learn/graph', destination: '/knowledge-tree', permanent: true },
    ];
  },
  async rewrites() {
    return [
      // WebSocket 对话代理（走认证网关统一入口，由网关转发到后端）
      {
        source: "/api/conversations/ws",
        destination: "http://127.0.0.1:18001/api/conversations/ws",
      },
      // WebSocket 其他代理（走认证网关统一入口）
      {
        source: "/ws/:path*",
        destination: "http://127.0.0.1:18001/ws/:path*",
      },
      // REST API 代理到认证网关（网关转发到主后端）
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:18001/api/:path*",
      },
      // 头像静态文件代理到认证网关
      {
        source: "/avatars/:path*",
        destination: "http://127.0.0.1:18001/avatars/:path*",
      },
    ];
  },
};

export default nextConfig;
