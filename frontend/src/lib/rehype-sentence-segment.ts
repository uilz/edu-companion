/// <reference lib="es2022.intl" />
/**
 * rehype-sentence-segment — Rehype plugin that wraps sentences in <span data-sentence>.
 *
 * Uses Intl.Segmenter for locale-aware sentence boundary detection.
 * Preserves inline elements (strong, em, a, code, del, etc.) across sentence boundaries.
 * Protects code blocks, KaTeX formulas, and other inline-code elements from segmentation.
 */

import type { Root, Element, Text, Node as HastNode, Parent } from "hast";
import { CONTINUE, SKIP, visit } from "unist-util-visit";

interface Options {
  /** BCP 47 locale for Intl.Segmenter (default: 'zh-CN') */
  locale?: string;
}

const BLOCK_TAGS = new Set([
  "p", "li", "h1", "h2", "h3", "h4", "h5", "h6",
  "td", "th", "blockquote", "dd", "dt",
]);

function isBlockTag(tagName: string): boolean {
  return BLOCK_TAGS.has(tagName);
}

function isBlockElement(node: Element): boolean {
  if (isBlockTag(node.tagName)) return true;
  // Treat KaTeX display math as block-level
  if (Array.isArray(node.properties?.className)) {
    const cls = node.properties.className as string[];
    if (cls.includes("katex-display")) return true;
  }
  return false;
}

function hasBlockDescendant(node: HastNode): boolean {
  if (node.type !== "element") return false;
  const el = node as Element;
  if (isBlockTag(el.tagName) && el !== node) return true; // not self
  for (const child of el.children) {
    if (hasBlockDescendant(child)) return true;
  }
  return false;
}

function isProtected(node: Element): boolean {
  // KaTeX formulas
  if (Array.isArray(node.properties?.className)) {
    const cls = node.properties.className as string[];
    if (cls.some((c: string) => c.includes("katex") || c.includes("math"))) return true;
  }
  // Code blocks and inline code
  if (node.tagName === "pre" || node.tagName === "code") return true;
  // Script / style (shouldn't be in the tree but safety)
  if (node.tagName === "script" || node.tagName === "style") return true;
  return false;
}

// ── Text extraction ──

interface TextSegment {
  node: Text | Element; // text node, or protected element
  text: string; // plain text, or "" for protected elements
}

function collectSegments(children: HastNode[]): TextSegment[] {
  const segs: TextSegment[] = [];
  for (const child of children) {
    if (child.type === "text") {
      segs.push({ node: child as Text, text: (child as Text).value });
    } else if (child.type === "element") {
      const el = child as Element;
      if (isProtected(el)) {
        segs.push({ node: el, text: "" }); // protected → empty placeholder
      } else {
        // recurse into non-protected inline elements
        segs.push(...collectSegments(el.children));
      }
    }
  }
  return segs;
}

// ── Slice children by character offsets ──

interface SliceState {
  /** Current character offset */
  offset: number;
}

function sliceChildren(
  children: HastNode[],
  start: number,
  end: number,
  state: SliceState
): HastNode[] {
  const result: HastNode[] = [];

  for (const child of children) {
    if (child.type === "text") {
      const val = (child as Text).value;
      const childStart = state.offset;
      const childEnd = state.offset + val.length;
      state.offset = childEnd;

      if (childEnd <= start || childStart >= end) continue; // outside range

      const s = Math.max(0, start - childStart);
      const e = Math.min(val.length, end - childStart);
      result.push({ type: "text", value: val.slice(s, e) } as Text);
    } else if (child.type === "element") {
      const el = child as Element;
      if (isProtected(el)) {
        // Protected element: keep whole if it overlaps the range
        if (state.offset < end) {
          result.push({ ...el, children: [...el.children] } as Element);
        }
        // Protected elements don't contribute to text offset
      } else {
        // Recurse into inline elements
        const sliced = sliceChildren(el.children, start, end, state);
        if (sliced.length > 0) {
          result.push({ ...el, children: sliced } as Element);
        }
      }
    }
  }

  return result;
}

// ── Main plugin ──

export default function rehypeSentenceSegment(options: Options = {}) {
  const locale = options.locale ?? "zh-CN";
  const segmenter = new Intl.Segmenter(locale, { granularity: "sentence" });

  return (tree: Root) => {
    visit(tree, "element", (node: Element, index: number | undefined, parent: Parent | undefined) => {
      if (!isBlockElement(node)) return CONTINUE;
      if (!parent) return CONTINUE;

      // Only process innermost blocks (children don't contain block elements)
      if (hasBlockDescendant(node)) return CONTINUE;
      // Skip empty blocks
      if (node.children.length === 0) return CONTINUE;

      const segments = collectSegments(node.children);
      const fullText = segments.map((s) => s.text).join("");

      // All content is protected (e.g., display math) → wrap entire block in data-sentence
      if (fullText.trim().length === 0) {
        const single: Element = {
          type: "element",
          tagName: "span",
          properties: { dataSentence: true },
          children: node.children as Element["children"],
        };
        (node as any).children = [single];
        return SKIP;
      }

      // Use Intl.Segmenter to find sentence boundaries
      const sentenceBounds: Array<{ start: number; end: number }> = [];
      for (const seg of Array.from(segmenter.segment(fullText))) {
        sentenceBounds.push({ start: seg.index, end: seg.index + seg.segment.length });
      }

      // Merge only overlapping segments (not adjacent ones)
      const merged: Array<{ start: number; end: number }> = [];
      for (const b of sentenceBounds) {
        const last = merged[merged.length - 1];
        if (last && b.start < last.end) {
          last.end = Math.max(last.end, b.end); // merge overlapping
        } else {
          merged.push({ ...b });
        }
      }

      // Deduplicate: if after merging we still have duplicates, take the max range
      // This handles the case where Segmenter produces overlapping spans

      if (merged.length <= 1) {
        // Even a single sentence needs data-sentence wrapping so complex
        // elements (KaTeX, code, etc.) inside the block can be found by
        // click handler via closest('[data-sentence]').
        const single: Element = {
          type: "element",
          tagName: "span",
          properties: { dataSentence: true },
          children: node.children as Element["children"],
        };
        (node as any).children = [single];
        return SKIP;
      }

      // Slice children into sentence groups
      const newChildren: HastNode[] = [];

      for (const b of merged) {
        const state: SliceState = { offset: 0 };
        const sliced = sliceChildren(node.children, b.start, b.end, state);
        if (sliced.length === 0) continue;

        const span: Element = {
          type: "element",
          tagName: "span",
          properties: { dataSentence: true },
          children: sliced as Element["children"],
        };
        newChildren.push(span);
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (node as any).children = newChildren;

      return SKIP; // don't recurse into children (we replaced them)
    });
  };
}
