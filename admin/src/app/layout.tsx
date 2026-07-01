import "./globals.css";
import { Topbar } from "@/lib/Topbar";

export const metadata = {
  title: "Edu Companion Admin",
  description: "管理后台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="bg-page text-ink-primary font-sans antialiased">
        <Topbar />
        <main className="px-6 py-5 max-w-[1440px] mx-auto">{children}</main>
      </body>
    </html>
  );
}
