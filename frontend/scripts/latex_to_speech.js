#!/usr/bin/env node
/**
 * LaTeX → 中文口语化文本
 *
 * temml (LaTeX→MathML) + 自定义 MathML→中文口语递归转换
 * 完全绕过 speech-rule-engine 英文输出。
 *
 * 用法: node latex_to_speech.js 'x^2 + y^2'
 *       echo 'x^2 + y^2' | node latex_to_speech.js
 */
const temml = require("temml");

// ── 简易 XML → JSON 解析 ──
function parseMathML(xmlStr) {
  const stack = [{ tag: "root", children: [], text: "" }];
  const tagRe = /<(\/?)(\w+)([^>]*)>/g;
  let lastIdx = 0;
  let m;

  while ((m = tagRe.exec(xmlStr)) !== null) {
    if (m.index > lastIdx) {
      const text = xmlStr.slice(lastIdx, m.index);
      if (text.trim()) stack[stack.length - 1].text += text;
    }
    const close = m[1] === "/";
    const tagName = m[2];
    if (close) {
      const node = stack.pop();
      if (stack.length > 0) stack[stack.length - 1].children.push(node);
    } else {
      const selfClose = m[3].trim().endsWith("/");
      const node = { tag: tagName, children: [], text: "" };
      if (!selfClose) { stack.push(node); }
      else { stack[stack.length - 1].children.push(node); }
    }
    lastIdx = tagRe.lastIndex;
  }

  if (lastIdx < xmlStr.length) {
    const text = xmlStr.slice(lastIdx);
    const closeRe = /<\/(\w+)>/g;
    let cm;
    while ((cm = closeRe.exec(text)) !== null) {
      if (stack.length > 0) {
        const n = stack.pop();
        if (stack.length > 0) stack[stack.length - 1].children.push(n);
      }
    }
  }

  function findMath(nodes) {
    for (const n of nodes) {
      if (n.tag === "math") return n;
      if (n.children) { const f = findMath(n.children); if (f) return f; }
    }
    return null;
  }
  return findMath(stack[0].children) || stack[0];
}

// ── 希腊字母映射（键用实际 Unicode 字符）──
const GREEK_UNICODE = {
  "\u03B1": "阿尔法", "\u03B2": "贝塔", "\u03B3": "伽马",
  "\u03B4": "德尔塔", "\u03B5": "伊普西龙", "\u03B6": "泽塔",
  "\u03B7": "伊塔", "\u03B8": "西塔", "\u03B9": "约塔",
  "\u03BA": "卡帕", "\u03BB": "兰布达", "\u03BC": "缪",
  "\u03BD": "纽", "\u03BE": "克西", "\u03BF": "奥密克龙",
  "\u03C0": "派", "\u03C1": "柔", "\u03C3": "西格马",
  "\u03C4": "套", "\u03C5": "宇普西龙", "\u03C6": "斐",
  "\u03C7": "恺", "\u03C8": "普赛", "\u03C9": "欧米伽",
  // 大写
  "\u0393": "大写伽马", "\u0394": "大写德尔塔",
  "\u0398": "大写西塔", "\u039B": "大写兰布达",
  "\u039E": "大写克西", "\u03A0": "大写派",
  "\u03A3": "大写西格马", "\u03A6": "大写斐",
  "\u03A8": "大写普赛", "\u03A9": "大写欧米伽",
};

// ── 运算符口语 ──
const OP_CN = {
  "+": "加",
  "\u2212": "减",   // U+2212 减号（负号上下文后面处理）
  "\u00D7": "乘以", // U+00D7
  "\u00F7": "除以", // U+00F7
  "=": "等于",
  "\u2260": "不等于",
  "\u2248": "约等于",
  "<": "小于", ">": "大于",
  "\u2264": "小于等于", "\u2265": "大于等于",
  "\u00B1": "正负",
  "\u2208": "属于", "\u2209": "不属于",
  "\u2282": "包含于", "\u2283": "包含",
  "\u2229": "交", "\u222A": "并",
  "\u2205": "空集",
  "\u2192": "趋近于",
  "\u21D2": "推出", "\u21D4": "当且仅当",
  "\u2200": "对所有", "\u2203": "存在",
  "\u2211": "求和", "\u220F": "求积",
  "\u222B": "积分", "\u222E": "环路积分",
  "\u2202": "偏导", "\u2207": "梯度",
  "\u221E": "无穷大", "\u221A": "根号",
  "\u00B0": "度", "\u2032": "撇", "\u2033": "双撇",
  "\u2235": "因为", "\u2234": "所以",
  "\u22A5": "垂直于", "\u2225": "平行于",
  "\u2220": "角", "\u25B3": "三角形",
  "\u2227": "与", "\u2228": "或", "\u00AC": "非",
  "\u2295": "直和", "\u2297": "张量积",
  "/": "除以",
  "\u00D7": "乘",
};

