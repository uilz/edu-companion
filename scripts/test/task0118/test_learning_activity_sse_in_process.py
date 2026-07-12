"""In-process test for LearningActivity SSE.

在同一个 Python 进程中同时建立 SSE 流和发布事件，验证实时推送。

用法：
    cd /home/deploy/edu-companion
    python3 scripts/test/task0110/test_learning_activity_sse_in_process.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "backend"))

from shared.events import SessionCompleted
from app.application.di import container
from app.application.handlers.learning_activity_event_bus import learning_activity_event_bus


async def collect_stream(user_id: str, duration: float = 5.0) -> list[str]:
    """收集 SSE 流事件一段时间。"""
    events: list[str] = []
    async for sse in learning_activity_event_bus.stream_events(user_id):
        events.append(sse)
        if len(events) >= 2 or (asyncio.get_event_loop().time() > duration):
            # 人为限制，实际测试会收到 connected + activity_created
            pass
        if len(events) >= 3:
            break
    return events


async def main() -> None:
    user_id = "u_f65eb04e5c6b"
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"

    # 确保 handler 已订阅
    from app.application.handlers.learning_activity_handler import learning_activity_event_handler
    learning_activity_event_handler.subscribe(container.event_bus)

    # 后台启动 SSE 收集
    stream_task = asyncio.create_task(collect_stream(user_id))
    await asyncio.sleep(0.5)  # 等待订阅建立

    event = SessionCompleted(
        user_id=user_id,
        session_id=session_id,
        session_type="practice",
        total_questions=5,
        correct_count=4,
        accuracy=0.8,
        duration_minutes=10.0,
    )
    print(f"Publishing {event.event_type} session={session_id}")
    await container.event_bus.publish(event)

    await asyncio.sleep(0.5)

    events = await asyncio.wait_for(stream_task, timeout=5.0)
    print(f"Collected {len(events)} SSE events:")
    for e in events:
        print(" ", e.strip())

    if len(events) < 2:
        print("ERROR: did not receive activity_created SSE")
        sys.exit(1)

    print("OK: SSE received activity event")


if __name__ == "__main__":
    asyncio.run(main())
