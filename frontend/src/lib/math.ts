import katex from "katex";

// ── Math rendering helpers ──

/** Math placeholder marker for markdown protection */
const MATH_PLACEHOLDER_PREFIX = "%%MATH%%";

/**
 * Render LaTeX math in text to HTML string.
 * Handles both display ($$...$$) and inline ($...$) math.
 */
export function renderMath(text: string): string {
  // Display math: $$ ... $$
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: true,
        throwOnError: false,
      });
    } catch {
      return `<code>${formula}</code>`;
    }
  });
  // Inline math: $ ... $  (avoid matching $$ and newlines)
  result = result.replace(/\$([^$\n]+?)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: false,
        throwOnError: false,
      });
    } catch {
      return `<code>${formula}</code>`;
    }
  });
  return result;
}

/**
 * Simple markdown to HTML (bold, code, line breaks).
 * Protects LaTeX math blocks during processing.
 */
export function renderMarkdown(text: string): string {
  let html = text;

  // Step 1: Protect math blocks from markdown processing
  const mathBlocks: string[] = [];
  html = html.replace(/\$\$[\s\S]+?\$\$/g, (match) => {
    mathBlocks.push(match);
    return `${MATH_PLACEHOLDER_PREFIX}${mathBlocks.length - 1}%%`;
  });
  html = html.replace(/\$[^$\n]+?\$/g, (match) => {
    mathBlocks.push(match);
    return `${MATH_PLACEHOLDER_PREFIX}${mathBlocks.length - 1}%%`;
  });

  // Step 2: HTML escape (only non-math text)
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Step 3: Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
  });
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Step 4: Bold
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Step 5: Paragraphs
  html = html
    .split("\n\n")
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");

  // Step 6: Restore math blocks and render them
  html = html.replace(
    new RegExp(`${MATH_PLACEHOLDER_PREFIX}(\\d+)%%`, "g"),
    (_, idx) => {
      const formula = mathBlocks[parseInt(idx)];
      if (!formula) return "";
      const isDisplay = formula.startsWith("$$");
      try {
        return katex.renderToString(
          formula.replace(/^\$\$|\$\$$/g, "").replace(/^\$|\$$/g, "").trim(),
          { displayMode: isDisplay, throwOnError: false }
        );
      } catch {
        return `<code>${formula}</code>`;
      }
    }
  );

  return html;
}

/**
 * Render text with full processing: markdown + math.
 * Preferred order: protect math → markdown → restore & render math.
 */
export function renderContent(text: string): string {
  return renderMarkdown(text);
}
