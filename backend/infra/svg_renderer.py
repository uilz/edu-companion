"""
SVG 配图渲染器 — 实现 ImageRenderer Protocol (Phase 5)

支持三种渲染方式:
1. LaTeX 公式 → SVG（matplotlib mathtext）
2. 概念关系图 → SVG（matplotlib + 手工布局）
3. Mermaid 图 → 生成源码（前端客户端渲染）
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("infra.svg")

CACHE_DIR = Path(os.path.expanduser("~/.companion/images"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

STATIC_PREFIX = "/api/multimodal/images"

# Matplotlib 后端（无 GUI）
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class SVGRenderer:
    """SVG 渲染器 — LaTeX 公式 + 概念图"""

    def __init__(self, cache_dir: Path | None = None):
        self._cache = cache_dir or CACHE_DIR
        self._cache.mkdir(parents=True, exist_ok=True)

    async def render_latex(
        self,
        formula: str,
        skill_id: str = "",
    ) -> dict:
        """LaTeX 公式 → SVG"""
        cache_key = hashlib.sha256(
            f"latex:{formula}".encode()
        ).hexdigest()[:16]
        cache_file = self._cache / f"latex_{cache_key}.svg"

        if cache_file.exists():
            logger.debug("LaTeX cache hit: %s", cache_key)
            return {
                "url": f"{STATIC_PREFIX}/{cache_file.name}",
                "format": "svg",
                "cache_hit": True,
            }

        # 渲染
        await asyncio.to_thread(_render_latex_sync, formula, str(cache_file))

        logger.info("LaTeX rendered: %s → %s", cache_key, cache_file.name)
        return {
            "url": f"{STATIC_PREFIX}/{cache_file.name}",
            "format": "svg",
            "cache_hit": False,
        }

    async def render_diagram(
        self,
        description: str,
        diagram_type: str = "concept",
        skill_id: str = "",
    ) -> dict:
        """概念/流程图 → SVG"""
        cache_key = hashlib.sha256(
            f"diagram:{diagram_type}:{description}".encode()
        ).hexdigest()[:16]
        cache_file = self._cache / f"diagram_{cache_key}.svg"

        if cache_file.exists():
            logger.debug("Diagram cache hit: %s", cache_key)
            return {
                "url": f"{STATIC_PREFIX}/{cache_file.name}",
                "format": "svg",
                "cache_hit": True,
            }

        if diagram_type == "concept":
            await asyncio.to_thread(
                _render_concept_sync, description, str(cache_file)
            )
        elif diagram_type in ("flow", "comparison"):
            await asyncio.to_thread(
                _render_flow_sync, description, diagram_type, str(cache_file)
            )
        else:
            # fallback: 纯文本 SVG
            await asyncio.to_thread(
                _render_text_sync, description, str(cache_file)
            )

        logger.info("Diagram rendered: %s → %s", cache_key, cache_file.name)
        return {
            "url": f"{STATIC_PREFIX}/{cache_file.name}",
            "format": "svg",
            "cache_hit": False,
        }

    async def render_for_knowledge(
        self,
        skill_id: str,
        skill_name: str,
        content: str,
    ) -> dict | None:
        """
        为知识点自动选择合适的配图方式。

        检测规则:
        - 含 $...$ 或 $$...$$ → LaTeX 渲染
        - 含"对比"/"区别"/"分类" → 概念图
        - 含"步骤"/"流程"/"过程" → 流程图
        - 其他 → None (跳过)
        """
        # 数学公式检测
        if re.search(r"\$.*?\$|\$\$.*?\$\$", content):
            # 提取第一个公式
            match = re.search(r"\$([^$]+)\$", content)
            if match:
                return await self.render_latex(match.group(1), skill_id)

        # 对比/分类检测
        if re.search(r"对比|区别|分类|vs|和.*不同", content):
            return await self.render_diagram(content, "comparison", skill_id)

        # 流程检测
        if re.search(r"步骤|流程|过程|阶段|首先.*然后", content):
            return await self.render_diagram(content, "flow", skill_id)

        # 通用概念图
        if len(content) > 50:
            return await self.render_diagram(content, "concept", skill_id)

        return None


# ── 同步渲染函数（在线程中执行，避免阻塞事件循环） ──


def _render_latex_sync(formula: str, output_path: str) -> None:
    """matplotlib mathtext → SVG"""
    fig, ax = plt.subplots(figsize=(6, 2))
    ax.axis("off")
    ax.text(0.5, 0.5, f"${formula}$", fontsize=18,
            ha="center", va="center", transform=ax.transAxes)
    fig.savefig(output_path, format="svg", bbox_inches="tight",
                pad_inches=0.2, transparent=True)
    plt.close(fig)


def _render_concept_sync(description: str, output_path: str) -> None:
    """概念关系图 — 中心节点 + 子节点环绕（简单放射布局）"""
    import math

    # 从描述中提取关键词（简单逗号/换行分割）
    parts = re.split(r"[，,\n]+", description)
    parts = [p.strip() for p in parts if p.strip()][:8]
    if not parts:
        parts = ["概念"]

    center = parts[0]
    satellites = parts[1:] if len(parts) > 1 else ["要点1", "要点2", "要点3"]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.axis("off")
    ax.set_xlim(-3, 3)
    ax.set_ylim(-3, 3)

    # 中心节点
    circle = plt.Circle((0, 0), 0.6, color="#4A90D9", alpha=0.9, ec="white", lw=2)
    ax.add_patch(circle)
    ax.text(0, 0, center[:8], ha="center", va="center",
            fontsize=12, fontweight="bold", color="white")

    # 卫星节点
    n = len(satellites)
    for i, sat in enumerate(satellites):
        angle = 2 * math.pi * i / n - math.pi / 2
        r = 2.0
        x, y = r * math.cos(angle), r * math.sin(angle)

        # 连线
        ax.plot([0, x], [0, y], color="#999", lw=1, alpha=0.5)

        # 节点
        circle = plt.Circle((x, y), 0.4, color="#E8F0FE", ec="#4A90D9", lw=1.5)
        ax.add_patch(circle)
        ax.text(x, y, sat[:10], ha="center", va="center",
                fontsize=9, color="#333")

    fig.savefig(output_path, format="svg", bbox_inches="tight",
                pad_inches=0.3, transparent=True)
    plt.close(fig)


def _render_flow_sync(description: str, diagram_type: str, output_path: str) -> None:
    """流程图/对比图"""
    parts = re.split(r"[，,\n]+", description)
    parts = [p.strip() for p in parts if p.strip()][:6]
    if not parts:
        parts = ["步骤"]

    if diagram_type == "comparison" and len(parts) >= 2:
        # 两列对比
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.axis("off")
        ax.set_xlim(0, 7)
        ax.set_ylim(0, 3)

        left_items = re.split(r"[；;]", parts[0])[:3]
        right_items = re.split(r"[；;]", parts[-1])[:3]

        # 标题
        ax.text(1.5, 2.5, left_items[0][:10] if left_items else "A",
                ha="center", fontsize=13, fontweight="bold", color="#4A90D9")
        ax.text(5.5, 2.5, right_items[0][:10] if right_items else "B",
                ha="center", fontsize=13, fontweight="bold", color="#E8753C")

        # 分隔线
        ax.axvline(3.5, color="#ccc", lw=1, linestyle="--")

        # 条目
        for i, (li, ri) in enumerate(zip(
            left_items[1:] + [""] * 3,
            right_items[1:] + [""] * 3
        )):
            y = 1.8 - i * 0.5
            if li:
                ax.text(1.5, y, f"• {li[:15]}", fontsize=10, color="#333")
            if ri:
                ax.text(5.5, y, f"• {ri[:15]}", fontsize=10, color="#333")
    else:
        # 竖向流程
        n = len(parts)
        fig, ax = plt.subplots(figsize=(5, n * 0.8 + 1))
        ax.axis("off")
        ax.set_xlim(0, 5)
        ax.set_ylim(-0.5, n + 0.5)

        for i, part in enumerate(parts):
            y = n - i - 0.5
            # 节点
            rect = plt.Rectangle((1, y - 0.3), 3, 0.6,
                                 facecolor="#E8F0FE", edgecolor="#4A90D9",
                                 lw=1.5, alpha=0.9)
            ax.add_patch(rect)
            ax.text(2.5, y, f"{i+1}. {part[:20]}", ha="center", va="center",
                    fontsize=11, color="#333")
            # 箭头
            if i < n - 1:
                ax.annotate("", xy=(2.5, y - 0.35), xytext=(2.5, y - 0.65),
                            arrowprops=dict(arrowstyle="->", color="#999", lw=1))

    fig.savefig(output_path, format="svg", bbox_inches="tight",
                pad_inches=0.3, transparent=True)
    plt.close(fig)


def _render_text_sync(text: str, output_path: str) -> None:
    """纯文本降级渲染"""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.axis("off")
    # 分行
    lines = text[:200].split("。")
    canvas = "\n".join(f"• {line.strip()}" for line in lines if line.strip())
    ax.text(0.5, 0.5, canvas, fontsize=12, ha="center", va="center",
            transform=ax.transAxes, family="monospace")
    fig.savefig(output_path, format="svg", bbox_inches="tight",
                pad_inches=0.3, transparent=True)
    plt.close(fig)
