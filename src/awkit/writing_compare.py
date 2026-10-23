"""Compare complete-file writing findings from two explicit, read-only Git revisions."""

import difflib
import hashlib
import importlib.metadata
import json
import marshal
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import __version__, checks


def _git(repo, *args):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args],
                            capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip() or "Git command failed")
    return result.stdout


def _commit(repo, revision):
    if not isinstance(revision, str) or not revision or "\0" in revision:
        raise ValueError("A nonempty explicit Git revision is required")
    value = _git(repo, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ValueError("The revision did not resolve to one commit")
    return value


def _paths(paths):
    valid, errors = [], []
    for raw in paths:
        name = str(raw)
        parts = name.split("/")
        if (not name or "\\" in name or any(ord(c) < 32 for c in name)
                or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
                or any(p in ("", ".", "..") for p in parts)
                or PurePosixPath(name).suffix.lower() != ".md"):
            errors.append({"scope": "selection", "path": name,
                           "message": "Select a repository-relative Markdown file path without traversal"})
        elif name in valid:
            errors.append({"scope": "selection", "path": name, "message": "Selected paths must be unique"})
        else:
            valid.append(name)
    if not valid:
        errors.append({"scope": "selection", "message": "Select at least one Markdown file"})
    return valid, errors


def _checker_identity(backend):
    module = Path(checks.__file__).resolve()
    identity = {"name": "awkit.checks.check_text", "package_version": __version__,
                "module": str(module), "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
                "loaded_function_sha256": hashlib.sha256(marshal.dumps(backend.__code__)).hexdigest(),
                "python": sys.version, "interpreter": sys.executable, "origin": {"kind": "unknown"}}
    checkout = module.parents[2]
    if module == checkout / "src/awkit/checks.py" and (checkout / "pyproject.toml").is_file():
        try:
            commit = _commit(checkout, "HEAD")
            committed = _git(checkout, "show", commit + ":src/awkit/checks.py")
            identity["origin"] = {"kind": "checkout", "commit": commit,
                                  "module_matches_commit_after_crlf_normalization":
                                  committed.replace(b"\r\n", b"\n") == module.read_bytes().replace(b"\r\n", b"\n")}
        except (OSError, ValueError):
            identity["origin"] = {"kind": "checkout", "commit": None}
    else:
        try:
            dist = importlib.metadata.distribution("agent-work-kit")
            if Path(dist.locate_file("awkit/checks.py")).resolve() == module:
                metadata = json.loads(dist.read_text("direct_url.json") or "{}")
                revision = metadata.get("vcs_info", {}).get("commit_id")
                identity["origin"] = {"kind": "installation", "metadata_commit": revision
                                      if isinstance(revision, str) and re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", revision)
                                      else None}
        except (importlib.metadata.PackageNotFoundError, OSError, ValueError, TypeError, AttributeError):
            pass
    return identity


def _side(repo, commit, paths, label, backend):
    report = {"files": 0, "errors": 0, "warnings": 0, "findings": [], "ok": True}
    state = {"status": "error" if commit is None else "no-files", "sources": [],
             "report": report, "errors": [], "exit_code": None}
    documents = {}
    if commit is None:
        state["errors"].append({"scope": label, "message": "Selected revision is unavailable"})
        return state, documents
    for name in paths:
        source = {"path": name, "state": "error"}
        state["sources"].append(source)
        try:
            raw = _git(repo, "--literal-pathspecs", "ls-tree", "-z", commit, "--", name)
            if not raw:
                source["state"] = "absent"
                continue
            entries = [part for part in raw.split(b"\0") if part]
            if len(entries) != 1:
                raise ValueError("The selected path is not one regular blob")
            head, _, actual = entries[0].partition(b"\t")
            mode, kind, oid = head.decode("ascii").split()
            if actual.decode("utf-8") != name or kind != "blob" or mode not in ("100644", "100755"):
                raise ValueError("Select a regular Markdown blob, not a directory, link or submodule")
            data = _git(repo, "cat-file", "blob", oid)
            source.update(blob=oid, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            text = data.decode("utf-8")
            if "\0" in text:
                raise ValueError("NUL-containing Markdown input is unsupported")
            source.update(state="present", encoding="utf-8")
            documents[name] = {"text": text, "lines": text.splitlines(), "sha256": source["sha256"]}
            report["files"] += 1
            for finding in backend(text):
                finding = {**finding, "path": name}
                report["findings"].append(finding)
                report["errors" if finding["level"] == "error" else "warnings"] += 1
        except (OSError, ValueError, UnicodeError) as exc:
            state["errors"].append({"scope": label, "path": name, "message": str(exc)})
    report["ok"] = not report["errors"]
    if state["errors"]:
        state["status"] = "error"
    else:
        state["status"] = "complete" if report["files"] else "no-files"
        state["exit_code"] = int(not report["ok"])
    return state, documents


def _occurrences(documents, report, label):
    rows, ordinals = [], Counter()
    patterns = {name: pattern for name, pattern, _ in (*checks.ERRORS, *checks.WARNINGS)}
    for index, raw in enumerate(report["findings"]):
        path, line, pattern = raw["path"], raw["line"], raw["pattern"]
        document = documents[path]
        prose = dict(checks._prose_lines(document["text"]))
        key = (path, line, pattern, raw["level"])
        ordinal = ordinals[key]
        ordinals[key] += 1
        if pattern == "mixed-endings":
            witness = {"scope": "whole-document", "contributing_lines": [
                {"line": n, "text": text, "polite": bool(checks.POLITE.search(text)),
                 "formal": bool(checks.FORMAL.search(text))}
                for n, text in prose.items() if checks.POLITE.search(text) or checks.FORMAL.search(text)]}
        else:
            matches = list(patterns[pattern].finditer(prose.get(line, ""))) if pattern in patterns else []
            witness = {"scope": "unavailable"}
            if ordinal < len(matches):
                match = matches[ordinal]
                witness = {"scope": "line-local", "line": line,
                           "raw_line": document["lines"][line - 1], "column_start": match.start() + 1,
                           "column_end_exclusive": match.end() + 1, "column_unit": "Unicode code points",
                           "ordinal_in_line_pattern": ordinal}
        rows.append({"id": f"{label}:{index}", "raw_index": index, "finding": raw, "witness": witness})
    return rows


def _correspondence(base, current, before, after, unavailable):
    old = _occurrences(base, before["report"], "baseline")
    rows = _occurrences(current, after["report"], "candidate")
    old_files, new_files = defaultdict(list), defaultdict(list)
    for row in old:
        old_files[row["finding"]["path"]].append(row)
    for row in rows:
        new_files[row["finding"]["path"]].append(row)
    paired, pending = set(), []
    for row in rows:
        finding = row["finding"]
        path = finding["path"]
        peers = [x for x in old_files[path] if x["finding"]["pattern"] == finding["pattern"]
                 and x["finding"]["level"] == finding["level"]]
        row["baseline_occurrence"] = None
        if unavailable:
            status, reason = "unclassified", "Comparison evidence is unavailable; retain the current finding"
        elif path not in base:
            status, reason = "unclassified", "Path absent in baseline; same-path correspondence is unavailable"
        elif base[path]["sha256"] == current[path]["sha256"]:
            ordinal = new_files[path].index(row)
            partner = old_files[path][ordinal]
            if partner["finding"] == finding and partner["id"] not in paired:
                paired.add(partner["id"])
                row["baseline_occurrence"] = partner["id"]
                status, reason = "existing", "Identical full file bytes and checker; same occurrence ordinal"
            else:
                status, reason = "unclassified", "Identical input produced inconsistent occurrence evidence"
        elif row["witness"]["scope"] == "whole-document":
            status, reason = (("unclassified", "Whole-document input changed; equal summaries do not prove correspondence")
                              if peers else ("introduced", "Complete baseline has no finding of this whole-document rule"))
        elif row["witness"]["scope"] != "line-local":
            status, reason = "unclassified", "The checker supplies no supported occurrence witness"
        else:
            text = row["witness"]["raw_line"]
            if base[path]["lines"].count(text) == current[path]["lines"].count(text) == 1:
                previous_line = base[path]["lines"].index(text) + 1
                matching = [x for x in peers if x["finding"]["line"] == previous_line]
                ordinal = row["witness"]["ordinal_in_line_pattern"]
                row["correspondence_evidence"] = {"baseline_line": previous_line,
                    "candidate_line": finding["line"], "unique_unchanged_line": True,
                    "baseline_line_checked_as_prose": previous_line in dict(checks._prose_lines(base[path]["text"]))}
                if ordinal < len(matching) and matching[ordinal]["id"] not in paired:
                    partner = matching[ordinal]
                    paired.add(partner["id"])
                    row["baseline_occurrence"] = partner["id"]
                    status, reason = "existing", "Unique unchanged line and matching rule occurrence span/order"
                elif not matching:
                    status, reason = "introduced", "Mapped line has no baseline finding; full-file context exposes the occurrence"
                else:
                    status, reason = "unclassified", "Occurrence correspondence is not one-to-one"
            else:
                pending.append((row, peers))
                continue
        row.update(classification=status, reason=reason)
    for row, peers in pending:
        row["potential_baseline_occurrences"] = [x["id"] for x in peers if x["id"] not in paired]
        if row["potential_baseline_occurrences"]:
            status, reason = "unclassified", "Changed or duplicate line with unresolved baseline occurrences"
        else:
            status, reason = "introduced", "Baseline rule occurrences are absent or already reliably paired"
        row.update(classification=status, reason=reason)
    inventory = []
    for row in old:
        raw = row["finding"]
        unknown = [x["id"] for x in rows if x["classification"] == "unclassified"
                   and x["finding"]["path"] == raw["path"] and x["finding"]["pattern"] == raw["pattern"]]
        state = ("paired" if row["id"] in paired else "unclassified" if unavailable or unknown else
                 "absent-at-selected-path" if raw["path"] not in current else "absent-in-candidate-report")
        inventory.append({**row, "correspondence": state, "possible_candidate_occurrences": unknown})
    return rows, inventory


def _display_lines(text):
    """Normalize the checker's recognized separators for display, preserving an absent terminator."""
    result = []
    for line in text.splitlines(keepends=True):
        if line.endswith("\r\n"):
            result.append(line[:-2] + "\n")
        elif line[-1:] in "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029":
            result.append(line[:-1] + "\n")
        else:
            result.append(line)
    return result


def _source_diff(name, before, after):
    rows = difflib.unified_diff(_display_lines(before), _display_lines(after),
                                fromfile="baseline/" + name, tofile="candidate/" + name)
    return "".join(row if row.endswith("\n") else row + "\n\\ No newline at end of file\n" for row in rows)


def compare_writing(repo, baseline, candidate, paths):
    """Return a format-1 report. Existing writing APIs, file contents and the Git index stay unchanged."""
    backend = checks.check_text
    names, errors = _paths(paths)
    inputs = {"repo": str(repo), "baseline": {"requested": baseline, "commit": None},
              "candidate": {"requested": candidate, "commit": None}, "paths": names}
    identity = None
    try:
        identity = _checker_identity(backend)
    except (OSError, ValueError) as exc:
        errors.append({"scope": "checker", "message": str(exc)})
    try:
        top = _git(repo, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        inputs["repo"] = top
        for label, revision in (("baseline", baseline), ("candidate", candidate)):
            try:
                inputs[label]["commit"] = _commit(top, revision)
            except (OSError, ValueError, UnicodeError) as exc:
                errors.append({"scope": label, "message": str(exc)})
    except (OSError, ValueError, UnicodeError) as exc:
        errors.append({"scope": "repository", "message": str(exc)})
    sides, documents = {}, {}
    for label in ("baseline", "candidate"):
        sides[label], documents[label] = _side(inputs["repo"], inputs[label]["commit"], names, label, backend)
        errors.extend(sides[label]["errors"])
    for name in names:
        states = [next((s["state"] for s in sides[label]["sources"] if s["path"] == name), "error")
                  for label in ("baseline", "candidate")]
        if states == ["absent", "absent"]:
            errors.append({"scope": "selection", "path": name, "message": "Path absent in both selected revisions"})
    invalid_scope = any(x["scope"] in ("selection", "repository") for x in errors)
    if invalid_scope:
        for side in sides.values():
            side["status"], side["exit_code"] = "error", None
    for side in sides.values():
        side["report_scope"] = "readable selected files only" if side["status"] == "error" else "all selected present files"
    rows, inventory = _correspondence(documents["baseline"], documents["candidate"],
                                    sides["baseline"], sides["candidate"], bool(errors))
    counts = Counter(row["classification"] for row in rows)
    changes = []
    for name in names:
        old, new = documents["baseline"].get(name), documents["candidate"].get(name)
        if old and new:
            diff = _source_diff(name, old["text"], new["text"])
            if diff:
                changes.append({"path": name, "diff": diff})
        elif old or new:
            states = {}
            for label in ("baseline", "candidate"):
                source = next((s["state"] for s in sides[label]["sources"] if s["path"] == name), "error")
                states[label] = "read" if name in documents[label] else "absent" if source == "absent" else "unavailable"
            changes.append({"path": name, **states})
    status = "error" if errors else "complete-with-unclassified" if counts["unclassified"] else "complete"
    return {"format": 1, "comparison_status": status, "inputs": inputs, "checker": identity,
            "full_file": sides, "candidate_occurrences": rows, "baseline_inventory": inventory,
            "changed_regions_display_only": changes,
            "reading_order": [row["id"] for row in sorted(rows, key=lambda r: (
                {"introduced": 0, "unclassified": 1, "existing": 2}[r["classification"]], r["raw_index"]))],
            "summary": {"candidate_occurrences_observed": len(rows),
                "candidate_occurrences_exact": None if sides["candidate"]["status"] == "error" else len(rows),
                "baseline_occurrences_exact": None if sides["baseline"]["status"] == "error" else len(inventory),
                "confirmed_existing": counts["existing"], "confirmed_introduced": counts["introduced"],
                "unclassified": counts["unclassified"],
                "introduced_total_exact": None if errors or counts["unclassified"] else counts["introduced"]},
            "errors": errors, "exit_code": 2 if errors else sides["candidate"]["exit_code"]}


def render_comparison(report):
    """Candidate status and changed/uncertain evidence first, with both full reports retained."""
    candidate = report["full_file"]["candidate"]
    raw = candidate["report"]
    state = ("unavailable (readable subset below)" if candidate["status"] == "error" else
             "no file checked" if candidate["status"] == "no-files" else
             "blocked" if raw["errors"] else "no errors")
    lines = [f"Candidate full-file check: {state}; {raw['files']} files, {raw['errors']} errors, {raw['warnings']} warnings",
             f"Comparison: {report['comparison_status']}"]
    for label in ("baseline", "candidate"):
        lines.append(f"{label}: {report['inputs'][label]['commit'] or 'unavailable'}")
    summary = report["summary"]
    exact = summary["introduced_total_exact"]
    lines.append(f"Confirmed introduced: {summary['confirmed_introduced']}; unclassified: {summary['unclassified']}; "
                 f"existing: {summary['confirmed_existing']}; exact introduced total: {exact if exact is not None else 'unknown'}")
    for error in report["errors"]:
        lines.append(f"error ({error['scope']}): {error.get('path', '')} {error['message']}")
    lookup = {row["id"]: row for row in report["candidate_occurrences"]}
    for title, existing in (("Introduced and unclassified findings", False), ("Existing findings", True)):
        lines.append("\n" + title + ":")
        for identity in report["reading_order"]:
            row = lookup[identity]
            if (row["classification"] == "existing") == existing:
                f = row["finding"]
                lines.append(f"[{row['classification']} {identity}] {f['path']}:{f['line']} {f['level']} "
                             f"[{f['pattern']}] {f['advice']}" + (f": {f['text']}" if f["text"] else ""))
                lines.append("  " + row["reason"])
        if not existing:
            lines.append("\nChanged source regions (display only; alignment does not prove correspondence):")
            for change in report["changed_regions_display_only"]:
                lines.append(change.get("diff") or f"{change['path']}: {change['baseline']} -> {change['candidate']}")
    lines.append("\nBaseline inventory (absence does not establish accepted correction):")
    for row in report["baseline_inventory"]:
        f = row["finding"]
        lines.append(f"{row['id']} {f['path']}:{f['line']} [{f['pattern']}] {row['correspondence']}")
    for label in ("baseline", "candidate"):
        side = report["full_file"][label]
        lines.append(f"\nFull {label} report ({side['status']}; {side['report_scope']}):")
        lines.append(checks.render_writing(side["report"]))
    lines.append("Scope: mechanical findings in selected frozen paths. Correspondence establishes no acceptance, "
                 "document quality or resolved findings. The selected baseline remains fixed.")
    return "\n".join(lines)
