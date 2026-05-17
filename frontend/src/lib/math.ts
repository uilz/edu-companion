import katex from "katex";

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
      return formula;
    }
  });
  // Inline math: $ ... $  (avoid matching $$ and newlines)
  result = result.replace(/\$([^\$\n]+?)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: false,
        throwOnError: false,
      });
    } catch {
      return formula;
    }
  });
  return result;
}

/**
 * Simple markdown to HTML (bold, code, line breaks).
 */
export function renderMarkdown(text: string): string {
  let html = text;
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
  });
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html
    .split("\n\n")
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");
  return html;
}
