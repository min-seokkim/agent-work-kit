"""Write the kit into a project: self-contained skills, role files, examples, or a copy of the kit folder."""

from __future__ import annotations

import json
import posixpath
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from .environment import GENERATED

SKIP = {"__pycache__", "__init__.py"}
# The failure catalogue entries (kit/failures.md) these commands guard against: guidance kept in context
# every session before anything shows it is needed, and a second copy of what a method bundle does (F12);
# a way of working that reaches only the project where someone copied it, not the person's next session
# elsewhere or an agent without skills (F29).
PREVENTS = {"awkit kit skills": ("F12", "F29"), "awkit kit guide": ("F29",)}


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
# The description is what the agent keeps in context every session to decide when to load the skill, so it
# is one line naming the situation. connect.md has no skill of its own: the workflow skill carries it, and
# a connected project would carry a second description in every session for a procedure used once.
WORKFLOW = ("awkit-workflow", "workflow.md",
            "Define, check and report any task here; connect the kit while the profile is empty.", "")
SITUATIONS = (
    ("awkit-writing", "writing.md",
     "Write or revise text people read: documents, reports, UI text, commit messages.",
     "For Korean text, also read `{kit}/korean-writing.md`."),
    ("awkit-work-types", "work-types.md",
     "Inputs and evidence for research, data, setup, operations, learning or automation work.", ""),
    ("awkit-checking", "checking.md",
     "Set up project checks, or read results that fail, pass on rerun or share resources.", ""),
    ("awkit-delivery", "delivery.md",
     "Hand over, publish or deploy a result and confirm it arrived.", ""),
    ("awkit-delegation", "delegation.md",
     "Split work across subagents, choose models or write a handoff.", ""),
    ("awkit-review-session", "review-session.md",
     "Work with a separate review session through awkit channel.", ""),
    ("awkit-records", "protocol.md",
     "Keep task records and states, or resume work another session left.", ""),
)
SKILL_FOLDERS = {"claude": Path(".claude") / "skills", "codex": Path(".agents") / "skills"}
# Guides inlined after the main guide in a self-contained skill, with the heading they get there.
APPENDED = {"awkit-workflow": ("connect.md",), "awkit-writing": ("korean-writing.md",)}
TEMPLATES = ("task.md", "review.md", "decision.md", "checkpoint.md")
# What a method bundle such as superpowers already does: planning, review and delegation. Its skills are
# the project's way of doing those, so the kit keeps only the evidence loop: checks, delivery and writing,
# and the workflow, whose check and report steps the bundle leaves to the project.
COVERED_BY_BUNDLES = {
    "awkit-work-types": "plans the work",
    "awkit-delegation": "delegates to subagents",
    "awkit-review-session": "runs reviews",
    "awkit-records": "keeps plans and task state",
}
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(#{1,5}) ", re.M)


def _skill_of(guide):
    for name, file, *_ in (WORKFLOW, *SITUATIONS):
        if file == guide:
            return name
    for name, files in APPENDED.items():
        if guide in files:
            return name
    return None


def _rewrite_links(text, skill, base=""):
    """Links between kit files lead nowhere inside a skill folder: name the skill or section instead.
    `base` is the folder of the file the text comes from, relative to the kit."""
    def replace(match):
        label, target = match.groups()
        if re.match(r"[a-z]+:", target):
            return match.group(0)
        path = target.split("#", 1)[0]
        if not path:
            return label
        path = posixpath.normpath(base + path)
        if path in ("LICENSE.md", "THIRD_PARTY_NOTICES.md"):
            return f"{label} (at the end of this skill)" if skill == "awkit-writing" else label
        if path == "templates/project.md":
            return f"{label} (the `[kit]` table of `checks.toml`; `awkit kit guide profile` prints the long form)"
        if path.startswith("templates/") and Path(path).name in TEMPLATES:
            return f"{label} (below)" if skill == "awkit-records" else f"{label} (in the `awkit-records` skill)"
        if path.startswith("templates/roles/"):
            return f"{label} (`awkit kit roles` writes them)"
        owner = _skill_of(path)
        if owner == skill:
            return f"{label} (below)" if path in APPENDED.get(skill, ()) else label
        if owner:
            return f"{label} (the `{owner}` skill)"
        name = guide_name(path)
        if name:
            return f"{label} (`awkit kit guide {name}`)"
        shown = f"`{path}`" if label == path else f"{label} (`{path}`"
        return shown + " in the Agent Work Kit package" + ("" if label == path else ")")
    return LINK.sub(replace, text)


# `awkit kit guide NAME` prints a kit file for agents without skills and for people. The names are the
# guides' file names without `.md`, plus the templates, which have no guide of their own.
GUIDE_ALIASES = {"profile": "templates/project.md", "profiles": "examples/project-profiles.md",
                 **{Path(name).stem: f"templates/{name}" for name in TEMPLATES}}


def guide_files():
    """{name: kit-relative path} for every guide `kit guide` prints."""
    found = {}
    for item in sorted(kit_root().iterdir(), key=lambda entry: entry.name):
        if item.name.endswith(".md"):
            found[item.name[:-3].lower().replace("_", "-")] = item.name
    return {**found, **GUIDE_ALIASES}


def guide_name(path):
    """The `kit guide` name of a kit-relative path, or None."""
    return next((name for name, file in guide_files().items() if file == path), None)


def guide(name):
    """A kit guide's text, with links between kit files turned into `awkit kit guide` names, since a
    reader of the printed text has no folder to follow them in."""
    files = guide_files()
    key = name.lower().removesuffix(".md")
    if key not in files:
        raise ValueError(f"No guide named {name}. Guides: " + ", ".join(sorted(files)))
    path = files[key]
    base = posixpath.dirname(path)

    def replace(match):
        label, target = match.groups()
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            return match.group(0)
        target = posixpath.normpath(posixpath.join(base, target.split("#", 1)[0]))
        if target == "templates/project.md" and path != target:
            return f"{label} (the `[kit]` table of `checks.toml`; `awkit kit guide profile` prints the long form)"
        linked = guide_name(target)
        return f"{label} (`awkit kit guide {linked}`)" if linked else label
    return LINK.sub(replace, _guide(path))


def _demote(text):
    """Headings one level down, outside code blocks, for a guide appended under another."""
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r"\s*(`{3,}|~{3,})", line)
        if marker:
            fence = None if fence and marker.group(1)[0] == fence else (fence or marker.group(1)[0])
        elif fence is None and HEADING.match(line):
            line = "#" + line
        lines.append(line)
    return "\n".join(lines) + "\n"


