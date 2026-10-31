"""Read existing review stores without changing evidence or trusting declared hashes."""

import hashlib
import json
import os
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from .artifact_store import STORE, metadata, store_descriptor

CATEGORIES = ("artifacts", "worktree", "records", "other")
STORE_CATEGORIES = ("objects", "staging", "metadata", "other")
STATUSES = {"running", "passed", "failed", "uncertain", "cleanup-failed"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


def _linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _identity(info):
    return info.st_dev, info.st_ino


def _issue(issues, path, code, detail):
    issues.append(dict(path=path, code=code, detail=detail))


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON number")


def _path(value):
    return (isinstance(value, str) and bool(value) and "\\" not in value
            and ":" not in value and "\0" not in value and not value.startswith("/")
            and all(part not in {"", ".", ".."} for part in value.split("/"))
            and PurePosixPath(value).as_posix() == value)


def _walk(root, issues):
    """Return regular-file stats; do not descend through symlinks or Windows reparse points."""
    files, directories = {}, {}

    def visit(folder):
        relative = folder.relative_to(root).as_posix()
        try:
            before = folder.lstat()
            if _linked(before) or not stat.S_ISDIR(before.st_mode):
                _issue(issues, relative, "skipped-link", "Directory is linked or changed type.")
                return
            with os.scandir(folder) as entries:
                names = sorted(entry.name for entry in entries)
            after = folder.lstat()
            if _linked(after) or _identity(before) != _identity(after):
                _issue(issues, relative, "changed-directory", "Directory changed during inspection.")
                return
            directories[relative] = after
        except (OSError, RecursionError) as exc:
            _issue(issues, relative, "scan-error", str(exc))
            return
        for name in names:
            child = folder / name
            relative = child.relative_to(root).as_posix()
            try:
                current = folder.lstat()
                if _linked(current) or _identity(current) != _identity(before):
                    _issue(issues, folder.relative_to(root).as_posix(), "changed-directory", "Directory changed before entry inspection.")
                    return
                info = child.lstat()
                current = folder.lstat()
                if _linked(current) or _identity(current) != _identity(before):
                    _issue(issues, folder.relative_to(root).as_posix(), "changed-directory", "Directory changed during entry inspection.")
                    return
                if _linked(info):
                    _issue(issues, relative, "skipped-link", "Linked or reparse entry was not followed.")
                elif stat.S_ISDIR(info.st_mode):
                    visit(child)
                elif stat.S_ISREG(info.st_mode):
                    files[relative] = info
                else:
                    _issue(issues, relative, "skipped-special", "Entry is not a regular file or directory.")
            except (OSError, RecursionError) as exc:
                _issue(issues, relative, "stat-error", str(exc))

    visit(root)
    return files, directories


def _parents(root, relative, directories):
    parent = root
    for part in (None, *PurePosixPath(relative).parts[:-1]):
        if part is not None:
            parent /= part
        expected = directories.get(parent.relative_to(root).as_posix())
        current = parent.lstat()
        if expected is None or _linked(current) or _identity(current) != _identity(expected):
            raise ValueError("Metadata directory changed during inspection.")


def _read(root, relative, files, directories, *, raw=False):
    """Read only an already inventoried regular metadata file; detect replacements before reading."""
    expected = files.get(relative)
    if expected is None:
        raise ValueError("Metadata is missing or was not safely inventoried.")
    path = root / relative
    _parents(root, relative, directories)
    current = path.lstat()
    if _linked(current) or _identity(current) != _identity(expected):
        raise ValueError("Metadata file changed during inspection.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if not stat.S_ISREG(actual.st_mode) or _identity(actual) != _identity(expected):
            raise ValueError("Metadata file was replaced before reading.")
        if (actual.st_size, actual.st_mtime_ns) != (expected.st_size, expected.st_mtime_ns):
            raise ValueError("Metadata file changed since its size was observed.")
        _parents(root, relative, directories)
        data = stream.read()
        final = os.fstat(stream.fileno())
        if (actual.st_size, actual.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
            raise ValueError("Metadata changed while reading.")
    return data if raw else json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant)


def _metadata(root, relative, files, directories, issues, *, captures=None):
    try:
        raw = _read(root, relative, files, directories, raw=True)
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant)
        if not isinstance(data, dict):
            raise ValueError("Metadata must be an object.")
        if captures is not None:
            captures[relative] = raw
        return data
    except (OSError, ValueError, RecursionError) as exc:
        _issue(issues, relative, "invalid-metadata", str(exc))
        return None


def _result_valid(result, name):
    return (result is not None and isinstance(result.get("snapshot"), str)
            and REVISION.fullmatch(result["snapshot"])
            and isinstance(result.get("config_sha256"), str) and HEX.fullmatch(result["config_sha256"])
            and isinstance(result.get("run_dir"), str)
            and (("artifact_export" in result and isinstance(result.get("run_id"), str)
                  and re.fullmatch(r"review-[A-Za-z0-9_-]+", result["run_id"]))
                 or result["run_dir"].replace("\\", "/").rstrip("/").split("/")[-1] == name)
            and isinstance(result.get("status"), str) and result["status"] in STATUSES)


def _manifest_valid(manifest, result, name):
    return (manifest is not None and type(manifest.get("schema")) is int and manifest["schema"] == 1
            and manifest.get("run_id") == name
            and manifest.get("snapshot") == result["snapshot"]
            and manifest.get("config_sha256") == result["config_sha256"]
            and manifest.get("subdir") == result.get("subdir")
            and isinstance(manifest.get("files"), dict))


def _shared_store(root):
    folder = root / STORE
    issues, objects = [], {}
    report = dict(path=STORE, present=False, descriptor="absent", collection_id=None,
                  observed={name: dict(bytes=0, files=0) for name in STORE_CATEGORIES}, issues=issues)
    try:
        info = folder.lstat()
    except FileNotFoundError:
        return report, objects
    except OSError as exc:
        _issue(issues, STORE, "stat-error", str(exc))
        return report, objects
    report["present"] = True
    if _linked(info) or not stat.S_ISDIR(info.st_mode):
        _issue(issues, STORE, "invalid-store", "Shared store is linked or is not a directory.")
        report["descriptor"] = "invalid"
        if not _linked(info) and stat.S_ISREG(info.st_mode):
            report["observed"]["other"] = dict(bytes=info.st_size, files=1)
        return report, objects
    files, directories = _walk(folder, issues)
    for relative, info in files.items():
        first = relative.split("/", 1)[0]
        category = first if first in {"objects", "staging"} and "/" in relative else (
            "metadata" if relative == "store.json" else "other")
        report["observed"][category]["bytes"] += info.st_size
        report["observed"][category]["files"] += 1
        if category == "objects":
            name = relative.removeprefix("objects/")
            if HEX.fullmatch(name):
                objects[name] = info
            else:
                _issue(issues, relative, "invalid-object-name", "Object entry is not a direct SHA-256 name.")
    descriptor = _metadata(folder, "store.json", files, directories, issues)
    try:
        if descriptor is None:
            raise ValueError("Shared store descriptor is unavailable.")
        report["collection_id"] = store_descriptor(descriptor)
        report["descriptor"] = "valid"
    except ValueError as exc:
        report["descriptor"] = "invalid"
        _issue(issues, "store.json", "invalid-store", str(exc))
    if "objects" not in directories:
        _issue(issues, "objects", "invalid-store", "Shared object directory is missing or was not safely inventoried.")
    return report, objects


def _shared_declarations(folder, manifest, raw_manifest, result, files, directories, store, objects):
    collection_id = metadata(manifest, result)
    if hashlib.sha256(raw_manifest).hexdigest() != result["artifact_publication"]["manifest_sha256"]:
        raise ValueError("Published shared manifest changed.")
    config = _read(folder, "config.toml", files, directories, raw=True)
    if hashlib.sha256(config).hexdigest() != result["config_sha256"]:
        raise ValueError("Retained check configuration changed.")
    if result["status"] == "running":
        raise ValueError("Shared run has not finished publication.")
    if store["descriptor"] != "valid" or store["collection_id"] != collection_id:
        raise ValueError("Shared store is unavailable or belongs to another collection.")
    return [(name, entry, "shared", objects.get(entry["sha256"]))
            for name, entry in sorted(manifest["files"].items())] + [
                (name, entry, "local", files.get("artifacts/" + name))
                for name, entry in sorted(manifest["local_files"].items())]


def _export_metadata(folder, files, directories, captures):
    from .review_export import EXPORT_METADATA, ORIGINAL_MANIFEST, export_metadata
    raw = {name: None if name == ORIGINAL_MANIFEST and name not in files and name not in directories
           else captures[name] if name in captures else _read(folder, name, files, directories, raw=True)
           for name in EXPORT_METADATA}
    return export_metadata(raw)


def _managed_path(name):
    if os.name != "nt":
        return name
    parts = name.split("/")
    if parts[0].casefold() in {"artifacts", "worktree", "result.json", "config.toml"}:
        parts[0] = parts[0].casefold()
    if len(parts) == 2 and parts[0] == "artifacts" and parts[1].casefold() == "manifest.json":
        parts[1] = "manifest.json"
    return "/".join(parts)


def _managed_index(entries, issues):
    result, aliases = {}, set()
    for name, value in entries.items():
        key = _managed_path(name)
        if key in result or key in aliases:
            result.pop(key, None)
            aliases.add(key)
            _issue(issues, name, "ambiguous-managed-name", "Multiple observed paths alias the same managed name.")
        else:
            result[key] = value
    return result


def _run(folder, store, objects):
    issues = []
    files, directories = _walk(folder, issues)
    observed = {name: dict(bytes=0, files=0) for name in CATEGORIES}
    for relative, info in files.items():
        relative = _managed_path(relative)
        first = relative.split("/", 1)[0]
        category = first if first in {"artifacts", "worktree"} and "/" in relative else (
            "records" if relative in {"result.json", "config.toml"} or re.fullmatch(r"\d+\.log", relative) else "other")
        observed[category]["bytes"] += info.st_size
        observed[category]["files"] += 1
    observed["total_bytes"] = sum(observed[name]["bytes"] for name in CATEGORIES)
    observed["total_files"] = sum(observed[name]["files"] for name in CATEGORIES)
    files, directories = _managed_index(files, issues), _managed_index(directories, issues)
    captures = {}
    result = _metadata(folder, "result.json", files, directories, issues, captures=captures)
    valid_result = _result_valid(result, folder.name)
    if result is not None and not valid_result:
        _issue(issues, "result.json", "invalid-result", "Invalid run identity, revision, configuration hash or status.")
    payloads = {name[len("artifacts/"):]: info for name, info in files.items()
                if name.startswith("artifacts/") and name != "artifacts/manifest.json"}
    manifest_present = "artifacts/manifest.json" in files
    has_artifacts = ("artifacts" in directories or manifest_present or payloads
                     or (valid_result and ("artifacts" in result or "artifact_export" in result
                                           or result.get("artifact_storage") == "shared")))
    manifest = _metadata(folder, "artifacts/manifest.json", files, directories, issues, captures=captures) if has_artifacts else None
    shared = bool((result and result.get("artifact_storage") == "shared") or (manifest and manifest.get("schema") == 2))
    exported = bool(result is not None and "artifact_export" in result)
    entries = []
    valid_manifest = bool(valid_result and not shared and not exported and _manifest_valid(manifest, result, folder.name))
    if exported and valid_result and manifest is not None:
        try:
            _export_metadata(folder, files, directories, captures)
            valid_manifest = True
        except (OSError, ValueError, RecursionError) as exc:
            _issue(issues, "result.json", "invalid-export-metadata", str(exc))
    elif shared and valid_result and manifest is not None:
        try:
            entries = _shared_declarations(folder, manifest, captures["artifacts/manifest.json"], result,
                                           files, directories, store, objects)
            valid_manifest = True
        except (OSError, ValueError, RecursionError) as exc:
            _issue(issues, "artifacts/manifest.json", "invalid-shared-metadata", str(exc))
    if manifest is not None and not valid_manifest:
        _issue(issues, "artifacts/manifest.json", "invalid-manifest", "Manifest schema or run identity does not match result.json.")
    declarations = []
    declared_paths = set()
    if valid_manifest:
        if not shared:
            entries = [(name, entry, "local", payloads.get(name)) for name, entry in sorted(manifest["files"].items())]
        for name, entry, source, info in entries:
            if (not _path(name) or not isinstance(entry, dict) or type(entry.get("size")) is not int
                    or entry["size"] < 0 or not isinstance(entry.get("sha256"), str) or not HEX.fullmatch(entry["sha256"])):
                _issue(issues, "artifacts/manifest.json", "invalid-declaration", "Invalid artifact path, size or SHA-256: " + name)
                continue
            if source == "local":
                declared_paths.add(name)
            eligible = info is not None and info.st_size == entry["size"]
            if not eligible:
                _issue(issues, "artifacts/" + name, "artifact-size-unavailable", "Declared artifact is missing, skipped or has another size.")
            declarations.append(dict(path=name, size=entry["size"], sha256=entry["sha256"], eligible=eligible, source=source))
        for name in sorted(payloads.keys() - declared_paths):
            _issue(issues, "artifacts/" + name, "unrecorded-artifact", "Observed artifact has no valid declaration.")
    status = result.get("status") if result and isinstance(result.get("status"), str) else None
    report = dict(name=folder.name, recorded_status=status, observed=observed,
                  metadata=dict(result="valid" if valid_result else "invalid",
                                manifest="valid" if valid_manifest else "invalid" if has_artifacts else "absent",
                                storage="shared" if shared else "copy",
                                exported=exported,
                                declared_files=len(declarations), declared_payload_bytes=sum(d["size"] for d in declarations)),
                  shared_references=dict(declared_files=sum(d["source"] == "shared" for d in declarations),
                                         declared_payload_bytes=sum(d["size"] for d in declarations if d["source"] == "shared")),
                  issues=issues)
    return report, declarations


def inspect(root, *, default=False):
    """Inspect direct review-* directories. `root` is selected once; metadata never selects paths."""
    try:
        root = Path(root).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Cannot resolve review storage root: {exc}") from exc
    report = dict(schema=2, root=str(root), selection="direct review-* directories and collection-local shared store", status="complete", complete=True,
                  observed={name: dict(bytes=0, files=0) for name in CATEGORIES}, runs=[], largest_runs=[], issues=[],
                  manifests=dict(valid_runs=0, declared_files=0, declared_payload_bytes=0, counted_files=0,
                                 counted_payload_bytes=0, unique_recorded_hashes=0, unique_recorded_payload_bytes=0,
                                 duplicate_declared_bytes=0, conflicting_hashes=[]),
                  limits=["Logical file sizes, not allocated disk usage or recoverable space.",
                          "Recorded payload hashes are unverified; payloads were not read or rehashed.",
                          "Live filesystem inspection is not an atomic snapshot.",
                          "Unreferenced objects are relative to valid readable manifests, not proven reclaimable bytes."])
    try:
        info = root.stat()
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Review storage root is not a directory.")
    except FileNotFoundError as exc:
        if not default:
            raise ValueError(f"Review storage root does not exist: {root}") from exc
        report["status"] = "absent"
        names = []
    except OSError as exc:
        raise ValueError(f"Cannot inspect review storage root: {root}: {exc}") from exc
    if report["status"] != "absent":
        try:
            with os.scandir(root) as entries:
                names = sorted(entry.name for entry in entries if entry.name.startswith("review-"))
            current = root.lstat()
            if _linked(current) or _identity(current) != _identity(info):
                raise ValueError("Review storage root changed during inspection.")
        except OSError as exc:
            raise ValueError(f"Cannot inspect review storage root: {root}: {exc}") from exc
    store, objects = _shared_store(root)
    report["shared_store"] = store
    candidates = []
    sizes = defaultdict(set)
    for name in names:
        folder = root / name
        try:
            info = folder.lstat()
            if _linked(info):
                _issue(report["issues"], name, "skipped-link", "Linked or reparse run was not followed.")
                continue
            if not stat.S_ISDIR(info.st_mode):
                continue
        except OSError as exc:
            _issue(report["issues"], name, "stat-error", str(exc))
            continue
        run, declarations = _run(folder, store, objects)
        report["runs"].append(run)
        candidates.append((run, declarations))
        for entry in declarations:
            sizes[entry["sha256"]].add(entry["size"])
    conflicts = sorted(key for key, values in sizes.items() if len(values) > 1)
    report["manifests"]["conflicting_hashes"] = conflicts
    unique = {}
    references = set()
    for run, declarations in candidates:
        counted = []
        for entry in declarations:
            if entry["source"] == "shared":
                references.add(entry["sha256"])
            if entry["sha256"] in conflicts:
                _issue(run["issues"], "artifacts/" + entry["path"], "conflicting-hash-size", "Recorded hash has conflicting sizes; all its declarations are excluded.")
            elif entry["eligible"]:
                counted.append(entry)
                unique[entry["sha256"]] = entry["size"]
        run["metadata"].update(counted_files=len(counted), counted_payload_bytes=sum(d["size"] for d in counted))
        run["shared_references"].update(counted_files=sum(d["source"] == "shared" for d in counted),
                                         counted_payload_bytes=sum(d["size"] for d in counted if d["source"] == "shared"))
        run["complete"] = not run["issues"]
        run["issues"].sort(key=lambda issue: (issue["path"], issue["code"], issue["detail"]))
        for category in CATEGORIES:
            for key in ("bytes", "files"):
                report["observed"][category][key] += run["observed"][category][key]
        report["manifests"]["valid_runs"] += run["metadata"]["manifest"] == "valid"
        for key in ("declared_files", "declared_payload_bytes", "counted_files", "counted_payload_bytes"):
            report["manifests"][key] += run["metadata"][key]
    report["manifests"]["unique_recorded_hashes"] = len(unique)
    report["manifests"]["unique_recorded_payload_bytes"] = sum(unique.values())
    report["manifests"]["duplicate_declared_bytes"] = report["manifests"]["counted_payload_bytes"] - sum(unique.values())
    report["observed"]["total_bytes"] = sum(report["observed"][c]["bytes"] for c in CATEGORIES)
    report["observed"]["total_files"] = sum(report["observed"][c]["files"] for c in CATEGORIES)
    for field in ("bytes", "files"):
        store["observed"]["total_" + field] = sum(store["observed"][c][field] for c in STORE_CATEGORIES)
    report["collection_observed"] = {"total_" + field: report["observed"]["total_" + field] + store["observed"]["total_" + field]
                                     for field in ("bytes", "files")}
    unreferenced = sorted(objects.keys() - references)
    store["unreferenced_objects"] = dict(hashes=unreferenced, files=len(unreferenced),
                                         bytes=sum(objects[name].st_size for name in unreferenced))
    store["referenced_objects"] = dict(files=len(objects.keys() & references),
                                       bytes=sum(objects[name].st_size for name in objects.keys() & references))
    report["run_count"] = len(report["runs"])
    report["metadata_coverage"] = dict(valid_results=sum(run["metadata"]["result"] == "valid" for run in report["runs"]),
                                       valid_manifests=report["manifests"]["valid_runs"],
                                       artifactless_runs=sum(run["metadata"]["result"] == "valid" and run["metadata"]["manifest"] == "absent"
                                                             for run in report["runs"]))
    report["recorded_status_counts"] = dict(sorted(Counter(run["recorded_status"] or "unknown" for run in report["runs"]).items()))
    report["largest_runs"] = [dict(name=run["name"], bytes=run["observed"]["total_bytes"])
                              for run in sorted(report["runs"], key=lambda run: (-run["observed"]["total_bytes"], run["name"]))[:10]]
    report["issues"].sort(key=lambda issue: (issue["path"], issue["code"], issue["detail"]))
    store["issues"].sort(key=lambda issue: (issue["path"], issue["code"], issue["detail"]))
    report["complete"] = not report["issues"] and not store["issues"] and all(run["complete"] for run in report["runs"])
    store["reference_coverage_complete"] = report["complete"] and all(run["recorded_status"] != "running" for run in report["runs"])
    store["reference_scope"] = "Valid readable manifests in the selected direct review-* directories."
    if not report["complete"]:
        report["status"] = "partial"
    return report


def _size(value):
    if value < 1024:
        return f"{value} bytes"
    unit = 1
    for label in ("KiB", "MiB", "GiB", "TiB", "PiB"):
        unit *= 1024
        if value < unit * 1024 or label == "PiB":
            scaled = (value * 100 + unit // 2) // unit
            return f"{value} bytes ({scaled // 100}.{scaled % 100:02d} {label})"


def _issue_summary(report):
    counts = Counter()
    affected = defaultdict(set)
    for scope, issues in (("collection", report["issues"]), ("shared store", report["shared_store"]["issues"])):
        counts.update((scope, issue["code"]) for issue in issues)
    for run in report["runs"]:
        for issue in run["issues"]:
            counts["runs", issue["code"]] += 1
            affected[issue["code"]].add(run["name"])
    total = sum(counts.values())
    run_count = len(set().union(*affected.values()))
    lines = [f"Issues: {total}; runs with run-scoped issues: {run_count}. Counts are classifications, not causes."]
    for (scope, code), count in sorted(counts.items()):
        suffix = f"; affected runs: {len(affected[code])}" if scope == "runs" else ""
        noun = "issue" if count == 1 else "issues"
        lines.append(f"  {scope} / {code}: {count} {noun}{suffix}")
    lines.extend([f"Individual issue details: {total} omitted.",
                  "For full rows and issue paths/details, omit --summary or use --json."])
    return lines


def text(report, *, summary=False):
    lines = [f"Review storage: {report['root']}", f"Inspection: {report['status']}; runs: {report['run_count']}",
             f"Observed run-local logical size: {_size(report['observed']['total_bytes'])}",
             f"Observed collection logical size: {_size(report['collection_observed']['total_bytes'])}"]
    status_items = report["recorded_status_counts"].items()
    statuses = ", ".join(f"{name}={count}" for name, count in (sorted(status_items) if summary else status_items)) or "none"
    lines.append("Recorded statuses: " + statuses)
    for category in CATEGORIES:
        value = report["observed"][category]
        lines.append(f"  {category}: {_size(value['bytes'])}; files: {value['files']}")
    store = report["shared_store"]
    lines.append(f"Shared store: {store['descriptor']}; reference coverage complete: {str(store['reference_coverage_complete']).lower()}")
    for category in STORE_CATEGORIES:
        value = store["observed"][category]
        lines.append(f"  shared {category}: {_size(value['bytes'])}; files: {value['files']}")
    unreferenced = store["unreferenced_objects"]
    lines.append(f"Objects unreferenced by valid readable manifests (not proven reclaimable): {_size(unreferenced['bytes'])}; files: {unreferenced['files']}")
    if summary:
        count = sum(run["metadata"]["storage"] == "shared" for run in report["runs"])
        lines.append(f"Shared logical references per run: {count} rows omitted.")
    else:
        lines.append("Shared logical references per run:")
        for run in report["runs"]:
            if run["metadata"]["storage"] == "shared":
                lines.append(f"  {run['name']}: declared {_size(run['shared_references']['declared_payload_bytes'])}; "
                             f"counted {_size(run['shared_references']['counted_payload_bytes'])}")
    manifests = report["manifests"]
    coverage = report["metadata_coverage"]
    lines.extend([f"Metadata coverage: valid results={coverage['valid_results']}, valid manifests={coverage['valid_manifests']}, artifactless runs={coverage['artifactless_runs']}",
                  f"Manifest-declared payload: {_size(manifests['declared_payload_bytes'])}",
                  f"Counted manifest payload: {_size(manifests['counted_payload_bytes'])}",
                  f"Unique recorded hash size (unverified): {_size(manifests['unique_recorded_payload_bytes'])}",
                  f"Duplicate declared size (not recoverable space): {_size(manifests['duplicate_declared_bytes'])}"])
    if summary:
        lines.append(f"Largest runs: {len(report['largest_runs'])} rows omitted.")
        lines.extend(_issue_summary(report))
    else:
        lines.append("Largest runs:")
        for run in report["largest_runs"]:
            lines.append(f"  {run['name']}: {_size(run['bytes'])}")
        for issue in report["issues"]:
            lines.append(f"issue {issue['path']}: {issue['code']}: {issue['detail']}")
        for issue in store["issues"]:
            lines.append(f"issue {STORE}/{issue['path']}: {issue['code']}: {issue['detail']}")
        for run in report["runs"]:
            for issue in run["issues"]:
                lines.append(f"issue {run['name']}/{issue['path']}: {issue['code']}: {issue['detail']}")
    lines.extend(report["limits"])
    return "\n".join(lines)
