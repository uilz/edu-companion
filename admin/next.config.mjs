/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  productionBrowserSourceMaps: false,
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    useLightningcss: false,
  },
  async rewrites() {
    return [
      // 把前端 /api/admin/* 反向代理到 8001 后端
      { source: "/api/admin/:path*", destination: "http://127.0.0.1:8001/api/admin/:path*" },
      // 把前端 /api/auth/* 反向代理到 Nginx 网关 (:8080)
      { source: "/api/auth/:path*", destination: "http://127.0.0.1:8080/api/auth/:path*" },
    ];
  },
};

export default nextConfig;
