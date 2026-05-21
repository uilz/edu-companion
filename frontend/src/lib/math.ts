/**
 * Math rendering helpers.
 * Uses marked for markdown + KaTeX for LaTeX math.
 */
import { marked } from 'marked';

// ── Lazy-load KaTeX ──
type KatexDefault = typeof import('katex').default;
let _katex: KatexDefault | null = null;
let _katexReady = false;

import('katex').then((m) => {
  _katex = m.default;
  _katexReady = true;
});

// ── Placeholders ──
const M_PLACEHOLDER = '\x00MATH\x00';

/**
 * Render LaTeX formula. Falls back to plain text if KaTeX not loaded yet.
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

// ── Custom marked renderer ──
const renderer = new marked.Renderer();

// Override code block to add language class
renderer.code = function({ text, lang }: { text: string; lang?: string }): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  const langClass = lang ? ` class="language-${lang}"` : '';
  return `<pre><code${langClass}>${escaped}</code></pre>`;
};

// inline code
renderer.codespan = function({ text }: { text: string }): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return `<code>${escaped}</code>`;
};

// Override link to open in new tab
renderer.link = function({ href, title, text }: { href: string; title?: string | null; text: string }): string {
  const titleAttr = title ? ` title="${title}"` : '';
  return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
};

// Override image
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
 * Process markdown + LaTeX in text.
 *
 * Pipeline:
 * 1. Extract & protect LaTeX math
 * 2. Render markdown via marked
 * 3. Restore & render math via KaTeX
 */
export function renderMarkdown(text: string): string {
  const mathBlocks: string[] = [];

  let html = text;

  // ── Step 1: Protect math ──
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}`;
  });
  html = html.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}`;
  });

  // ── Step 2: Render markdown ──
  html = marked.parse(html) as string;

  // ── Step 3: Restore math → KaTeX ──
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
 * Convenience: render content with full pipeline.
 */
export function renderContent(text: string): string {
  return renderMarkdown(text);
}

/**
 * Render ONLY LaTeX math (no markdown).
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
 * Check if KaTeX has loaded.
 */
export function isKatexReady(): boolean {
  return _katexReady;
}

/**
 * Subscribe to KaTeX load event.
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
