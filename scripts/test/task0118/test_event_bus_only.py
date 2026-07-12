"""Test LearningActivityEventBus directly."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "backend"))

from app.application.handlers.learning_activity_event_bus import learning_activity_event_bus


async def main() -> None:
    user_id = "u_test"
    events: list[str] = []

    async def collect() -> None:
        async for sse in learning_activity_event_bus.stream_events(user_id):
            events.append(sse)
            if len(events) >= 2:
                break

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.3)

    await learning_activity_event_bus.publish(
        event_type="activity_created",
        user_id=user_id,
        activity_id="la_test_001",
        data={"title": "test activity"},
    )

    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
        print("TIMEOUT")

    print(f"Received {len(events)} events:")
    for e in events:
        print(" ", e.strip())


if __name__ == "__main__":
    asyncio.run(main())
