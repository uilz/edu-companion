'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// 主题类型：亮色模式或暗色模式
type Theme = 'light' | 'dark';

// 主题上下文的类型定义
interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

// 创建主题上下文，默认主题为暗色模式
const ThemeContext = createContext<ThemeContextType>({
  theme: 'dark',
  toggleTheme: () => {},
  setTheme: () => {},
});

// 主题提供者组件，包裹整个应用以提供主题能力
export function ThemeProvider({ children }: { children: ReactNode }) {
  // 主题状态和挂载状态
  const [theme, setThemeState] = useState<Theme>('dark');
  const [mounted, setMounted] = useState(false);

  // 初始化：从 localStorage 读取已保存的主题，并应用到 document
  useEffect(() => {
    const saved = localStorage.getItem('edu-companion-theme') as Theme | null;
    const initial = saved || 'dark';
    setThemeState(initial);
    document.documentElement.setAttribute('data-theme', initial);
    setMounted(true);
  }, []);

  // 设置主题：更新状态、保存到 localStorage 并应用到 HTML 根元素
  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem('edu-companion-theme', t);
    document.documentElement.setAttribute('data-theme', t);
  };

  // 切换主题：在亮色与暗色之间切换
  const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark');

  // 防止服务端渲染与客户端渲染不一致导致闪烁：挂载前渲染子组件但不包裹上下文
  if (!mounted) return <>{children}</>;

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// 自定义 Hook，便捷访问主题上下文
export const useTheme = () => useContext(ThemeContext);
