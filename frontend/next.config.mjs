/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
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
