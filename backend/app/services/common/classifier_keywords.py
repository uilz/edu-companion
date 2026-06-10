"""
关键词知识库 — 按 分区→领域→专题→会话 四级组织。

每个层级一个独立 JSON 文件，存放在 `config/` 目录下：

  - keyword_weights.json        → KEYWORD_WEIGHTS         （分区级）
  - domain_keywords.json        → DOMAIN_KEYWORDS         （领域级）
  - topic_keywords.json         → TOPIC_KEYWORDS          （专题级）
  - conversation_keywords.json  → CONVERSATION_KEYWORDS   （会话级）

环境变量 `CLASSIFIER_KEYWORDS_DIR` 可覆盖配置文件目录。

用法：
  from app.services.common.classifier_keywords import (
      KEYWORD_WEIGHTS, DOMAIN_KEYWORDS, TOPIC_KEYWORDS, CONVERSATION_KEYWORDS
  )
  reload_keywords()                 # 运行时热重载
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── 配置文件目录 ──
_DEFAULT_CONFIG_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "config",
    ),
)
_CONFIG_DIR = os.environ.get("CLASSIFIER_KEYWORDS_DIR", _DEFAULT_CONFIG_DIR)

# ── 每个层级一个独立文件 ──
_KEYWORD_FILES: dict[str, str] = {
    "KEYWORD_WEIGHTS": "keyword_weights.json",
    "DOMAIN_KEYWORDS": "domain_keywords.json",
    "TOPIC_KEYWORDS": "topic_keywords.json",
    "CONVERSATION_KEYWORDS": "conversation_keywords.json",
}

# ── 全局变量（模块外部通过 from ... import 引用） ──
KEYWORD_WEIGHTS: dict[str, dict[str, float]] = {}
DOMAIN_KEYWORDS: dict[str, dict[str, dict[str, float]]] = {}
TOPIC_KEYWORDS: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
CONVERSATION_KEYWORDS: dict[str, dict[str, dict[str, dict[str, float]]]] = {}


# ════════════════════════════════════════════
#  加载 & 热重载
# ════════════════════════════════════════════

def _load_single_json(file_path: str) -> dict | None:
    """加载单个 JSON 文件。不存在或出错返回 None。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        logger.warning("加载关键词文件失败: %s", file_path, exc_info=True)
        return None


def reload_keywords(config_dir: str | None = None) -> None:
    """运行时热重载所有层级的 JSON 文件。

    Args:
        config_dir: 配置文件目录，默认使用 ``CLASSIFIER_KEYWORDS_DIR`` 环境变量或
                    ``backend/config/``。
    """
    global KEYWORD_WEIGHTS, DOMAIN_KEYWORDS, TOPIC_KEYWORDS, CONVERSATION_KEYWORDS

    base = config_dir or _CONFIG_DIR
    loaded_count = 0

    for var_name, filename in _KEYWORD_FILES.items():
        file_path = os.path.join(base, filename)
        data = _load_single_json(file_path)
        if data is not None:
            globals()[var_name] = data
            loaded_count += 1
        else:
            globals()[var_name] = {}
            logger.info("关键词文件不存在，%s 置空: %s", var_name, file_path)

    logger.info(
        "关键词热重载完成: 成功加载 %d/4 个文件 (%s)",
        loaded_count, base,
    )


# 模块导入时自动加载
reload_keywords()
