import "./globals.css";
import { Topbar } from "@/lib/Topbar";

export const metadata = {
  title: "Edu Companion Admin",
  description: "管理后台 — 用户/数据/监控/分析",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <Topbar />
        <main className="main">{children}</main>
      </body>
    </html>
  );
}
