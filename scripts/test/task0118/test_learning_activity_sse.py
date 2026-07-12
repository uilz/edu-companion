"""Test script for LearningActivity SSE stream.

用法：
    cd /home/deploy/edu-companion
    python3 scripts/test/task0110/test_learning_activity_sse.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "backend"))

from shared.events import SessionCompleted
from app.application.di import container


async def main() -> None:
    bus = container.event_bus
    user_id = "u_f65eb04e5c6b"
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"

    event = SessionCompleted(
        user_id=user_id,
        session_id=session_id,
        session_type="practice",
        total_questions=5,
        correct_count=4,
        accuracy=0.8,
        duration_minutes=10.0,
    )

    print(f"Publishing {event.event_type} session={session_id} for user={user_id}")
    await bus.publish(event)
    await asyncio.sleep(0.3)
    print("OK: event published")


if __name__ == "__main__":
    asyncio.run(main())
