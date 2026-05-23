from __future__ import annotations

from app.database.memory_store import STORE
from app.database.seed import seed_memory_store


def bootstrap_memory_store() -> None:
    STORE.reset()
    seed_memory_store()
