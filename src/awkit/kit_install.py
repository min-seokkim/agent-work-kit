"""Copy the Markdown agent kit into a project."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

SKIP = {"__pycache__", "__init__.py"}


def kit_root():
    """The kit installed with the wheel, or the repository's kit/ folder when run from source."""
    try:
        from importlib.resources import files
        root = files("awkit.kit")
        if root.joinpath("README.md").is_file():
            return root
    except ModuleNotFoundError:
        pass
    source = Path(__file__).resolve().parents[2] / "kit"
    if (source / "README.md").is_file():
        return source
    raise ValueError("The installed kit files were not found.")


def _copy(node, destination: Path, copied: list[str], prefix="", suffixes=(".md",)):
    """Copy the files under `node` whose names end with one of `suffixes` (every file when None)."""
    for child in sorted(node.iterdir(), key=lambda item: item.name):
        if child.name in SKIP or child.name.endswith((".pyc", ".pyo")):
            continue
        relative = f"{prefix}{child.name}"
        if child.is_dir():
            (destination / child.name).mkdir()
            _copy(child, destination / child.name, copied, relative + "/", suffixes)
        elif suffixes is None or child.name.endswith(tuple(suffixes)):
            (destination / child.name).write_bytes(child.read_bytes())
            copied.append(relative)


EXAMPLES = ("documents", "data", "analysis")


def example_root(kind):
    """The first-run example installed with the wheel, or the repository's examples/first-run folder."""
    if kind not in EXAMPLES:
        raise ValueError("The example kind must be one of: " + ", ".join(EXAMPLES))
    try:
        from importlib.resources import files
        root = files("awkit.examples").joinpath(kind)
        if root.joinpath("README.md").is_file():
            return root
    except ModuleNotFoundError:
        pass
    source = Path(__file__).resolve().parents[2] / "examples" / "first-run" / kind
    if (source / "README.md").is_file():
        return source
    raise ValueError(f"The installed example files were not found: {kind}")


def install_example(kind, target: Path):
    """Create `target` with the example's files. The folder must not exist yet.

    The CLI commits the folder afterwards with `review.track`; this function only copies."""
    source = example_root(kind)
    target = Path(target).absolute()
    if target.exists():
        raise ValueError(f"{target} already exists. Choose a new folder for the example.")
    if not target.parent.is_dir():
        raise ValueError(f"The parent folder does not exist: {target.parent}")
    staging = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
    staging.mkdir()
    copied: list[str] = []
    try:
        _copy(source, staging, copied, suffixes=None)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target, copied


TIERS = ("efficient", "standard", "judge", "top")
CLAUDE_DEFAULTS = {"efficient": "haiku", "standard": "sonnet", "judge": "opus"}
READ_ONLY_TOOLS = "Read, Grep, Glob, Bash"


def load_roles():
    """Read the provider-neutral role templates (front matter plus instructions)."""
    folder = kit_root().joinpath("templates").joinpath("roles")
    roles = []
    for item in sorted(folder.iterdir(), key=lambda entry: entry.name):
        if not item.name.endswith(".md") or item.name == "README.md":
            continue
        text = item.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise ValueError(f"Cannot read the front matter of the role template: {item.name}")
        head, body = text[4:].split("\n---\n", 1)
        meta = {}
        for line in head.splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        if meta.get("tier") not in TIERS or meta.get("access") not in ("read-only", "write") or not meta.get("name"):
            raise ValueError(f"The role template needs valid name, tier and access fields: {item.name}")
        roles.append({**meta, "instructions": body.strip() + "\n"})
    return roles


def parse_models(specs):
    """Turn ["judge=opus", "efficient=gpt-x:medium"] into {tier: (model, effort)}."""
    models = {}
    for spec in specs or []:
        tier, sep, value = spec.partition("=")
        model, _, effort = value.partition(":")
        if not sep or tier not in TIERS or not model.strip():
            raise ValueError(f"--model takes TIER=MODEL or TIER=MODEL:EFFORT: {spec}")
        if any(ch in model + effort for ch in "\n\"'\\"):
            raise ValueError(f"The model name contains characters that cannot be written: {spec}")
        models[tier] = (model.strip(), effort.strip() or None)
    return models


