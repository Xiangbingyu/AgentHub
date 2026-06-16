from uuid import uuid4

from agent_service.app.models.subtask import SubtaskModel
from agent_service.app.repositories.subtask_repository import SubtaskRepository


def test_list_by_session_id_returns_only_matching() -> None:
    repository = SubtaskRepository()
    session_id = uuid4()
    other_session_id = uuid4()

    mine = SubtaskModel(
        subtask_id=uuid4(),
        session_id=session_id,
        root_run_id=uuid4(),
        parent_run_id=uuid4(),
        task_prompt="mine",
    )
    other = SubtaskModel(
        subtask_id=uuid4(),
        session_id=other_session_id,
        root_run_id=uuid4(),
        parent_run_id=uuid4(),
        task_prompt="other",
    )

    repository.create(mine)
    repository.create(other)
    items = repository.list_by_session_id(session_id)

    subtask_ids = {item.subtask_id for item in items}
    assert mine.subtask_id in subtask_ids
    assert other.subtask_id not in subtask_ids