def _guide(name):
    return kit_root().joinpath(name).read_text(encoding="utf-8").replace("\r\n", "\n")


def _source_label():
    record = kit_source()
    label = f"awkit {record['awkit']}"
    if record.get("commit"):
        label += f" (kit commit {record['commit'][:7]})"
    return label


def skill_text(name, guide, description, extra="", kit_path=None):
    """The SKILL.md for one guide. With `kit_path` it points to the guide in a kit folder inside the
    project; otherwise it holds the guide itself, so nothing outside the skill folder is needed."""
    head = f"---\nname: {name}\n" \
           f"description: {json.dumps(description)}\n---\n\n"  # JSON is valid YAML; ": " needs quoting
    if kit_path is not None:
        body = (f"Read `{kit_path}/{guide}` and follow it. It is a situation guide of Agent Work Kit; the baseline "
                f"workflow in `{kit_path}/workflow.md` still applies.")
        if extra:
            body += " " + extra.format(kit=kit_path)
        # Only the version: the guide it points at carries the content, so the file changes only with awkit.
        return head + f"{GENERATED} by awkit {kit_source()['awkit']}. Update with `awkit kit skills --project --kit {kit_path}`. -->\n\n" \
            + body + "\n"
    sources = [guide, *APPENDED.get(name, ())]
    # One line: which awkit made the file and how to update it. A skill in the user folder outlives any
    # project, so the version is what tells a reader whether it is current.
    parts = [f"{GENERATED} by {_source_label()} from {', '.join(sources)}. Update with `awkit kit skills`. -->\n",
             _rewrite_links(_guide(guide), name)]
    for appended in APPENDED.get(name, ()):
        parts.append(_demote(_rewrite_links(_guide(appended), name)))
    if name == "awkit-records":
        for template in TEMPLATES:
            text = _rewrite_links(_guide(f"templates/{template}"), name, "templates/")
            parts.append(f"## Template: {template}\n\nCopy it into the project's record location when the project "
                         f"has no record system of its own.\n\n````markdown\n{text.rstrip()}\n````\n")
    parts.append("## License\n\n" + _guide("LICENSE.md").replace("# MIT License", "MIT License", 1).strip() + "\n")
    if name == "awkit-writing":
        notices = _guide("THIRD_PARTY_NOTICES.md")
        parts.append(_demote(_rewrite_links(notices, name)))
    return head + "\n".join(part.rstrip("\n") + "\n" for part in parts)


