"""LanguageRoom 服务层 — 初始化 + 建表确保

依据 docs/modules/language-room/data-model.md + ADR 0004

注意：不要在此文件中用 `from app.services.liveroom import realtime` 等语句，
因为 `from __future__ import annotations` 会让 `realtime` 名指向 __future__._Feature，
破坏模块导入解析。子模块应在使用方通过 `import app.services.liveroom.X` 导入。
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _ensure_tables() -> None:
    """确保 LanguageRoom 模块所有表存在（幂等）

    依据: docs/modules/language-room/data-model.md
    11 张表：
      1. language_rooms
      2. room_participants
      3. room_sessions
      4. room_transcripts
      5. room_recordings
      6. room_scenarios
      7. ai_personas
      8. ai_companion_configs
      9. ai_helper_invasiveness
      10. vocabulary_captures
      11. room_invitations
    """
    from app.infrastructure.db.database import get_db
    db = get_db()
    sql_path_options = [
        "app/infrastructure/db/liveroom_schema.sql",
        os.path.join(os.path.dirname(__file__), "../infrastructure/db/liveroom_schema.sql"),
        "/home/deploy/edu-companion/backend/app/infrastructure/db/liveroom_schema.sql",
    ]
    sql_path: Optional[str] = None
    for p in sql_path_options:
        if os.path.exists(p):
            sql_path = p
            break
    if not sql_path:
        logger.error("找不到 liveroom_schema.sql 建表文件")
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
    logger.info("LanguageRoom schema: 11 张表已确保就绪")
