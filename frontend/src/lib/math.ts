import katex from "katex";

// ── Math rendering helpers ──
// Strategy: protect code blocks → protect math → process markdown → restore math → restore code

const M_PLACEHOLDER = "%%MATH%%";
const C_PLACEHOLDER = "%%CODE%%";

/**
 * Render LaTeX via KaTeX. Returns HTML or falls back to escaped code.
 */
function renderFormula(formula: string, displayMode: boolean): string {
  try {
    return katex.renderToString(formula.trim(), {
      displayMode,
      throwOnError: false,
      strict: false,
      trust: true,
    });
  } catch {
    // Fallback: show raw formula as code
    const escaped = formula
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return displayMode
      ? `<pre><code>${escaped}</code></pre>`
      : `<code>${escaped}</code>`;
  }
}

/**
 * Process markdown + LaTeX in text.
 *
 * Pipeline:
 * 1. Extract & protect code blocks (```...``` and `...`)
 * 2. Extract & protect LaTeX math ($$...$$ and $...$)
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
  // Multi-line ```...```
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const escaped = code
      .trim()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    codeBlocks.push(
      `<pre><code class="language-${lang}">${escaped}</code></pre>`
    );
    return `${C_PLACEHOLDER}${codeBlocks.length - 1}%%`;
  });
  // Inline `...`
  html = html.replace(/`([^`]+)`/g, (_, code) => {
    const escaped = code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    codeBlocks.push(`<code>${escaped}</code>`);
    return `${C_PLACEHOLDER}${codeBlocks.length - 1}%%`;
  });

  // ── Step 2: Protect math ──
  // Display math: $$...$$ (multi-line supported)
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}%%`;
  });
  // Inline math: $...$ (single line, not empty, no consecutive $$)
  // Must avoid matching inside URLs or plain dollar amounts
  html = html.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (match) => {
    mathBlocks.push(match);
    return `${M_PLACEHOLDER}${mathBlocks.length - 1}%%`;
  });

  // ── Step 3: HTML escape (now only non-code, non-math text) ──
  html = html
    .replace(/&(?!(?:amp|lt|gt|#\d+|#x[\da-f]+);)/gi, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // ── Step 4: Markdown ──
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Paragraphs (split on double newline)
  html = html
    .split("\n\n")
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");

  // ── Step 5: Restore math → KaTeX ──
  html = html.replace(
    new RegExp(`${M_PLACEHOLDER}(\\d+)%%`, "g"),
    (_, idx) => {
      const formula = mathBlocks[parseInt(idx)];
      if (!formula) return "";
      const isDisplay = formula.startsWith("$$");
      return renderFormula(
        formula.replace(/^\$\$|\$\$$/g, "").replace(/^\$|\$$/g, ""),
        isDisplay
      );
    }
  );

  // ── Step 6: Restore code blocks ──
  html = html.replace(
    new RegExp(`${C_PLACEHOLDER}(\\d+)%%`, "g"),
    (_, idx) => codeBlocks[parseInt(idx)] || ""
  );

  return html;
}

/**
 * Convenience: just render content with full pipeline.
 */
export function renderContent(text: string): string {
  return renderMarkdown(text);
}

/**
 * Render ONLY LaTeX math (no markdown). For standalone math display.
 * Handles both $$...$$ and $...$.
 */
export function renderMath(text: string): string {
  let result = text;

  // Display math: $$ ... $$
  result = result.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) =>
    renderFormula(formula, true)
  );
  // Inline math: $ ... $
  result = result.replace(/(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)/g, (_, formula) =>
    renderFormula(formula, false)
  );

  return result;
}
