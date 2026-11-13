"""Every test runs against a throwaway board and never touches the real one."""

import pytest

from fu import core


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("FU_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JQ_TOOLS_CONFIG", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for var in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(var, raising=False)
    # CONFIG_FILE is fixed when core is imported, so the env var above is too late to protect it
    monkeypatch.setattr(core, "CONFIG_FILE", tmp_path / "cfg" / "follow-ups" / "config.toml")
    monkeypatch.setattr(core, "COPILOT_SESSIONS", tmp_path / "copilot-sessions")
    return tmp_path


@pytest.fixture
def seeded():
    """Two jobs; four tasks across three sessions, one done."""
    db = core.load_db()
    core.ensure_job(db, "Backprop from scratch", "epic")
    core.ensure_job(db, "ReLU derivative bug", "bug")
    sess = {"claude": "aaaa1111-0000-0000-0000-000000000001", "copilot": "bbbb2222-0000-0000-0000-000000000002"}
    core.new_item(
        db, "Write gradient check", agent="claude", session_id=sess["claude"], cwd="/w", job="Backprop from scratch"
    )
    core.new_item(
        db, "Vectorise softmax", agent="copilot", session_id=sess["copilot"], cwd="/d", job="Backprop from scratch"
    )
    core.new_item(
        db, "Check relu_backward", agent="claude", session_id=sess["claude"], cwd="/w", job="ReLU derivative bug"
    )
    core.new_item(db, "Tidy notes", status="done", last_worked="2026-10-01")
    core.save_db(db)
    return core.load_db()
