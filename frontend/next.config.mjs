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
      // 旧对话/图谱 → 学习空间
      { source: '/chat', destination: '/learn', permanent: true },
      { source: '/graph', destination: '/learn?panel=graph', permanent: true },
    ];
  },
  async rewrites() {
    return [
      // WebSocket 代理到后端
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
