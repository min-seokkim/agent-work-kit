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
    raise ValueError("설치된 키트 파일을 찾지 못했습니다.")


def _copy(node, destination: Path, copied: list[str], prefix=""):
    for child in sorted(node.iterdir(), key=lambda item: item.name):
        if child.name in SKIP:
            continue
        relative = f"{prefix}{child.name}"
        if child.is_dir():
            (destination / child.name).mkdir()
            _copy(child, destination / child.name, copied, relative + "/")
        elif child.name.endswith(".md"):
            (destination / child.name).write_bytes(child.read_bytes())
            copied.append(relative)


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
            raise ValueError(f"역할 양식의 머리말을 읽지 못했습니다: {item.name}")
        head, body = text[4:].split("\n---\n", 1)
        meta = {}
        for line in head.splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        if meta.get("tier") not in TIERS or meta.get("access") not in ("read-only", "write") or not meta.get("name"):
            raise ValueError(f"역할 양식의 name, tier, access를 확인하세요: {item.name}")
        roles.append({**meta, "instructions": body.strip() + "\n"})
    return roles


def parse_models(specs):
    """Turn ["judge=opus", "efficient=gpt-x:medium"] into {tier: (model, effort)}."""
    models = {}
    for spec in specs or []:
        tier, sep, value = spec.partition("=")
        model, _, effort = value.partition(":")
        if not sep or tier not in TIERS or not model.strip():
            raise ValueError(f"--model은 등급=모델 또는 등급=모델:추론수준 형식이어야 합니다: {spec}")
        if any(ch in model + effort for ch in "\n\"'\\"):
            raise ValueError(f"모델 이름에 쓸 수 없는 문자가 있습니다: {spec}")
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
        raise ValueError(f"역할 지침에 ''' 를 쓸 수 없습니다: {role['name']}")
    lines.append(f"developer_instructions = '''\n{instructions}'''")
    return "\n".join(lines) + "\n"


def install_roles(project: Path, provider: str, specs=None):
    """Write provider role files under the project. Existing files are never overwritten."""
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError(f"대상 폴더가 없습니다: {project}")
    models = parse_models(specs)
    roles = load_roles()
    planned, warnings = [], []
    if provider == "claude":
        if any(effort for _, effort in models.values()):
            raise ValueError("Claude Code 역할 파일에는 추론 수준을 지정하지 않습니다. 모델만 적으세요.")
        if "top" in models:
            warnings.append("Claude Code는 호출할 때 지정한 모델이 역할 파일보다 우선하므로 최상위 등급은 파일에 넣지 않았습니다.")
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
            warnings.append("모델을 지정하지 않아 [agents] 기본값이나 부모 세션 모델을 물려받는 역할: "
                            + ", ".join(inherited))
    else:
        raise ValueError("provider는 claude 또는 codex여야 합니다.")
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


def install(parent: Path, name="agent-work-kit"):
    """Create parent/name with the kit. Never overwrites: existing records stay untouched."""
    if not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("폴더 이름에는 경로 구분자를 넣지 마세요.")
    parent = Path(parent).resolve()
    if not parent.is_dir():
        raise ValueError(f"대상 폴더가 없습니다: {parent}")
    target = parent / name
    if target.exists():
        raise ValueError(f"{target}이(가) 이미 있습니다. 작성한 기록을 보존하려면 "
                         "--name으로 다른 폴더에 설치한 뒤 비교해 반영하세요.")
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
