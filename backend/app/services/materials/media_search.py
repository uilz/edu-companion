"""
多平台媒体搜索服务

不调用外部API——生成搜索链接 + AI推荐搜索词。
用户点击新窗口打开，零法律风险。
"""
from __future__ import annotations

import logging
import urllib.parse
from typing import Optional

from app.services.llm.llm_service import llm_service

logger = logging.getLogger(__name__)

# 平台搜索URL模板
PLATFORMS = {
    "bilibili": {
        "name": "B站",
        "icon": "🎬",
        "search_url": "https://search.bilibili.com/all?keyword={query}",
        "description": "国内最大的学习视频平台",
        "tags": ["教学", "课程", "讲解"],
    },
    "youtube": {
        "name": "YouTube",
        "icon": "▶️",
        "search_url": "https://www.youtube.com/results?search_query={query}",
        "description": "全球视频平台，英文内容丰富",
        "tags": ["tutorial", "lecture", "explained"],
    },
    "zhihu": {
        "name": "知乎",
        "icon": "💬",
        "search_url": "https://www.zhihu.com/search?type=content&q={query}",
        "description": "高质量问答和深度解析",
        "tags": ["如何理解", "详解", "总结"],
    },
    "baidu_wenku": {
        "name": "百度文库",
        "icon": "📄",
        "search_url": "https://wenku.baidu.com/search?word={query}",
        "description": "课件、习题、笔记文档",
        "tags": ["课件", "习题", "笔记"],
    },
    "xuexi_qiangguo": {
        "name": "学习强国",
        "icon": "🇨🇳",
        "search_url": "https://www.xuexi.cn/search.html?q={query}",
        "description": "官方学习资源",
        "tags": ["课程", "理论"],
    },
    "cnki": {
        "name": "知网",
        "icon": "📖",
        "search_url": "https://kns.cnki.net/kns8/defaultresult/index?kwd={query}",
        "description": "学术论文和期刊",
        "tags": ["论文", "研究"],
    },
    "douyin": {
        "name": "抖音",
        "icon": "🎵",
        "search_url": "https://www.douyin.com/search/{query}",
        "description": "短视频知识科普",
        "tags": ["科普", "速成"],
    },
    "xiaohongshu": {
        "name": "小红书",
        "icon": "📕",
        "search_url": "https://www.xiaohongshu.com/search_result?keyword={query}",
        "description": "学习笔记、经验分享",
        "tags": ["笔记", "经验", "攻略"],
    },
    "bing": {
        "name": "Bing",
        "icon": "🔍",
        "search_url": "https://www.bing.com/search?q={query}",
        "description": "全球搜索引擎，中英文通用",
        "tags": ["综合", "中英文"],
    },
    "baidu": {
        "name": "百度",
        "icon": "🌐",
        "search_url": "https://www.baidu.com/s?wd={query}",
        "description": "国内通用搜索",
        "tags": ["综合", "中文"],
    },
}

# AI搜索词生成的系统提示
KEYWORD_PROMPT = """你是学习搜索助手。根据学生的问题，生成3-5个针对不同平台的精简搜索关键词。

## 规则
1. 每个平台的关键词要有针对性：
   - B站: 加上"讲解/入门/速成"等教学类后缀
   - YouTube: 用英文关键词
   - 知乎: 加上"如何理解/详解"
   - 百度文库: 加上"课件/习题/知识点总结"
2. 关键词要精简（2-5个词），不要长句
3. 中文关键词不要超过8个字

## 学生问题
{question}

## 输出格式 (JSON)
{{
  "bilibili": ["关键词1", "关键词2", "关键词3"],
  "youtube": ["keyword1", "keyword2"],
  "zhihu": ["关键词1", "关键词2"],
  "baidu_wenku": ["关键词1"],
  "primary_query": "主搜索词"
}}
"""


class MediaSearchService:
    """
    多平台媒体搜索服务
    
    核心: 生成搜索链接 + AI优化搜索词，用户自己搜。
    不调用外部API —— 零法律风险，零限流。
    """

    def __init__(self):
        self.platforms = PLATFORMS

    async def search(
        self,
        query: str,
        platforms: Optional[list[str]] = None,
        limit: int = 4,
    ) -> list[dict]:
        """
        为给定查询生成多平台搜索链接
        
        参数:
            query: 用户问题或知识点
            platforms: 限定平台列表 (如 ["bilibili", "zhihu"])
            limit: 每平台最多返回几条
        
        返回:
            list of platform results: {
                "platform": str,
                "name": str,
                "icon": str,
                "links": [{"query": str, "url": str}, ...]
            }
        """
        # Step 1: 用 AI 生成各平台搜索词
        keywords_map = await self._generate_keywords(query)

        # Step 2: 构建搜索链接
        results = []
        target_platforms = platforms or list(self.platforms.keys())

        for pid in target_platforms[:limit]:
            if pid not in self.platforms:
                continue

            platform = self.platforms[pid]
            queries = keywords_map.get(pid, [keywords_map.get("primary_query", query)])

            links = []
            for q in queries[:3]:  # 每平台最多3条
                encoded = urllib.parse.quote(q)
                url = platform["search_url"].format(query=encoded)
                links.append({"query": q, "url": url})

            if links:
                results.append({
                    "platform": pid,
                    "name": platform["name"],
                    "icon": platform["icon"],
                    "description": platform["description"],
                    "links": links,
                })

        return results

    async def recommend_for_error(
        self,
        error_skill: str,
        error_type: str = "",
        count: int = 3,
    ) -> list[dict]:
        """
        针对错题推荐搜索关键词
        
        根据错误类型优化搜索词:
        - 概念错误 → "XXX 概念讲解"
        - 计算错误 → "XXX 解题技巧"
        - 程序错误 → "XXX 详细步骤"
        """
        # 根据错误类型调整搜索词
        suffix_map = {
            "conceptual": "概念讲解 通俗",
            "computation": "解题技巧 易错",
            "procedural": "详细步骤 例题",
            "reading": "审题技巧",
            "transfer": "应用举例",
        }
        suffix = suffix_map.get(error_type, "入门讲解")

        query = f"{error_skill} {suffix}"
        return await self.search(query, platforms=["bilibili", "zhihu", "youtube"], limit=3)

    async def _generate_keywords(self, query: str) -> dict:
        """用LLM生成各平台优化后的搜索关键词"""
        try:
            prompt = KEYWORD_PROMPT.format(question=query)
            response = llm_service.chat(
                system_prompt="你是学习搜索关键词优化助手。只输出JSON。",
                user_prompt=prompt,
            )

            # 解析 JSON
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            logger.warning(f"AI关键词生成失败: {e}")

        # Fallback: 直接用原始query
        return {"primary_query": query, "bilibili": [query]}


# 全局实例
media_search = MediaSearchService()