def planned_skills(project: Path, provider: str, kit: Path | None = None, found_bundles=None, names=None):
    """([(skill name, path, text)], [(skill name, reason)]) that `install_skills` would write."""
    from .environment import bundles
    if provider not in SKILL_FOLDERS:
        raise ValueError("The provider must be claude or codex.")
    project = Path(project).resolve()
    copied = project / "agent-work-kit"
    if kit is None and (copied / "workflow.md").is_file():
        kit = copied
    kit_path = None
    if kit is not None:
        kit = Path(kit).resolve()
        if not (kit / "workflow.md").is_file():
            raise ValueError(f"No kit folder with workflow.md at {kit}. Leave out --kit to write self-contained skills.")
        try:
            kit_path = kit.relative_to(project).as_posix()
        except ValueError as exc:
            raise ValueError("The kit folder must be inside the project folder.") from exc
    found_bundles = bundles(project) if found_bundles is None else found_bundles
    # With a kit folder the instruction file points at workflow.md itself; without one the workflow is a skill.
    chosen = SITUATIONS if kit_path is not None else (WORKFLOW, *SITUATIONS)
    planned, omitted = [], []
    for name, guide, description, extra in chosen:
        if names is not None and name not in names:
            omitted.append((name, "left out with --without"))
            continue
        if found_bundles and name in COVERED_BY_BUNDLES:
            bundle = found_bundles[0]
            omitted.append((name, f"{bundle['name']} ({bundle['evidence']}) {COVERED_BY_BUNDLES[name]}"))
            continue
        path = project / SKILL_FOLDERS[provider] / name / "SKILL.md"
        planned.append((name, path, skill_text(name, guide, description, extra, kit_path)))
    return planned, omitted


def install_skills(project: Path, provider: str, kit: Path | None = None, changes=None, names=None):
    """Write one skill per guide into the project, or only the skills in `names`. Files awkit wrote earlier
    are regenerated; any other file with the same name is kept. Returns {created, updated, unchanged, kept,
    omitted}."""
    planned, omitted = planned_skills(project, provider, kit, names=names)
    return _write_skills(planned, omitted, changes)


def user_skill_folders(home=None):
    """Where Claude Code and Codex read skills for every project of this user: `~/.claude/skills` and
    `~/.agents/skills` (Codex also reads the older `$CODEX_HOME/skills`; awkit writes the current place)."""
    home = Path.home() if home is None else Path(home)
    return {provider: home / folder for provider, folder in SKILL_FOLDERS.items()}


