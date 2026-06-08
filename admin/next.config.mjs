/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      // 把前端 /api/admin/* 反向代理到 8001 后端
      { source: "/api/admin/:path*", destination: "http://127.0.0.1:8001/api/admin/:path*" },
    ];
  },
};

export default nextConfig;
