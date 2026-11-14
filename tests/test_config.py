import pytest

from fu import config, core


@pytest.fixture
def cfg():
    config.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    return config.CONFIG_FILE


def test_defaults_apply_without_a_file():
    assert config.load()["jobs"]["types"] == list(core.KINDS) and config.modifier() == "ctrl"


def test_projects_override_the_top_level_settings(cfg):
    cfg.write_text(
        "ai:\n  agent: claude\n  skills: [a]\n"
        "projects:\n  ML:\n    ai:\n      skills: [learn]\n    jobs:\n      extra_types: [chore]\n"
    )
    assert config.for_project("ML")["ai"]["skills"] == ["learn"]
    assert config.for_project("ML")["ai"]["agent"] == "claude"  # untouched settings come from the top
    assert config.for_project("OPS")["ai"]["skills"] == ["a"]
    assert core.job_types(project="ML") == [*core.KINDS, "chore"] and "chore" not in core.job_types()


def test_types_can_be_replaced(cfg):
    cfg.write_text("jobs:\n  types: [feature, chore]\n")
    assert core.job_types() == ["feature", "chore"]


def test_a_broken_file_is_ignored_not_fatal(cfg, capsys):
    cfg.write_text("keys: [unclosed\n")
    assert config.modifier() == "ctrl" and "doesn't parse" in capsys.readouterr().err


def test_an_old_toml_config_is_converted_once_and_kept(cfg, capsys):
    old = cfg.with_suffix(".toml")
    old.write_text('data_dir = "~/elsewhere"\n\n[keys]\nmodifier = "alt"\n')
    loaded = config.load()
    assert loaded["data_dir"] == "~/elsewhere" and loaded["keys"]["modifier"] == "alt"
    assert cfg.exists() and not old.exists() and old.with_name("config.toml.migrated").exists()
    assert "# follow-ups (fu) config" in cfg.read_text()  # the comments of the default file survive
    assert "config.toml.migrated" in capsys.readouterr().err
