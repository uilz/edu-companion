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
  serifFont: boolean;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
  setStyle: (s: DesignStyle) => void;
  setSerifFont: (v: boolean) => void;
  currentStyleMeta: StyleMeta;
}

// ── 常量 ──

const STORAGE_THEME_KEY = 'edu-companion-theme';
const STORAGE_STYLE_KEY = 'edu-companion-style';
const DEFAULT_THEME: Theme = 'light';
const DEFAULT_STYLE: DesignStyle = 'professional';

// ── Context ──

const ThemeContext = createContext<ThemeContextType>({
  theme: DEFAULT_THEME,
  style: DEFAULT_STYLE,
  serifFont: false,
  toggleTheme: () => {},
  setTheme: () => {},
  setStyle: () => {},
  setSerifFont: () => {},
  currentStyleMeta: STYLE_LIST[0],
});

// ── Provider ──

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(DEFAULT_THEME);
  const [style, setStyleState] = useState<DesignStyle>(DEFAULT_STYLE);
  const [serifFont, setSerifFontState] = useState(false);
  const [mounted, setMounted] = useState(false);

  // 初始化：先 localStorage 缓存（同 tab 立即生效）, 再从服务端拉取（跨设备一致）
  useEffect(() => {
    if (typeof window === 'undefined') return;
    // 1. 立即从 localStorage 恢复（防闪烁）
    const cachedTheme = localStorage.getItem(STORAGE_THEME_KEY) as Theme | null;
    const cachedStyle = localStorage.getItem(STORAGE_STYLE_KEY) as DesignStyle | null;
    const cachedSerif = localStorage.getItem('edu-companion-serif-font');
    const initialTheme = cachedTheme || DEFAULT_THEME;
    const initialStyle = cachedStyle || DEFAULT_STYLE;
    setThemeState(initialTheme);
    setStyleState(initialStyle);
    if (cachedSerif === 'true') {
      setSerifFontState(true);
    }
    const root = document.documentElement;
    root.setAttribute('data-theme', initialTheme);
    root.setAttribute('data-style', initialStyle);
    root.setAttribute('data-serif-font', cachedSerif === 'true' ? 'true' : 'false');
    setMounted(true);

    // 2. Task #84: B4 修复 — 从服务端拉取最新值（跨设备一致）
    (async () => {
      try {
        const token = localStorage.getItem('access_token');
        if (!token) return; // 未登录, 用 localStorage 即可
        const res = await fetch('/api/settings/ui', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!data) return;
        if (data.theme && (data.theme === 'dark' || data.theme === 'light')
            && data.theme !== initialTheme) {
          setThemeState(data.theme);
          localStorage.setItem(STORAGE_THEME_KEY, data.theme);
          root.setAttribute('data-theme', data.theme);
        }
        if (data.style && STYLE_LIST.find(s => s.id === data.style)
            && data.style !== initialStyle) {
          setStyleState(data.style);
          localStorage.setItem(STORAGE_STYLE_KEY, data.style);
          root.setAttribute('data-style', data.style);
        }
        if (typeof data.serif_font === 'boolean') {
          setSerifFontState(data.serif_font);
          localStorage.setItem('edu-companion-serif-font', String(data.serif_font));
          root.setAttribute('data-serif-font', String(data.serif_font));
        }
      } catch { /* 静默 — 用 localStorage 即可 */ }
    })();
  }, []);

  // 同步到服务端 (Task #84: B4 修复)
  const persistUi = useCallback(async (patch: { theme?: Theme; style?: DesignStyle; serif_font?: boolean }) => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('access_token');
    if (!token) return; // 未登录, 仅 localStorage
    try {
      await fetch('/api/settings/ui', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(patch),
      });
    } catch (e) {
      console.warn('[theme] 同步服务端失败:', e);
    }
  }, []);

  // 设置主题并持久化（localStorage 立即生效 + 服务端异步）
  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    try { localStorage.setItem(STORAGE_THEME_KEY, t); } catch { /* */ }
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', t);
    }
    persistUi({ theme: t });
  }, [persistUi]);

  // 切换主题
  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  }, [theme, setTheme]);

  // 设置风格并持久化
  const setStyle = useCallback((s: DesignStyle) => {
    setStyleState(s);
    try { localStorage.setItem(STORAGE_STYLE_KEY, s); } catch { /* */ }
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-style', s);
    }
    persistUi({ style: s });
  }, [persistUi]);

  // 设置衬线字体偏好
  const setSerifFont = useCallback((v: boolean) => {
    setSerifFontState(v);
    try { localStorage.setItem('edu-companion-serif-font', String(v)); } catch { /* */ }
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-serif-font', String(v));
    }
    persistUi({ serif_font: v });
  }, [persistUi]);

  // 当前风格元数据
  const currentStyleMeta = STYLE_LIST.find(s => s.id === style) || STYLE_LIST[0];

  // 防止 SSR 闪烁：挂载前直接渲染子组件
  if (!mounted) return <>{children}</>;

  return (
    <ThemeContext.Provider value={{ theme, style, serifFont, toggleTheme, setTheme, setStyle, setSerifFont, currentStyleMeta }}>
      {children}
    </ThemeContext.Provider>
  );
}

/** 访问主题上下文的 Hook */
export const useTheme = () => useContext(ThemeContext);
