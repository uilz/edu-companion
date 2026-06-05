/**
 * 数学渲染工具函数
 * 保留 renderMarkdown / renderMath / onKatexReady 供 InlinePracticeBlock 使用。
 */

import { marked } from 'marked';

// ── 懒加载 KaTeX ──
type KatexDefault = typeof import('katex').default;
let _katex: KatexDefault | null = null;
let _katexReady = false;

import('katex').then((m) => {
  _katex = m.default;
  _katexReady = true;
});

// ── KaTeX 渲染 ──
function renderFormula(formula: string, displayMode: boolean): string {
  if (_katex) {
    try {
      return _katex.renderToString(formula.trim(), {
        displayMode,
        throwOnError: false,
        strict: false,
        trust: true,
      });
    } catch { /* fall through */ }
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

// ── marked 配置 ──
const renderer = new marked.Renderer();
renderer.code = function ({ text, lang }: { text: string; lang?: string }): string {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const langClass = lang ? ` class="language-${lang}"` : '';
  return `<pre><code${langClass}>${escaped}</code></pre>`;
};
renderer.codespan = function ({ text }: { text: string }): string {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return `<code>${escaped}</code>`;
};
renderer.link = function ({ href, title, text }: { href: string; title?: string | null; text: string }): string {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
};
renderer.image = function ({ href, title, text }: { href: string; title?: string | null; text: string }): string {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<img src="${href}" alt="${text}"${titleAttr} loading="lazy" />`;
};
marked.setOptions({ renderer, gfm: true, breaks: true });

// ── 公式占位符 ──
const M_PLACEHOLDER = '\x00MATH\x00';

/** 渲染 Markdown + LaTeX → HTML 字符串（供 InlinePracticeBlock 等服务端场景使用） */
export function renderMarkdown(text: string): string {
  const mathBlocks: string[] = [];
  let html = text;

  // 1. 提取并保护 LaTeX
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_match: string) => {
    mathBlocks.push(_match);
    return M_PLACEHOLDER;
  });

  // 2. marked 渲染 Markdown
  html = marked.parse(html) as string;

  // 3. 恢复占位符，KaTeX 渲染
  html = html.replace(new RegExp(M_PLACEHOLDER.replace(/\x00/g, '\\x00'), 'g'), () => {
    const m = mathBlocks.shift() || '';
    const formula = m.replace(/^\$\$/, '').replace(/\$\$$/, '');
    return renderFormula(formula, true);
  });

  return html;
}

/** 仅渲染 LaTeX 公式（不处理 Markdown） */
export function renderMath(text: string): string {
  return text.replace(/\$\$([\s\S]*?)\$\$/g, (_: string, f: string) => renderFormula(f, true));
}

/** KaTeX 加载完成回调 */
export function onKatexReady(cb: () => void): () => void {
  if (_katexReady) { cb(); return () => {}; }
  const check = setInterval(() => {
    if (_katexReady) { clearInterval(check); cb(); }
  }, 100);
  return () => clearInterval(check);
}
