"""Test script for LearningActivityEventHandler.

发布一个 SessionCompleted 事件，然后查询 learning_activities 表验证记录已写入。

用法：
    cd /home/deploy/edu-companion
    python3 scripts/test/task0110/test_learning_activity_handler.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 将 backend 加入路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "backend"))

from shared.events import SessionCompleted
from app.application.di import container
from app.api.learning_activity import service


async def main() -> None:
    bus = container.event_bus
    user_id = "u_f65eb04e5c6b"  # apple 测试用户

    event = SessionCompleted(
        user_id=user_id,
        session_id="test_session_001",
        session_type="practice",
        total_questions=10,
        correct_count=8,
        accuracy=0.8,
        duration_minutes=15.0,
    )

    print(f"Publishing {event.event_type} for user={user_id}")
    await bus.publish(event)

    # 等待事件处理完成
    await asyncio.sleep(0.5)

    # 查询活动流
    result = service.list_activities(user_id, limit=10)
    print(f"Found {result['total']} activities:")
    for item in result["items"]:
        print(f"  - [{item['module']}] {item['title']}: {item['description']}")
        print(f"    deep_link={item['deep_link']}")

    if result["total"] == 0:
        print("ERROR: no activity recorded")
        sys.exit(1)

    print("OK: activity recorded successfully")


if __name__ == "__main__":
    asyncio.run(main())
