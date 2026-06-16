from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine


class ChatRunRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, concurrent.futures.Future] = {}
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="agenthub-chat-run-loop",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def spawn(
        self,
        coro: Coroutine,
        *,
        session_id: str,
        name: str | None = None,
    ) -> concurrent.futures.Future:
        del name
        with self._lock:
            existing = self._tasks.get(session_id)
            if existing is not None and not existing.done():
                raise RuntimeError(
                    f"Session {session_id!r} already has an active chat run in this process.",
                )
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            self._tasks[session_id] = future

            def _cleanup(done_future: concurrent.futures.Future) -> None:
                with self._lock:
                    if self._tasks.get(session_id) is done_future:
                        self._tasks.pop(session_id, None)

            future.add_done_callback(_cleanup)
            return future

    def get(self, session_id: str) -> concurrent.futures.Future | None:
        with self._lock:
            return self._tasks.get(session_id)

    async def __aenter__(self) -> ChatRunRegistry:
        return self

    async def __aexit__(self, *exc: object) -> None:
        with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for future in tasks:
            future.cancel()
        for future in tasks:
            try:
                future.result(timeout=5)
            except Exception:
                pass

        async def _drain_pending_tasks() -> None:
            await asyncio.sleep(0)
            current = asyncio.current_task()
            pending = [
                task
                for task in asyncio.all_tasks()
                if task is not current and not task.done()
            ]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        try:
            asyncio.run_coroutine_threadsafe(_drain_pending_tasks(), self._loop).result(timeout=5)
        except Exception:
            pass

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("ChatRunRegistry loop thread did not stop cleanly")
        self._loop.close()
