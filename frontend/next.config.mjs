/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async redirects() {
    return [
      // 旧首页 → 驾驶舱
      { source: '/', destination: '/dashboard', permanent: true },
      // 旧分析页 → 驾驶舱对应 Tab
      { source: '/analytics', destination: '/dashboard?tab=analytics', permanent: true },
      { source: '/stats', destination: '/dashboard?tab=analytics', permanent: true },
      { source: '/progress', destination: '/dashboard?tab=analytics', permanent: true },
      // 旧页面 → 驾驶舱对应 Tab
      { source: '/errors', destination: '/dashboard?tab=errors', permanent: true },
      { source: '/calendar', destination: '/dashboard?tab=calendar', permanent: true },
      { source: '/achievements', destination: '/dashboard?tab=achievements', permanent: true },
      { source: '/study', destination: '/dashboard?tab=plan', permanent: true },
      { source: '/quality', destination: '/dashboard?tab=quality', permanent: true },
      // 旧对话 → 学习空间
      { source: '/chat', destination: '/learn', permanent: true },
      // 图形图谱页 → 驾驶舱图谱 Tab
      { source: '/graph', destination: '/dashboard?tab=graph', permanent: true },
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
