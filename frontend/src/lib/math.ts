/**
 * Math rendering helpers.
 * KaTeX is code-split: math formulas show as plain text until loaded (~200ms),
 * then re-render with proper typesetting.
 */

// ── Lazy-load KaTeX ──
type KatexDefault = typeof import('katex').default;
let _katex: KatexDefault | null = null;
let _katexReady = false;

// Fire-and-forget: load katex in background
import('katex').then((m) => {
  _katex = m.default;
  _katexReady = true;
});

// ── Placeholders ──
const M_PLACEHOLDER = '%%MATH%%';
const C_PLACEHOLDER = '%%CODE%%';

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
      // Fall through to plain-text fallback
    }
  }
  // Plain-text fallback (before KaTeX loads or on error)
  const escaped = formula
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  if (displayMode) {
    return `<div class="katex-loading">$$${escaped}$$</div>`;
  }
  return `<span class="katex-loading">$${escaped}$</span>`;
}

/**
 * Process markdown + LaTeX in text.
 *
 * Pipeline:
 * 1. Extract & protect code blocks
 * 2. Extract & protect LaTeX math
 * 3. HTML-escape remaining text
 * 4. Apply markdown formatting (bold, paragraphs)
 * 5. Restore & render math via KaTeX
 * 6. Restore code blocks
 */
export function renderMarkdown(text: string): string {
  const codeBlocks: string[] = [];
  const mathBlocks: string[] = [];

  let html = text;

  // ── Step 1: Protect code blocks ──
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const escaped = code
      .trim()
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    codeBlocks.push(
      `<pre><code class="language-${lang}">${escaped}</code></pre>`
    );
    return `${C_PLACEHOLDER}${codeBlocks.length - 1}%%`;
  });
  html = html.replace(/`([^`]+)`/g, (_, code) => {
    const escaped = code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    codeBlocks.push(`<code>${escaped}</code>`);
    return `${C_PLACEHOLDER}${codeBlocks.length - 1}%%`;
  });

  // ── Step 2: Protect math ──
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}%%`;
  });
  html = html.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}%%`;
  });

  // ── Step 3: HTML escape ──
  html = html
    .replace(/&(?!(?:amp|lt|gt|#\d+|#x[\da-f]+);)/gi, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // ── Step 4: Markdown ──
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html
    .split('\n\n')
    .map((p) => `<p>${p.replace(/\n/g, '<br/>')}</p>`)
    .join('');

  // ── Step 5: Restore math → KaTeX ──
  html = html.replace(
    new RegExp(`${M_PLACEHOLDER}(\\d+)%%`, 'g'),
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

  // ── Step 6: Restore code blocks ──
  html = html.replace(
    new RegExp(`${C_PLACEHOLDER}(\\d+)%%`, 'g'),
    (_, idx) => codeBlocks[parseInt(idx)] || ''
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
 * Check if KaTeX has loaded. Callers can use this to trigger re-renders.
 */
export function isKatexReady(): boolean {
  return _katexReady;
}

/**
 * Subscribe to KaTeX load event. Returns unsubscribe function.
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
