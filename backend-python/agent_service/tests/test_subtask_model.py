from uuid import uuid4

from agent_service.app.models.subtask import SubtaskModel


def test_subtask_model_keeps_session_id() -> None:
    session_id = uuid4()
    subtask = SubtaskModel(
        subtask_id=uuid4(),
        session_id=session_id,
        root_run_id=uuid4(),
        parent_run_id=uuid4(),
        worker_run_id=uuid4(),
        status="created",
        task_prompt="demo",
    )

    assert subtask.session_id == session_id
