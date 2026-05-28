/**
 * 数学渲染工具函数
 * 使用 marked 渲染 Markdown，使用 KaTeX 渲染 LaTeX 数学公式
 */
import { marked } from 'marked';

// ── 懒加载 KaTeX（按需加载，避免阻塞首次渲染） ──
type KatexDefault = typeof import('katex').default;
let _katex: KatexDefault | null = null;
let _katexReady = false;

import('katex').then((m) => {
  _katex = m.default;
  _katexReady = true;
});

// ── 占位符，用于暂存提取的数学公式 ──
const M_PLACEHOLDER = '\x00MATH\x00';

/**
 * 渲染 LaTeX 公式。如果 KaTeX 尚未加载完成，则回退为纯文本显示
 */
function renderFormula(formula: string, displayMode: boolean): string {
  if (_katex) {
    try {
      return _katex.renderToString(formula.trim(), {
        displayMode,
        throwOnError: false,
        strict: false,
        trust: true,
      });
    } catch {
      // Fall through
    }
  }
  const escaped = formula
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  if (displayMode) {
    return `<div class="katex-loading">$$${escaped}$$</div>`;
  }
  return `<span class="katex-loading">$${escaped}$</span>`;
}

// ── 自定义 marked 渲染器，重写部分默认行为 ──
const renderer = new marked.Renderer();

// 重写代码块渲染：添加语言类名，便于语法高亮
renderer.code = function({ text, lang }: { text: string; lang?: string }): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  const langClass = lang ? ` class="language-${lang}"` : '';
  return `<pre><code${langClass}>${escaped}</code></pre>`;
};

// 重写行内代码渲染
renderer.codespan = function({ text }: { text: string }): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return `<code>${escaped}</code>`;
};

// 重写链接渲染：默认在新标签页中打开
renderer.link = function({ href, title, text }: { href: string; title?: string | null; text: string }): string {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
};

// 重写图片渲染：添加懒加载属性
renderer.image = function({ href, title, text }: { href: string; title?: string | null; text: string }): string {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<img src="${href}" alt="${text}"${titleAttr} loading="lazy" />`;
};

marked.setOptions({
  renderer,
  gfm: true,
  breaks: true,
});

/**
 * 处理文本中的 Markdown 与 LaTeX 内容
 *
 * 处理流程：
 * 1. 提取并保护 LaTeX 数学公式（替换为占位符）
 * 2. 通过 marked 渲染 Markdown
 * 3. 恢复占位符，使用 KaTeX 将 LaTeX 渲染为 HTML
 */
export function renderMarkdown(text: string): string {
  const mathBlocks: string[] = [];

  let html = text;

  // ── 步骤 1：提取并保护 LaTeX 公式（避免被 marked 错误处理） ──
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}`;
  });
  html = html.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}`;
  });

  // ── 步骤 2：渲染 Markdown ──
  html = marked.parse(html) as string;

  // ── 步骤 3：恢复占位符，用 KaTeX 渲染 LaTeX 公式 ──
  html = html.replace(
    new RegExp(`${M_PLACEHOLDER.replace(/\x00/g, '\\x00')}(\\d+)`, 'g'),
    (_, idx) => {
      const formula = mathBlocks[parseInt(idx)];
      if (!formula) return '';
      const isDisplay = formula.startsWith('$$');
      return renderFormula(
        formula.replace(/^\$\$|\$\$$/g, '').replace(/^\$|\$$/g, ''),
        isDisplay
      );
    }
  );

  return html;
}

/**
 * 便捷函数：对内容执行完整的 Markdown + LaTeX 渲染流程
 */
export function renderContent(text: string): string {
  return renderMarkdown(text);
}

/**
 * 仅渲染 LaTeX 数学公式（不处理 Markdown）
 */
export function renderMath(text: string): string {
  let result = text;
  result = result.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) =>
    renderFormula(formula, true)
  );
  result = result.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (_, formula) =>
    renderFormula(formula, false)
  );
  return result;
}

/**
 * 订阅 KaTeX 加载完成事件；若已加载则立即执行回调
 * 返回取消订阅函数
 */
export function onKatexReady(cb: () => void): () => void {
  if (_katexReady) {
    cb();
    return () => {};
  }
  const check = setInterval(() => {
    if (_katexReady) {
      clearInterval(check);
      cb();
    }
  }, 100);
  return () => clearInterval(check);
}
