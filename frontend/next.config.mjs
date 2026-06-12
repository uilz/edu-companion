/** @type {import('next').NextConfig} */

// 从 config/.env 加载环境变量（不用 dotenv 包，避免额外依赖）
import { readFileSync, existsSync } from 'fs';
import { resolve } from 'path';

const envPath = resolve(import.meta.dirname || process.cwd(), 'config', '.env');
if (existsSync(envPath)) {
  const content = readFileSync(envPath, 'utf-8');
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim();
    if (key && !process.env[key]) {
      process.env[key] = val;
    }
  }
}

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
      // 直接访问 :3000 时，API 请求代理到统一网关 :8080
      //（通过 :8080 访问时 Nginx 会处理，不会命中这些 rewrite）
      { source: '/api/auth/:path*', destination: 'http://127.0.0.1:8080/api/auth/:path*' },
      { source: '/api/conversations/ws', destination: 'http://127.0.0.1:8080/api/conversations/ws' },
      { source: '/api/:path*', destination: 'http://127.0.0.1:8080/api/:path*' },
      { source: '/avatars/:path*', destination: 'http://127.0.0.1:8080/avatars/:path*' },
    ];
  },
};

export default nextConfig;
