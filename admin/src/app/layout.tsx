import "./globals.css";
import { Topbar } from "@/lib/Topbar";
import { ThemeProvider } from "@/lib/theme";

export const metadata = {
  title: "Edu Companion Admin",
  description: "管理后台",
};

// 在 hydration 前根据 localStorage 设置 data-theme，避免闪烁
const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('admin-theme');
    if (!t) t = 'light';
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="bg-page text-ink-primary font-sans antialiased">
        <ThemeProvider>
          <Topbar />
          <main className="px-6 py-5 max-w-[1440px] mx-auto">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
