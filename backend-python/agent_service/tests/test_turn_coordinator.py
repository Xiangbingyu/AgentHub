from uuid import uuid4

from agent_service.app.services.turn_coordinator import TurnCoordinator


def test_begin_cancels_previous_turn_for_same_run() -> None:
    coordinator = TurnCoordinator()
    run_id = uuid4()

    first = coordinator.begin(run_id)
    assert not first.cancel_event.is_set()

    # 同一 run 再开新回合：上一回合应被置中断标志。
    second = coordinator.begin(run_id)
    assert first.cancel_event.is_set()
    assert not second.cancel_event.is_set()
    assert first.token != second.token


def test_begin_does_not_cross_cancel_other_runs() -> None:
    coordinator = TurnCoordinator()
    run_a = uuid4()
    run_b = uuid4()

    turn_a = coordinator.begin(run_a)
    coordinator.begin(run_b)
    # 不同 run 互不影响。
    assert not turn_a.cancel_event.is_set()


def test_end_only_clears_when_still_current() -> None:
    coordinator = TurnCoordinator()
    run_id = uuid4()

    first = coordinator.begin(run_id)
    second = coordinator.begin(run_id)

    # 旧回合结束不应清掉已接管的新回合。
    coordinator.end(run_id, first.token)
    third = coordinator.begin(run_id)
    assert second.cancel_event.is_set()  # 仍被 third 正常中断，说明 second 仍是登记的当前回合
    assert not third.cancel_event.is_set()
