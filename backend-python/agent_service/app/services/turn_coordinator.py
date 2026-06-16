from __future__ import annotations

import threading
from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class TurnHandle:
    """一次 run 回合的句柄：token 用于归属判断，cancel_event 用于协作式中断。"""

    token: UUID
    cancel_event: threading.Event


class TurnCoordinator:
    """按 run_id 跟踪“当前正在执行的回合”，支持后到的消息中断仍在进行的回合。

    设计为协作式中断：新回合开始时给上一回合的 cancel_event 置位，正在跑的
    编排工具循环在每轮边界检查该标志并提前收尾。无法打断已阻塞的单次 LLM/工具
    调用——中断在下一轮边界生效（最坏等一次调用返回）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[UUID, TurnHandle] = {}

    def begin(self, run_id: UUID) -> TurnHandle:
        handle = TurnHandle(token=uuid4(), cancel_event=threading.Event())
        with self._lock:
            previous = self._active.get(run_id)
            if previous is not None:
                # 通知上一回合：有新消息到达，请在下一轮边界停下。
                previous.cancel_event.set()
            self._active[run_id] = handle
        return handle

    def cancel(self, run_id: UUID) -> None:
        with self._lock:
            current = self._active.get(run_id)
            if current is not None:
                current.cancel_event.set()

    def is_active(self, run_id: UUID) -> bool:
        with self._lock:
            return run_id in self._active

    def end(self, run_id: UUID, token: UUID) -> None:
        # 仅当自己仍是当前回合时才清理，避免误删已接管的新回合。
        with self._lock:
            current = self._active.get(run_id)
            if current is not None and current.token == token:
                del self._active[run_id]


# 进程内单例：FastAPI 同步端点在线程池中并发执行，按 run_id 共享同一份状态。
TURN_COORDINATOR = TurnCoordinator()
