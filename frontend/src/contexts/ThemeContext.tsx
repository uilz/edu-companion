'use client';
import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

// ── 类型定义 ──

/** 主题：亮色 / 暗色 */
type Theme = 'light' | 'dark';

/** 视觉风格 — 对应 design-language.md 的五套风格 */
export type DesignStyle = 'professional' | 'playful' | 'knowledge' | 'soft-data' | 'gamified';

/** 风格元数据 */
export interface StyleMeta {
  id: DesignStyle;
  label: string;
  labelEn: string;
  description: string;
}

/** 所有可用风格列表 */
export const STYLE_LIST: StyleMeta[] = [
  { id: 'professional', label: '现代专业风', labelEn: 'Professional', description: '高对比、低装饰、专业工具感' },
  { id: 'playful',      label: '活力趣味风', labelEn: 'Playful',      description: '明亮色彩、大圆角、友好亲和' },
  { id: 'knowledge',    label: '紧凑知识风', labelEn: 'Knowledge',    description: '高信息密度、阅读友好、沉浸感' },
  { id: 'soft-data',    label: '柔和数据风', labelEn: 'Soft Data',    description: '温和视觉、数据可视化、减少认知负荷' },
  { id: 'gamified',     label: '游戏化激励风', labelEn: 'Gamified',  description: '成就驱动、强反馈、高能量' },
];

/** 主题上下文的类型 */
interface ThemeContextType {
  theme: Theme;
  style: DesignStyle;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  setStyle: (s: DesignStyle) => void;
  currentStyleMeta: StyleMeta;
}

// ── 常量 ──

const STORAGE_THEME_KEY = 'edu-companion-theme';
const STORAGE_STYLE_KEY = 'edu-companion-style';
const DEFAULT_THEME: Theme = 'dark';
const DEFAULT_STYLE: DesignStyle = 'professional';

// ── Context ──

const ThemeContext = createContext<ThemeContextType>({
  theme: DEFAULT_THEME,
  style: DEFAULT_STYLE,
  toggleTheme: () => {},
  setTheme: () => {},
  setStyle: () => {},
  currentStyleMeta: STYLE_LIST[0],
});

// ── Provider ──

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [style, setStyleState] = useState<DesignStyle>(DEFAULT_STYLE);
  const [mounted, setMounted] = useState(false);

  // 初始化：从 localStorage 恢复设置并应用到 document
  useEffect(() => {
    const savedTheme = localStorage.getItem(STORAGE_THEME_KEY) as Theme | null;
    const savedStyle = localStorage.getItem(STORAGE_STYLE_KEY) as DesignStyle | null;
    const initialTheme = savedTheme || DEFAULT_THEME;
    const initialStyle = savedStyle || DEFAULT_STYLE;

    setThemeState(initialTheme);
    setStyleState(initialStyle);

    const root = document.documentElement;
    root.setAttribute('data-theme', initialTheme);
    root.setAttribute('data-style', initialStyle);

    setMounted(true);
  }, []);

  // 设置主题并持久化
  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_THEME_KEY, t);
    document.documentElement.setAttribute('data-theme', t);
  }, []);

  // 切换主题
  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  }, [theme, setTheme]);

  // 设置风格并持久化
  const setStyle = useCallback((s: DesignStyle) => {
    setStyleState(s);
    localStorage.setItem(STORAGE_STYLE_KEY, s);
    document.documentElement.setAttribute('data-style', s);
  }, []);

  // 当前风格元数据
  const currentStyleMeta = STYLE_LIST.find(s => s.id === style) || STYLE_LIST[0];

  // 防止 SSR 闪烁：挂载前直接渲染子组件
  if (!mounted) return <>{children}</>;

  return (
    <ThemeContext.Provider value={{ theme, style, toggleTheme, setTheme, setStyle, currentStyleMeta }}>
      {children}
    </ThemeContext.Provider>
  );
}

/** 访问主题上下文的 Hook */
export const useTheme = () => useContext(ThemeContext);
