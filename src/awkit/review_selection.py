"""Selection rules shared by collection and the current-folder preview."""

import fnmatch
import hashlib
import os
import re
import stat
import sys
import tomllib
from pathlib import Path


def classify(base, path, source=None):
    """Return (relative name, shared stat, skipped), or None for an ignored match.

    Keep copied and shared collection rules distinct. Callers own enumeration,
    duplicate handling and payload access; this function reads only metadata.
    """
    name = path.relative_to(base).as_posix()
    if ".git" in path.relative_to(base).parts:
        return None
    if source is None:
        if any(p.is_symlink() for p in [path, *path.parents] if p != base.parent) \
                or not path.resolve().is_relative_to(base) or not path.is_file():
            return (name, None, True) if path.is_file() or path.is_symlink() else None
        return name, None, False

    from .artifact_store import ArtifactCollision, linked, relative
    try:
        parts = relative(name).parts
    except ValueError as exc:
        raise ArtifactCollision([name], "Artifact path is not portable") from exc
    if any(linked(source.info("/".join(parts[:index]))) for index in range(1, len(parts) + 1)):
        return name, None, True
    info = source.info(name)
    return (name, info, False) if stat.S_ISREG(info.st_mode) else None


def candidates(source, pattern):
    """Enumerate one glob using metadata only; never descend through a link.

    Collectors retain Path.glob. This bounded preview traversal uses its segment
    matching and platform case convention, but exposes I/O errors that glob hides.
    A linked branch has unknown contents and is reported without following it.
    """
    from .artifact_store import linked
    parts = pattern.split("/")
    if sys.version_info < (3, 13) and any("**" in part and part != "**" for part in parts):
        raise ValueError("Invalid pattern: '**' can only be an entire path component on this Python.")
    found, skipped, errors, visited = {}, [], [], set()

    def issue(name, operation, exc):
        errors.append(dict(path=name or ".", operation=operation, message=str(exc)))

    def entries(name, segment):
        # SafeRoot pins/anchors ordinary parents. The unused leaf is never created.
        probe = name + "/.awkit-preview" if name else ".awkit-preview"
        # Path.glob uses regex IGNORECASE on Windows, including Unicode ranges;
        # fnmatch.fnmatch's normcase would silently omit some of those names.
        matches = re.compile(fnmatch.translate(segment), re.IGNORECASE if os.name == "nt" else 0).match
        try:
            with source.parent(probe) as (path, parent):
                with os.scandir(path.parent if parent is None else parent) as stream:
                    for entry in stream:
                        if entry.name == ".git" or not matches(entry.name):
                            continue
                        child = name + "/" + entry.name if name else entry.name
                        try:
                            target = path.parent / entry.name if parent is None else entry.name
                            yield child, os.stat(target, dir_fd=parent, follow_symlinks=False)
                        except OSError as exc:
                            issue(child, "stat", exc)
        except (OSError, ValueError) as exc:
            if isinstance(exc, ValueError):
                skipped.append(dict(path=name or ".", reason="unsafe-metadata-branch", scope="branch"))
            issue(name, "enumerate", exc)

    def visit(name, index, info):
        if (name, index) in visited:
            return
        visited.add((name, index))
        if index == len(parts):
            found[name] = info
            return
        if linked(info):
            skipped.append(dict(path=name, reason="linked-branch", scope="branch"))
            issue(name, "enumerate", "Linked branch was not traversed; descendant matches are unknown.")
            return
        if not stat.S_ISDIR(info.st_mode):
            return
        part = parts[index]
        if part == "**":
            visit(name, index + 1, info)
            for child, child_info in entries(name, "*"):
                if index == len(parts) - 1 and sys.version_info >= (3, 13):
                    found[child] = child_info
                visit(child, index, child_info)
        elif sys.version_info[:2] == (3, 12) or any(char in part for char in "*?["):
            # Python 3.12 glob enumerates literal segments too: spelling and
            # Windows Unicode matches come from directory entries, not lookup.
            for child, child_info in entries(name, part):
                visit(child, index + 1, child_info)
        else:
            child = name + "/" + part if name else part
            if ".git" in child.split("/"):
                return
            try:
                child_info = source.info(child)
            except FileNotFoundError:
                return  # An exact configured path need not exist before checks.
            except (OSError, ValueError) as exc:
                if isinstance(exc, ValueError):
                    skipped.append(dict(path=child, reason="unsafe-metadata-path", scope="path"))
                issue(child, "stat", exc)
                return
            visit(child, index + 1, child_info)

    try:
        visit("", 0, source.root.lstat())
    except OSError as exc:
        issue("", "stat", exc)
    return found, skipped, errors