def skill_names(without=()):
    """The skill names `without` leaves, from names given with or without the `awkit-` prefix."""
    names = [name for name, *_ in (WORKFLOW, *SITUATIONS)]
    chosen = set()
    for value in without:
        for part in str(value).split(","):
            part = part.strip()
            if not part:
                continue
            name = part if part.startswith("awkit-") else f"awkit-{part}"
            if name not in names:
                raise ValueError(f"No skill named {part}. Skills: " + ", ".join(n.removeprefix("awkit-") for n in names))
            chosen.add(name)
    return [name for name in names if name not in chosen], sorted(chosen)


def install_user_skills(providers=("claude", "codex"), without=(), home=None):
    """Write the self-contained skills into the user's skill folders, which every session of the agent reads
    in any project; the guides are the person's way of working, not a project's. Skills left out with
    `without` that awkit wrote earlier are deleted. Everything written is recorded in `~/.awkit/installed.json`,
    which `kit remove --user` reads. Returns ({provider: result}, record path or None)."""
    from .connect import Changes
    from .environment import is_awkit_skill
    home = Path.home() if home is None else Path(home)
    keep, left_out = skill_names(without)
    changes = Changes(home, exclude=False)
    results = {}
    for provider in providers:
        folder = user_skill_folders(home)[provider]
        planned = [(name, folder / name / "SKILL.md", skill_text(name, guide, description, extra))
                   for name, guide, description, extra in (WORKFLOW, *SITUATIONS) if name in keep]
        result = _write_skills(planned, [(name, "left out with --without") for name in left_out], changes)
        result["removed"] = []
        for name in left_out:
            path = folder / name / "SKILL.md"
            if path.is_file() and is_awkit_skill(path.read_text(encoding="utf-8", errors="replace")):
                path.unlink()
                if not any(path.parent.iterdir()):
                    path.parent.rmdir()
                result["removed"].append(path)
        results[provider] = result
    return results, changes.save()


def _write_skills(planned, omitted, changes):
    from .environment import is_awkit_skill
    result = {"created": [], "updated": [], "unchanged": [], "kept": [], "omitted": omitted}
    for _, path, text in planned:
        if path.exists():
            current = path.read_text(encoding="utf-8", errors="replace")
            if not is_awkit_skill(current):
                result["kept"].append(path)
                continue
            if current == text:
                result["unchanged"].append(path)
                continue
            key = "updated"
        else:
            key = "created"
        if changes is not None:
            changes.write(path, text, "created")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        result[key].append(path)
    return result


VERSION_FILE = "VERSION.txt"


def kit_source():
    """Which version of the kit `install` copies: the awkit version, and for a source checkout its commit
    and whether kit/ had uncommitted changes, which are copied as they are."""
    from . import __version__
    record = {"awkit": __version__, "source": "package"}
    checkout = Path(__file__).resolve().parents[2]
    try:
        from_checkout = Path(str(kit_root())).resolve() == (checkout / "kit").resolve()
    except ValueError:
        from_checkout = False
    if from_checkout:
        record["source"] = "checkout"

        def run(*args):
            return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        head = run("rev-parse", "--verify", "-q", "HEAD")
        if head.returncode == 0:
            record["commit"] = head.stdout.strip()
            record["uncommitted kit changes"] = "yes" if run("status", "--porcelain", "--", "kit").stdout.strip() else "no"
    return record


def read_version(kit: Path):
    """The record `install` wrote into a kit folder, or {} for a kit copied before it did."""
    try:
        lines = (Path(kit) / VERSION_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    return dict(line.split(": ", 1) for line in lines if ": " in line)


def install(parent: Path, name="agent-work-kit"):
    """Create parent/name with the kit. Never overwrites: existing records stay untouched.

    With `--commit`, the CLI commits the new folder afterwards with `review.track`; this function only copies."""
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
        _copy(kit_root(), staging, copied, suffixes=(".md", ".toml"))
        record = kit_source()
        (staging / VERSION_FILE).write_text(
            "Written by awkit kit init. Compare it with a newer kit's before carrying changes over.\n"
            + "".join(f"{key}: {value}\n" for key, value in record.items()), encoding="utf-8", newline="\n")
        copied.append(VERSION_FILE)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target, copied
