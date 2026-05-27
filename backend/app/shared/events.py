"""
Compatibility shim — re-exports all events from the canonical source.

All event classes are now defined in `backend/shared/events.py`.
This module exists so that old imports of `app.shared.events` still work.
New code should import directly from `shared.events`.
"""
from shared.events import *  # noqa: F401, F403
