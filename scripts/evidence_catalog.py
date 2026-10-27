"""Index development evidence without moving it or interpreting it as acceptance."""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = ("handoffs", "reviews", "workspaces")
REFERENCE = re.compile(r"\.awkit/(handoffs|reviews|workspaces)/([^/`<>\s)\\]+)")


def linked(path):
    """Include Windows junctions; do not traverse reparse points."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def safe_path(root, path):
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if linked(current):
            raise ValueError("linked path")
    return path


def record_for(source):
    if source.startswith("docs/history/tasks/"):
        return source.replace("docs/history/", "docs/", 1)
    if source == "docs/history/document-workflow-plan.md":
        return "docs/document-workflow-plan.md"
    return source


def inventory(root, path):
    result = {"availability": "present", "kind": "directory", "files": 0, "bytes": 0, "runs": [], "issues": []}

    def issue(target, error):
        result["issues"].append({"path": target.relative_to(root).as_posix(), "error": error})

    try:
        safe_path(root, path)
        if path.is_file():
            result.update(kind="file", files=1, bytes=path.stat().st_size)
            return result
        if not path.is_dir():
            raise NotADirectoryError(path)
    except FileNotFoundError:
        result["availability"] = "missing"
        return result
    except (OSError, ValueError) as exc:
        result["availability"] = "unreadable" if isinstance(exc, OSError) else "linked"
        issue(path, type(exc).__name__)
        return result

    def walk_error(error):
        issue(Path(error.filename), type(error).__name__)

    for directory, directories, files in os.walk(path, followlinks=False, onerror=walk_error):
        parent = Path(directory)
        for name in list(directories):
            target = parent / name
            try:
                if linked(target):
                    directories.remove(name)
                    issue(target, "linked; skipped")
            except OSError as exc:
                directories.remove(name)
                issue(target, type(exc).__name__)
        for name in sorted(files):
            target = parent / name
            try:
                if linked(target):
                    issue(target, "linked; skipped")
                    continue
                result["files"] += 1
                result["bytes"] += target.stat().st_size
                if name != "result.json" or parent.parent.name != "reviews" or not parent.name.startswith("review-"):
                    continue
                data = json.loads(target.read_text(encoding="utf-8-sig"))
                if not isinstance(data, dict):
                    raise ValueError("expected an object")
                status = data.get("status")
                snapshot = data.get("snapshot")
                result["runs"].append({
                    "path": target.relative_to(root).as_posix(),
                    "recorded_status": status if status in ("passed", "failed", "running") else "unknown",
                    "snapshot": snapshot if isinstance(snapshot, str) and re.fullmatch(r"[0-9a-f]{40}", snapshot) else None,
                })
            except (OSError, ValueError) as exc:
                issue(target, type(exc).__name__)
    if result["issues"]:
        result["availability"] = "partial"
    result["runs"].sort(key=lambda run: run["path"])
    result["issues"].sort(key=lambda error: error["path"])
    return result


def catalogue(root):
    root = root.resolve()
    references = {}
    documents = {}
    issues = []
    for path in sorted((root / "docs").rglob("*.md")):
        source = path.relative_to(root).as_posix()
        try:
            safe_path(root, path)
            content = path.read_bytes()
            documents[source] = hashlib.sha256(content).hexdigest()
            for store, name in REFERENCE.findall(content.decode("utf-8")):
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
                    continue
                group = f".awkit/{store}/{name}"
                references.setdefault(group, set()).add((record_for(source), source))
        except (OSError, ValueError) as exc:
            issues.append({"path": source, "error": type(exc).__name__})
    groups = set(references)
    for store in STORES:
        path = root / ".awkit" / store
        try:
            safe_path(root, path)
            for child in path.iterdir():
                # Include linked entries so they are visible as skipped collections.
                if linked(child) or child.is_dir() or child.is_file():
                    groups.add(child.relative_to(root).as_posix())
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as exc:
            issues.append({"path": path.relative_to(root).as_posix(), "error": type(exc).__name__})
    collections = []
    for group in sorted(groups):
        refs = references.get(group, set())
        collections.append({
            "path": group,
            "records": sorted({record for record, _ in refs}),
            "references": [{"record": record, "source": source} for record, source in sorted(refs)],
            **inventory(root, root / group),
        })
    revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    return {
        "schema": 1,
        "revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "documents": documents,
        "scope": "Local collection availability and document references; recorded run statuses are not revalidated.",
        "collections": collections,
        "issues": issues,
    }


def markdown(data):
    def link(path):
        return f"[{path}](../../{path})"

    lines = ["# Local evidence catalogue", "", data["scope"], "",
             f"Checkout revision: `{data['revision']}`. Document hashes are in `catalog.json`.", "",
             "Rebuild with `python scripts/evidence_catalog.py`. Missing, partial or linked locations require inspection.",
             "An unreferenced collection is retained; this list does not authorize cleanup.", "", "## By record", ""]
    records = sorted({record for group in data["collections"] for record in group["records"]})
    for record in records:
        lines.extend([f"### {record}", "", f"Read {link(record)}.", ""])
        for group in data["collections"]:
            if record in group["records"]:
                lines.append(f"- {link(group['path'])}: {group['availability']}")
        lines.append("")
    lines.extend(["## Collections", "", "| Collection | Availability | Files | Bytes | References |",
                  "|---|---|---:|---:|---|"])
    for group in data["collections"]:
        refs = f"{len(group['records'])} records" if group["records"] else "unreferenced"
        lines.append(f"| {link(group['path'])} | {group['availability']} | {group['files']} | {group['bytes']} | {refs} |")
    lines.extend(["", "## Recorded review results", "", "These statuses were read from disk. Process activity, current validity and acceptance remain unchecked.", ""])
    for group in data["collections"]:
        for run in group["runs"]:
            lines.append(f"- {link(run['path'])}: `{run['recorded_status']}`, snapshot `{run['snapshot']}`")
    lines.extend(["", "## Inspection issues", ""])
    errors = data["issues"] + [issue for group in data["collections"] for issue in group["issues"]]
    lines.extend(f"- `{issue['path']}`: {issue['error']}" for issue in errors)
    if not errors:
        lines.append("No inspection errors recorded.")
    return "\n".join(lines) + "\n"


def write_catalogue(root, data):
    destination = root / ".awkit" / "evidence"
    # Refuse linked parents or outputs instead of writing outside the local store.
    for path in (root / ".awkit", destination):
        try:
            safe_path(root, path)
        except FileNotFoundError:
            path.mkdir()
    for name, content in (("catalog.json", json.dumps(data, indent=2) + "\n"), ("index.md", markdown(data))):
        path = destination / name
        try:
            safe_path(root, path)
        except FileNotFoundError:
            pass
        path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository checkout to inspect")
    args = parser.parse_args()
    root = args.root.resolve()
    data = catalogue(root)
    write_catalogue(root, data)
    print(json.dumps({"collections": len(data["collections"]), "documents": len(data["documents"]),
                      "inspection_issues": len(data["issues"]) + sum(len(group["issues"]) for group in data["collections"]),
                      "output": str(root / ".awkit/evidence/index.md")}))


if __name__ == "__main__":
    main()