// ── 函数名口语（小写）──
const FUNC_CN = {
  sin: "正弦", cos: "余弦", tan: "正切",
  cot: "余切", sec: "正割", csc: "余割",
  arcsin: "反正弦", arccos: "反余弦", arctan: "反正切",
  sinh: "双曲正弦", cosh: "双曲余弦", tanh: "双曲正切",
  log: "对数", ln: "自然对数", lg: "常用对数",
  exp: "指数", lim: "极限", det: "行列式",
  min: "最小值", max: "最大值",
  gcd: "最大公约数", lcm: "最小公倍数",
  mod: "模", Pr: "概率",
  arccot: "反余切", arcsec: "反正割", arccsc: "反余割",
};

// ── MathML → 中文口语 ──
function mathmlToSpeech(node, parentCtx) {
  if (!node) return "";
  const tag = node.tag || "";
  const text = node.text || "";
  const children = node.children || [];
  const ctx = parentCtx || {};

  switch (tag) {
    case "root":
    case "math": {
      // 预处理：合并相邻或连续的 mi 节点（如 "alpha" 拼写）
      const merged = mergeAdjacentMi(children);
      return merged.map(c => mathmlToSpeech(c, ctx)).join("");
    }

    case "mrow": {
      const merged = mergeAdjacentMi(children);
      return merged.map(c => mathmlToSpeech(c, ctx)).join("");
    }

    case "mi": {
      const t = text.trim().normalize();
      if (!t) return "";
      // 单个 Unicode 希腊字母
      if (GREEK_UNICODE[t]) return GREEK_UNICODE[t];
      // 特殊符号（无穷大等）
      if (OP_CN[t]) return OP_CN[t];
      // 多字符文本（如 temml 拼写的 "alpha"）
      const lower = t.toLowerCase();
      if (FUNC_CN[lower]) return FUNC_CN[lower];
      if (GREEK_UNICODE[t]) return GREEK_UNICODE[t];
      if (t.match(/^[A-Z]$/)) return `大写${t}`;
      return t;
    }

    case "mn":
      return text.trim() || "";

    case "mo": {
      const t = text.trim();
      if (!t) return "";
      // 过滤函数应用字符 U+2061
      if (t === "\u2061") return "";
      // 括号直接透出（或跳过）
      if (t === "(" || t === "[" || t === "{") return "";
      if (t === ")" || t === "]" || t === "}") return "";
      if (t === "|") return "";
      if (t === ",") return "逗号";
      if (t === ";") return "分号";
      if (t === ":") return "比";
      if (t === "!") return "的阶乘";
      // Unicode 减号在开头或前面是运算符时读"负"
      if (t === "\u2212") {
        // 在表达式开头或前面是左括号时，读"负"
        if (!parentCtx || parentCtx.isFirst) return "负";
        return "减";
      }
      if (OP_CN[t]) return OP_CN[t];
      if (/[\u4e00-\u9fff]/.test(t)) return t;
      return t;
    }

    case "msup": {
      const base = children[0] ? mathmlToSpeech(children[0], {}) : "";
      const expNode = children[1];
      if (!expNode) return base;
      const expText = expNode.text ? expNode.text.trim() : "";
      const isDigit = expNode.tag === "mn" && /^\d+$/.test(expText);
      const expInner = mathmlToSpeech(expNode, { isFirst: expNode.tag === "mrow" || expNode.tag === "mn" || expNode.tag === "msup" });

      // 函数判断（sin^2 x）
      const baseText = children[0] && children[0].tag === "mi"
        ? (children[0].text || "").trim().toLowerCase() : "";
      const baseIsFunc = FUNC_CN[baseText] !== undefined;

      if (isDigit) {
        const n = parseInt(expText);
        if (n === 2) return baseIsFunc ? `${base}平方` : `${base}的平方`;
        if (n === 3) return baseIsFunc ? `${base}立方` : `${base}的立方`;
        return baseIsFunc ? `${base}${n}次方` : `${base}的${n}次方`;
      }
      // 复杂上标：如果 expInner 已含"平方"/"立方"，不加重复"次方"
      const suffix = /(平方|立方|次方)$/.test(expInner) ? "" : "次方";
      return baseIsFunc
        ? `${base}${expInner}${suffix}`
        : `${base}的${expInner}${suffix}`;
    }

    case "msub": {
      const base = children[0] ? mathmlToSpeech(children[0], {}) : "";
      const sub = children[1] ? mathmlToSpeech(children[1], {}) : "";
      // lim 特殊处理
      const baseText = children[0] && children[0].tag === "mi"
        ? (children[0].text || "").trim().toLowerCase() : "";
      if (baseText === "lim") return `当${sub}时的极限`;
      return `${base}下标${sub}`;
    }

    case "msubsup": {
      const base = children[0] ? mathmlToSpeech(children[0], {}) : "";
      const sub = children[1] ? mathmlToSpeech(children[1], {}) : "";
      const sup = children[2] ? mathmlToSpeech(children[2], {}) : "";
      const baseMo = children[0]?.tag === "mo" ? (children[0].text || "").trim() : "";
      if (baseMo === "\u222B") return `从${sub}到${sup}的积分`;
      if (baseMo === "\u2211") return `从${sub}到${sup}的和`;
      if (baseMo === "\u220F") return `从${sub}到${sup}的积`;
      return `${base}下标${sub}上标${sup}`;
    }

    case "mfrac": {
      const numCtx = { isFirst: true };
      const denCtx = { isFirst: true };
      const num = children[0] ? mathmlToSpeech(children[0], numCtx) : "";
      const den = children[1] ? mathmlToSpeech(children[1], denCtx) : "";
      return `${den}分之${num}`;
    }

    case "msqrt": {
      const inner = children.map(c => mathmlToSpeech(c, {})).join("");
      return `根号${inner}`;
    }

    case "mroot": {
      const base = children[0] ? mathmlToSpeech(children[0], {}) : "";
      const n = children[1] ? mathmlToSpeech(children[1], {}) : "";
      return `${base}的${n}次方根`;
    }

    case "mover": {
      const base = children[0] ? mathmlToSpeech(children[0], {}) : "";
      const overChar = children[1]?.text?.trim() || "";
      // 向量箭头 \vec{v}
      if (overChar === "\u2192") return `向量${base}`;
      return base;
    }

    case "munder":
    case "munderover": {
      const base = children[0] ? mathmlToSpeech(children[0], {}) : "";
      const under = children[1] ? mathmlToSpeech(children[1], {}) : "";
      const over = children[2] ? mathmlToSpeech(children[2], {}) : "";
      const baseMo = children[0]?.tag === "mo" ? (children[0].text || "").trim() : "";
      // lim 特殊处理
      const baseText = children[0]?.tag === "mi" ? (children[0].text || "").trim().toLowerCase() : "";

      if (baseText === "lim") return `当${under}时的极限`;
      if (baseMo === "\u2211") return over ? `从${under}到${over}的和` : `求和${under}`;
      if (baseMo === "\u220F") return over ? `从${under}到${over}的积` : `从${under}的积`;
      if (baseMo === "\u222B") return over ? `从${under}到${over}的积分` : `从${under}的积分`;
      return `${base}下标${under}` + (over ? `上标${over}` : "");
    }

    case "mtext":
      return text.trim() || "";

    case "mspace":
      return "";

    case "mtable":
    case "mtr":
    case "mtd":
    case "mlabeledtr":
      return children.map(c => mathmlToSpeech(c, {})).join("逗号");

    default:
      return children.map(c => mathmlToSpeech(c, {})).join("");
  }
}

