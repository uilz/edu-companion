"""Planning 模块初始化 + 建表确保"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _ensure_tables() -> None:
    """确保 Planning 模块所有表存在（幂等）"""
    from app.infrastructure.db.database import get_db
    db = get_db()
    sql_path_options = [
        "app/infrastructure/db/planning_schema.sql",
        os.path.join(os.path.dirname(__file__), "../infrastructure/db/planning_schema.sql"),
        "/home/deploy/edu-companion/backend/app/infrastructure/db/planning_schema.sql",
    ]
    sql_path: Optional[str] = None
    for p in sql_path_options:
        if os.path.exists(p):
            sql_path = p
            break
    if not sql_path:
        logger.error("找不到 planning_schema.sql 建表文件")
        return
    with open(sql_path) as f:
        sql = f.read()
    for statement in sql.split(";"):
        s = statement.strip()
        if not s:
            continue
        try:
            db.execute(s)
        except Exception as e:
            logger.warning("建表异常: %s", e)


# 便捷导入（放在底部避免循环导入）
from app.services.planning.items import (
    complete_plan_item,
    create_plan_item,
    delete_plan_item,
    extend_plan_item,
    find_plan_item_by_request_id,
    get_plan_item,
    list_plan_items,
    list_plan_items_by_node_ids,
    skip_plan_item,
    start_plan_item,
    update_plan_item,
)
from app.services.planning.goals import create_goal, get_goal, list_goals, update_goal
from app.services.planning.reviews import generate_review, list_reviews
from app.services.planning.layouts import create_view_layout, list_view_layouts
from app.services.planning.confirmations import (
    accept_confirmation,
    count_pending_confirmations,
    create_confirmation,
    dismiss_confirmation,
    find_confirmation_by_request_id,
    find_confirmation_by_suggestion_id,
    get_confirmation,
    list_confirmations,
)
from app.services.planning.views import (
    build_daily_view,
    build_knowledge_view,
    build_weekly_view,
)
from app.services.planning.aggregators import consume_status_bar

__all__ = [
    "_ensure_tables",
    # items
    "list_plan_items",
    "list_plan_items_by_node_ids",
    "get_plan_item",
    "create_plan_item",
    "find_plan_item_by_request_id",
    "update_plan_item",
    "start_plan_item",
    "skip_plan_item",
    "extend_plan_item",
    "complete_plan_item",
    "delete_plan_item",
    # goals
    "list_goals",
    "create_goal",
    "get_goal",
    "update_goal",
    # reviews
    "list_reviews",
    "generate_review",
    # layouts
    "list_view_layouts",
    "create_view_layout",
    # confirmations
    "find_confirmation_by_request_id",
    "find_confirmation_by_suggestion_id",
    "count_pending_confirmations",
    "create_confirmation",
    "list_confirmations",
    "get_confirmation",
    "accept_confirmation",
    "dismiss_confirmation",
    # views
    "build_daily_view",
    "build_weekly_view",
    "build_knowledge_view",
    "consume_status_bar",
]
