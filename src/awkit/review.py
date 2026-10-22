"""Freeze explicitly selected changes and check a fixed Git object in isolation."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import tomllib

from .pipeline import atomic_json
from .process import run_to_files


def git(repo, *args, env=None):
    result = subprocess.run(["git", "-C", str(repo), *args], env=env,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git 명령에 실패했습니다.")
    return result.stdout.strip()


def relative_file(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or any(p.lower() in ("", ".", "..", ".git") for p in value.split("/"))
            or "\\" in value or ":" in value or "\x00" in value):
        raise ValueError(f"프로젝트 안의 파일 경로를 지정하세요: {value}")
    return path


def relative_directory(value):
    if not isinstance(value, str):
        raise ValueError("cwd에는 worktree 기준 상대경로를 문자열로 지정하세요.")
    return PurePosixPath(".") if value == "." else relative_file(value)


def snapshot(repo, paths):
    repo = Path(git(repo, "rev-parse", "--show-toplevel"))
    parent = git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if not paths:
        raise ValueError("포함할 변경 파일을 지정하세요.")
    for name in paths:
        rel = relative_file(name)
        target = repo / rel
        if target.is_dir() or any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
                                  for p in [target, *target.parents] if p != repo.parent):
            raise ValueError(f"디렉터리나 연결 파일은 포함할 수 없습니다: {name}")
        if not target.resolve().is_relative_to(repo.resolve()):
            raise ValueError("저장소 밖의 파일입니다.")
        if not target.exists() and not git(repo, "ls-files", "--error-unmatch", "--", name):
            raise ValueError(f"파일을 찾을 수 없습니다: {name}")
    with tempfile.TemporaryDirectory(prefix="awkit-index-") as temporary:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        env["GIT_LITERAL_PATHSPECS"] = "1"
        env.update(GIT_AUTHOR_NAME="Agent Work Kit", GIT_AUTHOR_EMAIL="snapshot@localhost",
                   GIT_COMMITTER_NAME="Agent Work Kit", GIT_COMMITTER_EMAIL="snapshot@localhost")
        git(repo, "read-tree", parent, env=env)
        git(repo, "add", "-A", "--", *paths, env=env)
        tree = git(repo, "write-tree", env=env)
        return git(repo, "commit-tree", tree, "-p", parent, "-m", "Review snapshot", env=env)


def check(repo, revision, config, runs_root=None, keep=False):
    if not re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", revision):
        raise ValueError("검사할 Git commit의 전체 식별자를 지정하세요.")
    repo = Path(git(repo, "rev-parse", "--show-toplevel"))
    commit = git(repo, "rev-parse", "--verify", revision + "^{commit}")
    raw = Path(config).read_bytes()
    settings = tomllib.loads(raw.decode("utf-8"))
    if type(settings.get("schema")) is not int or settings["schema"] != 1:
        raise ValueError("검사 설정의 schema는 1이어야 합니다.")
    timeout = settings.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400:
        raise ValueError("제한 시간은 0초 초과, 86400초 이하여야 합니다.")
    checks, setup = settings.get("checks"), settings.get("setup", [])
    if not isinstance(checks, list) or not checks or not isinstance(setup, list):
        raise ValueError("checks에 검사 명령을 하나 이상 지정하세요.")
    names = set()
    for step in setup + checks:
        if not isinstance(step, dict):
            raise ValueError("각 검사 단계를 표로 지정하세요.")
        name, argv = step.get("name"), step.get("argv")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("각 단계에 서로 다른 이름을 지정하세요.")
        names.add(name)
        if not isinstance(argv, list) or not argv or any(not isinstance(s, str) for s in argv):
            raise ValueError("명령은 문자열 인자 배열이어야 합니다.")
        relative_directory(step.get("cwd", "."))
    custom_env = settings.get("env", {})
    if not isinstance(custom_env, dict) or any(not isinstance(v, str) for v in custom_env.values()):
        raise ValueError("env에는 문자열 값을 지정하세요.")
    root = Path(runs_root or Path(tempfile.gettempdir()) / "agent-work-kit-reviews").resolve()
    root.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="review-", dir=root))
    worktree = run / "worktree"
    result = {"snapshot": commit, "config_sha256": hashlib.sha256(raw).hexdigest(),
              "run_dir": str(run), "worktree": str(worktree), "status": "running", "steps": []}
    def save():
        atomic_json(run / "result.json", result)
    values = {"{worktree}": str(worktree), "{run_dir}": str(run), "{run_id}": run.name,
              "{python}": sys.executable}
    def expand(value):
        for key, replacement in values.items():
            value = value.replace(key, replacement)
        return value
    env = os.environ.copy()
    env.update({key: expand(value) for key, value in custom_env.items()})
    env.update(AWKIT_WORKTREE=str(worktree), AWKIT_RUN_DIR=str(run), AWKIT_RUN_ID=run.name)
    added = False
    preserve = keep
    save()
    try:
        git(repo, "worktree", "add", "--detach", str(worktree), commit)
        added = True
        for index, step in enumerate(setup + checks):
            step_dir = worktree / relative_directory(step.get("cwd", "."))
            entry = {"name": step["name"], "cwd": str(step_dir), "phase": "setup" if index < len(setup) else "check",
                     "log": f"{index + 1:02d}.log", "argv": [expand(s) for s in step["argv"]]}
            result["steps"].append(entry)
            with (run / entry["log"]).open("wb") as log:
                try:
                    # Resolve after preceding setup steps, which may create this directory.
                    resolved_dir = step_dir.resolve()
                    if not resolved_dir.is_relative_to(worktree.resolve()):
                        raise ValueError("cwd가 worktree 밖을 가리킵니다.")
                    if not resolved_dir.is_dir():
                        raise ValueError("cwd 디렉터리가 없습니다: " + str(step_dir))
                    entry["cwd"] = str(resolved_dir)
                    returncode = run_to_files(entry["argv"], cwd=resolved_dir, env=env,
                                              stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                    entry.update(exit_code=returncode,
                                 status="passed" if returncode == 0 else "failed")
                except subprocess.TimeoutExpired:
                    entry["status"] = "timeout"
                    preserve = True
                except (OSError, ValueError) as exc:
                    entry.update(status="failed", error=str(exc))
            save()
            if entry["status"] == "timeout" or (index < len(setup) and entry["status"] != "passed"):
                break
        result["status"] = "passed" if (len(result["steps"]) == len(setup + checks)
            and all(s["status"] == "passed" for s in result["steps"])) else "failed"
        if any(s["status"] == "timeout" for s in result["steps"]):
            result["status"] = "uncertain"
    except BaseException:
        preserve = True
        result["status"] = "uncertain"
        raise
    finally:
        if added and not preserve:
            try:
                git(repo, "worktree", "remove", "--force", str(worktree))
            except ValueError as exc:
                result.update(status="cleanup-failed", cleanup_error=str(exc))
        result["worktree_retained"] = worktree.exists()
        save()
    return result
