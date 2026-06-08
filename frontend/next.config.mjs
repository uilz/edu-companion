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
      // WebSocket 对话代理（显式静态路径，比动态 rewrite 更可靠处理 WS upgrade）
      {
        source: "/api/conversations/ws",
        destination: "http://127.0.0.1:8000/api/conversations/ws",
      },
      // WebSocket 其他代理
      {
        source: "/ws/:path*",
        destination: "http://127.0.0.1:8000/ws/:path*",
      },
      // REST API 代理到后端
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
