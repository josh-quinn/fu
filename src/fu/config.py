"""The config file, ~/.config/jq-tools/follow-ups/config.yaml (ADR 0008).

Settings at the top apply everywhere; an entry under `projects:` (a Jira key such as ML) overrides
any of them for that project's jobs. fu reads this file and never writes it, apart from creating
it with the defaults and converting an old config.toml once.
"""

import os
import re
import sys
import tomllib
from pathlib import Path

import yaml

CONFIG_ROOT = Path(os.environ.get("JQ_TOOLS_CONFIG", "~/.config/jq-tools")).expanduser()
CONFIG_FILE = CONFIG_ROOT / "follow-ups" / "config.yaml"
MODIFIERS = ("ctrl", "alt", "super", "meta")
DEFAULT_YAML = """\
# follow-ups (fu) config. Settings at the top apply everywhere; a project under `projects:`
# (its Jira key, e.g. ML) overrides any of them for that project's jobs.

# Where board.json and BOARD.md live. FU_DATA_DIR overrides this per command.
data_dir: ~/development/follow-ups

keys:
  # Held with a letter it runs a shortcut (a add, e edit, y copy ...) even while a column search
  # is typing. "ctrl" works in every terminal; "alt" in most; "super" (Cmd) needs a terminal
  # that reports it (kitty, Ghostty, WezTerm).
  modifier: ctrl

jobs:
  types: [epic, story, bug, spike, task]  # replace the list of job types
  extra_types: []                         # or add to it
  home: ""          # where new sessions start for a job with no home folder of its own
  templates: {}     # type -> the description a new job of that type starts with, e.g.
  #   story: "As a <who> I want <what> so that <why>."

ai:                 # what a new session started from fu gets
  agent: claude     # claude or copilot
  model: ""         # blank lets the agent choose
  skills: []        # named in the session's brief as skills to use
  instructions: ""  # added to the session's brief
  mcp_config: ""    # a JSON file of MCP servers
  add_dirs: []      # extra folders the agent may use
  allowed_tools: []
  claude:
    args: []        # any other flags, passed as they are
  copilot:
    args: []

projects: {}
#  ML:
#    jobs:
#      home: ~/vault/msc-ai
#    ai:
#      skills: [learn]
"""


def merge(base: dict, over: dict) -> dict:
    """A copy of base with over laid on top; dicts merge, everything else is replaced."""
    out = dict(base)
    for key, value in (over or {}).items():
        out[key] = merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def _from_toml(old: Path) -> str:
    """The default YAML carrying over what an old config.toml set."""
    data = tomllib.loads(old.read_text())
    text = DEFAULT_YAML
    if "data_dir" in data:
        text = re.sub(r"(?m)^data_dir: .*$", f"data_dir: {data['data_dir']}", text)
    if data.get("keys", {}).get("modifier") in MODIFIERS:
        text = re.sub(r"(?m)^  modifier: .*$", f"  modifier: {data['keys']['modifier']}", text)
    return text


def ensure() -> None:
    """Create the config on first use, converting a config.toml from before if there is one."""
    if CONFIG_FILE.exists():
        return
    old = CONFIG_FILE.with_suffix(".toml")
    if old.exists():
        CONFIG_FILE.write_text(_from_toml(old))
        old.rename(old.with_name("config.toml.migrated"))
        print(f"fu: moved your settings to {CONFIG_FILE} (the old file is config.toml.migrated)", file=sys.stderr)
    elif "JQ_TOOLS_CONFIG" not in os.environ:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(DEFAULT_YAML)


def load() -> dict:
    """The defaults with the file laid over them. A file that doesn't parse is reported and ignored."""
    ensure()
    defaults = yaml.safe_load(DEFAULT_YAML)
    try:
        user = yaml.safe_load(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
    except (OSError, yaml.YAMLError) as err:
        print(f"fu: ignoring {CONFIG_FILE}, it doesn't parse: {err}", file=sys.stderr)
        user = {}
    return merge(defaults, user if isinstance(user, dict) else {})


def for_project(project: str | None) -> dict:
    """The settings for one project: the top-level ones with that project's overrides on top."""
    cfg = load()
    projects = cfg.pop("projects", None) or {}
    return merge(cfg, projects.get(project) or {}) if project else cfg


def modifier() -> str:
    mod = str((load().get("keys") or {}).get("modifier", "ctrl"))
    return mod if mod in MODIFIERS else "ctrl"