def preview(repo, config):
    """Observe the current working folder, without running or retaining evidence."""
    from .artifact_store import SafeRoot, distinct, fingerprint, linked, relative
    from .review import git, located, validate_settings
    base, config = Path(repo).resolve(), Path(config).resolve()
    top, subdir = located(base)
    raw = config.read_bytes()
    settings = tomllib.loads(raw.decode("utf-8"))
    *_, patterns, required = validate_settings(settings)
    mode = settings.get("artifact_storage", "copy")
    source = SafeRoot(base)
    report = dict(schema=1, kind="artifact-selection-preview", base=str(base), repository=str(top), subdir=subdir,
                  head=git(top, "rev-parse", "HEAD"), config=str(config), config_sha256=hashlib.sha256(raw).hexdigest(),
                  artifact_storage=mode, scope="current-working-tree-before-checks", complete=True,
                  files=[], patterns=[], unmatched_optional=[], unmatched_required=[], skipped=[], errors=[],
                  limits=["Observed paths may include untracked or ignored files absent from a later snapshot.",
                          "Setup and checks may generate or change files; current missing matches do not predict check failure.",
                          "Logical stat bytes cover observed distinct paths, not allocated space or content sharing.",
                          "This observation establishes no evidence completeness or consumer compatibility."])
    selected = {}
    for pattern in dict.fromkeys(patterns + required):
        observed, skipped, errors = candidates(source, pattern)
        matches = []
        for name, info in sorted(observed.items()):
            path = base / name
            if linked(info):
                skipped.append(dict(path=name, reason="linked-path", scope="path"))
                continue
            if name:
                try:
                    relative(name)
                except ValueError as exc:
                    skipped.append(dict(path=name, reason="nonportable-path", scope="path"))
                    errors.append(dict(path=name, operation="stat", message=str(exc)))
                    continue
            try:
                if not name and mode == "copy":
                    continue  # Bare ** also yields the root directory.
                if name:
                    current = source.info(name)
                    if linked(current) or fingerprint(current) != fingerprint(info):
                        raise ValueError("Path changed during observation.")
                    if not stat.S_ISREG(info.st_mode):
                        continue
                # Preview's ordinary portable paths use anchored metadata in
                # either mode. Copied collection retains its legacy classifier.
                candidate = classify(base, path, source)
                if candidate is None:
                    raise ValueError("Path stopped being an ordinary file during observation.")
                selected_name, shared_info, excluded = candidate
                if excluded:
                    raise ValueError("Path became linked during observation.")
                if fingerprint(shared_info) != fingerprint(info):
                    raise ValueError("Path changed during observation.")
                if selected_name not in selected:
                    selected[selected_name] = dict(path=selected_name, size=shared_info.st_size, patterns=[])
                selected[selected_name]["patterns"].append(pattern)
                matches.append(selected_name)
            except (OSError, ValueError) as exc:
                errors.append(dict(path=name or ".", operation="select", message=str(exc)))
        entry = dict(pattern=pattern, optional=pattern in patterns, required=pattern in required,
                     match_count=len(matches), matches=matches, complete=not errors)
        report["patterns"].append(entry)
        if not matches:
            if entry["optional"]:
                report["unmatched_optional"].append(pattern)
            if entry["required"]:
                report["unmatched_required"].append(pattern)
        report["skipped"].extend(dict(item, pattern=pattern) for item in skipped)
        report["errors"].extend(dict(item, pattern=pattern) for item in errors)
    if mode == "shared":
        try:
            distinct([*selected, "manifest.json"])
        except ValueError as exc:
            report["errors"].append(dict(path=None, operation="selection-collision", message=str(exc),
                                         paths=getattr(exc, "paths", [])))
    report["files"] = [selected[name] for name in sorted(selected)]
    report["complete"] = not report["errors"]
    report["totals"] = dict(files=len(selected), logical_bytes=sum(item["size"] for item in selected.values()),
                            complete=report["complete"])
    report["status"] = "complete" if report["complete"] else "partial"
    report["skipped"].sort(key=lambda item: (item["pattern"], item["path"], item["reason"]))
    return report


def text(report):
    """Render the observation and its limits without implying a check result."""
    lines = ["Artifact selection preview: " + report["status"], "Scope: current working tree, before setup and checks",
             "Base: " + report["base"], "Configuration: " + report["config"],
             "Configuration SHA-256: " + report["config_sha256"], "Storage mode: " + report["artifact_storage"],
             f"Observed selection{' (partial totals)' if not report['complete'] else ''}: "
             f"{report['totals']['files']} files, {report['totals']['logical_bytes']} logical bytes"]
    for item in report["patterns"]:
        origins = ", ".join(key for key in ("optional", "required") if item[key])
        coverage = "" if item["complete"] else "; partial observation"
        lines.append(f"Pattern {item['pattern']} ({origins}): {item['match_count']} matches{coverage}")
    shown = sorted(report["files"], key=lambda item: (-item["size"], item["path"]))[:20]
    lines.append(f"Largest selected files: showing {len(shown)} of {len(report['files'])}; --json lists every path and pattern association")
    lines.extend(f"  {item['size']} bytes  {item['path']}" for item in shown)
    for key, label in (("unmatched_optional", "Currently unmatched optional"),
                       ("unmatched_required", "Currently unmatched required")):
        lines.extend(label + ": " + pattern for pattern in report[key])
    lines.extend(f"Skipped {item['path']} ({item['reason']}; pattern {item['pattern']})" for item in report["skipped"])
    lines.extend(f"Incomplete {item['path'] or '.'} ({item['operation']}): {item['message']}" for item in report["errors"])
    lines.extend("Limit: " + limit for limit in report["limits"])
    return "\n".join(lines)