// 合并相邻或连续的 mi 节点（处理 temml 把 alpha 拆成 a/l/p/h/a 的情况）
function mergeAdjacentMi(nodes) {
  const result = [];
  let miBuffer = [];
  let miText = "";

  for (const n of nodes) {
    if (n.tag === "mi") {
      miBuffer.push(n);
      miText += (n.text || "").trim();
    } else {
      // flush 缓冲区
      if (miBuffer.length > 0) {
        result.push(mergeMiBuffer(miBuffer, miText));
        miBuffer = [];
        miText = "";
      }
      result.push(n);
    }
  }
  if (miBuffer.length > 0) {
    result.push(mergeMiBuffer(miBuffer, miText));
  }
  return result;
}

function mergeMiBuffer(buf, mergedText) {
  // 合并为单个 mi 节点
  return { tag: "mi", children: [], text: mergedText };
}

// ── 后处理 ──
function cleanSpeech(text) {
  let s = text;
  // 过滤不可见 Unicode
  s = s.replace(/[\u200B-\u200D\uFEFF\u2060-\u2064]/g, "");
  // 清理重复标点
  s = s.replace(/逗号逗号+/g, "逗号");
  s = s.replace(/的的/g, "的");
  s = s.replace(/下标下标/g, "下标");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

// ── 主转换 ──
async function convert(latex) {
  let s = latex.trim();
  s = s.replace(/^\$\$?|\$\$?$/g, "").trim();
  if (!s) return "";

  try {
    const mathmlStr = temml.renderToString(s, {
      displayMode: false,
      throwOnError: false,
    });
    if (mathmlStr && mathmlStr.includes("<math")) {
      const doc = parseMathML(mathmlStr);
      const speech = mathmlToSpeech(doc, { isFirst: true });
      const cleaned = cleanSpeech(speech);
      if (cleaned) return cleaned;
    }
  } catch (e) {
    // fallback
  }

  // Fallback
  return latexFallback(s);
}

// ── Fallback: simple LaTeX → Chinese ──
function latexFallback(s) {
  let r = s;
  const greekFallback = {
    "\\alpha": "阿尔法", "\\beta": "贝塔", "\\gamma": "伽马",
    "\\delta": "德尔塔", "\\epsilon": "伊普西龙", "\\zeta": "泽塔",
    "\\eta": "伊塔", "\\theta": "西塔", "\\iota": "约塔",
    "\\kappa": "卡帕", "\\lambda": "兰布达", "\\mu": "缪",
    "\\nu": "纽", "\\xi": "克西", "\\pi": "派",
    "\\rho": "柔", "\\sigma": "西格马", "\\tau": "套",
    "\\upsilon": "宇普西龙", "\\phi": "斐", "\\chi": "恺",
    "\\psi": "普赛", "\\omega": "欧米伽",
  };
  const cmdFallback = {
    "\\sin": "正弦", "\\cos": "余弦", "\\tan": "正切",
    "\\cot": "余切", "\\sec": "正割", "\\csc": "余割",
    "\\log": "对数", "\\ln": "自然对数", "\\lg": "常用对数",
    "\\lim": "极限", "\\sum": "求和", "\\int": "积分",
    "\\prod": "乘积", "\\partial": "偏导",
    "\\infty": "无穷大",
    "\\to": "趋近于", "\\rightarrow": "趋近于",
    "\\Rightarrow": "推出",
    "\\geq": "大于等于", "\\leq": "小于等于",
    "\\neq": "不等于", "\\approx": "约等于",
    "\\times": "乘以", "\\cdot": "点乘", "\\div": "除以",
    "\\colon": "比",
    "\\pm": "正负",
    "\\mp": "负正",
  };

  const allCmds = { ...greekFallback, ...cmdFallback };
  const keys = Object.keys(allCmds).sort((a, b) => b.length - a.length);
  for (const k of keys) r = r.replace(new RegExp(k.replace(/\\/g, "\\\\"), "g"), allCmds[k]);

  while (/\\frac\{([^{}]*)\}\{([^{}]*)\}/.test(r)) {
    r = r.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, (_, a, b) => `${b}分之${a}`);
  }

  const supStr = { "2": "平方", "3": "立方" };
  r = r.replace(/\^\{(\d+)\}/g, (_, p) => supStr[p] || `${p}次方`);
  r = r.replace(/\^(\w)/g, (_, p) => (supStr[p] || `${p}次方`));
  r = r.replace(/\^\{([^{}]+)\}/g, (_, p) => `${p}次方`);
  r = r.replace(/_\{([^{}]+)\}/g, (_, p) => `下标${p}`);
  r = r.replace(/_(\w)/g, (_, p) => `下标${p}`);
  r = r.replace(/[{}]/g, "");
  r = r.replace(/\s+/g, " ").trim();
  return r || s;
}

const input = process.argv[2] || "";
if (input) {
  convert(input).then(r => { console.log(r); process.exit(0); });
} else {
  let data = "";
  process.stdin.on("data", chunk => data += chunk);
  process.stdin.on("end", () => {
    convert(data).then(r => { console.log(r); process.exit(0); });
  });
}