def _toml_string(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _claude_file(role, model):
    lines = ["---", f"name: {role['name']}", f"description: {json.dumps(role['description'], ensure_ascii=False)}",
             f"model: {model}"]
    if role["access"] == "read-only":
        lines.append(f"tools: {READ_ONLY_TOOLS}")
    return "\n".join(lines) + "\n---\n" + role["instructions"]


def _codex_file(role, name, model):
    lines = [f"name = {_toml_string(name)}", f"description = {_toml_string(role['description'])}"]
    if model:
        lines.append(f"model = {_toml_string(model[0])}")
        if model[1]:
            lines.append(f"model_reasoning_effort = {_toml_string(model[1])}")
    instructions = role["instructions"]
    if "'''" in instructions:
        raise ValueError(f"Role instructions cannot contain ''': {role['name']}")
    lines.append(f"developer_instructions = '''\n{instructions}'''")
    return "\n".join(lines) + "\n"


def install_roles(project: Path, provider: str, specs=None):
    """Write provider role files under the project. Existing files are never overwritten."""
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError(f"The target folder does not exist: {project}")
    models = parse_models(specs)
    roles = load_roles()
    planned, warnings = [], []
    if provider == "claude":
        if any(effort for _, effort in models.values()):
            raise ValueError("Claude Code role files take a model only, without a reasoning effort.")
        if "top" in models:
            warnings.append("The top tier was not written: in Claude Code the model given at call time overrides the role file.")
        mapping = {**CLAUDE_DEFAULTS, **{tier: model for tier, (model, _) in models.items() if tier != "top"}}
        folder = project / ".claude" / "agents"
        for role in roles:
            planned.append((folder / f"{role['name']}.md", _claude_file(role, mapping[role["tier"]])))
    elif provider == "codex":
        folder = project / ".codex" / "agents"
        inherited = []
        for role in roles:
            model = models.get(role["tier"])
            if not model:
                inherited.append(role["name"])
            planned.append((folder / f"{role['name']}.toml", _codex_file(role, role["name"], model)))
        if "top" in models:
            analyst = next(role for role in roles if role["name"] == "analyst")
            planned.append((folder / "analyst_top.toml",
                            _codex_file({**analyst, "description": analyst["description"] + " Judgment role pinned to the top-tier model."},
                                        "analyst_top", models["top"])))
        if inherited:
            warnings.append("roles without a model inherit the [agents] default or the parent session's model: "
                            + ", ".join(inherited))
    else:
        raise ValueError("provider must be claude or codex.")
    written, skipped = [], []
    for path, content in planned:
        if path.exists():
            skipped.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        written.append(path)
    return written, skipped, warnings


# Situation guides and the skill each becomes: (skill name, guide file, description, extra instruction).
# The description is what the agent sees before loading the skill, so it names the situation.
SITUATIONS = (
    ("awkit-connect", "connect.md",
     "Connect Agent Work Kit to this project. Use when the agent-work-kit folder was just added or its project "
     "profile is still empty.", ""),
    ("awkit-writing", "writing.md",
     "Write or revise text people read: documents, reports, READMEs, UI text, CLI output, notifications, handoffs, "
     "commit and PR descriptions.", "For Korean text, also read `{kit}/korean-writing.md`."),
    ("awkit-work-types", "work-types.md",
     "Decide inputs and completion evidence for work that is not a code change: research, writing, data "
     "preparation and analysis, environment setup and troubleshooting, operating an application, learning, "
     "automation.", ""),
    ("awkit-checking", "checking.md",
     "Set up or interpret project checks: check configuration, isolated worktrees, databases, ports and devices "
     "shared by checks, multiprocess programs, and failures that pass on a rerun.", ""),
    ("awkit-delivery", "delivery.md",
     "Hand over, submit, publish or deploy a result, or replace a running version, and confirm it arrived.", ""),
    ("awkit-delegation", "delegation.md",
     "Split work across subagents, choose roles and models, or write a handoff for another agent.", ""),
    ("awkit-review-session", "review-session.md",
     "Work with a separate review session through awkit channel, as the main session or as the reviewer.", ""),
    ("awkit-records", "protocol.md",
     "Keep task records and states, write review or decision records, or resume work another session left.", ""),
)
SKILL_FOLDERS = {"claude": Path(".claude") / "skills", "codex": Path(".agents") / "skills"}


def install_skills(project: Path, provider: str, kit: Path | None = None):
    """Write one skill per situation guide. Each skill points to the guide in the project's kit folder, so
    the kit stays the single source. Existing skill files are never overwritten."""
    if provider not in SKILL_FOLDERS:
        raise ValueError("The provider must be claude or codex.")
    project = Path(project).resolve()
    kit = (project / "agent-work-kit") if kit is None else Path(kit).resolve()
    if not (kit / "workflow.md").is_file():
        raise ValueError(f"No kit folder with workflow.md at {kit}. Run `awkit kit init` first or pass --kit.")
    try:
        kit_path = kit.relative_to(project).as_posix()
    except ValueError as exc:
        raise ValueError("The kit folder must be inside the project folder.") from exc
    written, skipped = [], []
    for name, guide, description, extra in SITUATIONS:
        path = project / SKILL_FOLDERS[provider] / name / "SKILL.md"
        if path.exists():
            skipped.append(path)
            continue
        body = (f"Read `{kit_path}/{guide}` and follow it. It is a situation guide of Agent Work Kit; the baseline "
                f"workflow in `{kit_path}/workflow.md` still applies.")
        if extra:
            body += " " + extra.format(kit=kit_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # A JSON string is a valid YAML double-quoted scalar; descriptions contain ": ", which plain YAML forbids.
        path.write_text(f"---\nname: {name}\ndescription: {json.dumps(description)}\n---\n\n{body}\n",
                        encoding="utf-8", newline="\n")
        written.append(path)
    return written, skipped


def install(parent: Path, name="agent-work-kit"):
    """Create parent/name with the kit. Never overwrites: existing records stay untouched.

    The CLI commits the new folder afterwards with `review.track`; this function only copies."""
    if not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("The folder name cannot contain path separators.")
    parent = Path(parent).resolve()
    if not parent.is_dir():
        raise ValueError(f"The target folder does not exist: {parent}")
    target = parent / name
    if target.exists():
        raise ValueError(f"{target} already exists. To keep the records written there, "
                         "install into another folder with --name and compare.")
    staging = parent / f".{name}.{uuid.uuid4().hex}.tmp"
    staging.mkdir()
    copied: list[str] = []
    try:
        _copy(kit_root(), staging, copied)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target, copied
