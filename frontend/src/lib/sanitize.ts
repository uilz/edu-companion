/* eslint-disable @typescript-eslint/no-require-imports */
// DOMPurify uses CommonJS exports — need require-style import
// eslint-disable-next-line @typescript-eslint/no-var-requires
const createDOMPurify = require("dompurify");

/**
 * Sanitize HTML to prevent XSS attacks.
 * Allows safe tags/attributes while stripping dangerous ones.
 */
export function sanitizeHtml(html: string): string {
  // Server-side: return as-is (DOMPurify needs browser DOM)
  if (typeof window === "undefined") return html;
  const DOMPurify = createDOMPurify(window);
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "p", "br", "strong", "em", "u", "s", "code", "pre", "blockquote",
      "h1", "h2", "h3", "h4", "h5", "h6",
      "ul", "ol", "li",
      "a", "img", "span", "div",
      "table", "thead", "tbody", "tr", "th", "td",
      "hr", "sup", "sub", "mark",
      // KaTeX elements
      "math", "semantics", "mrow", "mi", "mo", "mn", "msup", "msub",
      "mfrac", "msqrt", "mroot", "mstyle", "mtext", "mpadded",
      "annotation",
    ],
    ALLOWED_ATTR: [
      "href", "src", "alt", "class", "style",
      "target", "rel", "title", "width", "height",
      "colSpan", "rowSpan",
      // KaTeX attributes
      "mathvariant", "stretchy", "accent",
    ],
    ALLOW_DATA_ATTR: false,
  });
}
