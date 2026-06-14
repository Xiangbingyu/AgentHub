from pathlib import Path

import pytest

from agent_service.app.runtime.workspace.workspace_tree import list_tree_level


def test_list_tree_level_returns_entries(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "readme.md").write_text("y")

    entries = list_tree_level(str(tmp_path), ".")
    by_name = {entry["name"]: entry for entry in entries}

    assert by_name["src"]["type"] == "directory"
    assert by_name["readme.md"]["type"] == "file"


def test_list_tree_level_lists_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")

    entries = list_tree_level(str(tmp_path), "src")
    by_name = {entry["name"]: entry for entry in entries}

    assert by_name["a.py"]["type"] == "file"
    assert by_name["a.py"]["path"] == "src/a.py"


def test_list_tree_level_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        list_tree_level(str(tmp_path), "../..")
