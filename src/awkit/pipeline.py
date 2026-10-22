"""Release orchestration; project commands are explicit trusted adapters."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .process import run_to_files

RELEASE = re.compile(r"[0-9a-f]{7,64}\Z")
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
PHASES = ("preflight", "backup", "deploy", "verify", "rollback")
# A previous run ended in a state the controller cannot vouch for.
BLOCKING = ("running", "uncertain", "rollback-failed", "failed-unrecovered")
HISTORY_LIMIT = 50


class StepError(RuntimeError):
    def __init__(self, phase, reason, code=1, uncertain=False, report=None):
        super().__init__(f"{phase}: {reason}")
        self.phase, self.code, self.uncertain, self.report = phase, code, uncertain, report


def stamp():
    return datetime.now(UTC).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Pipeline:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        with self.config_path.open("rb") as handle:
            config = tomllib.load(handle)
        settings = config["pipeline"]
        if config.get("schema_version") != 1:
            raise ValueError("The configuration needs schema_version = 1.")
        self.project = self.config_path.parent
        self.target = settings["target"]
        if not isinstance(self.target, str) or not LABEL.fullmatch(self.target):
            raise ValueError("target may contain letters, digits, dots, underscores and hyphens only.")
        self.timeout = settings.get("timeout_seconds", 120)
        if type(self.timeout) not in (int, float) or not 0 < self.timeout <= 86400:
            raise ValueError("timeout_seconds must be above 0 and at most 86400.")
        self.auto_rollback = settings.get("auto_rollback", False)
        if type(self.auto_rollback) is not bool:
            raise ValueError("auto_rollback must be true or false.")
        self.required_checks = settings["required_checks"]
        if (not isinstance(self.required_checks, list) or not self.required_checks
                or not all(isinstance(name, str) and LABEL.fullmatch(name)
                           for name in self.required_checks)
                or len(set(self.required_checks)) != len(self.required_checks)):
            raise ValueError("required_checks must list distinct check names.")
        self.state = (self.project / settings.get("state_dir", ".awkit/releases")).resolve()
        self.commands = config["commands"]
        for phase in PHASES:
            argv = self.commands.get(phase)
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) and v for v in argv):
                raise ValueError(f"The {phase} command must be a non-empty array of strings.")
            for arg in argv:
                self.expand(arg, "a" * 40, "b" * 40, Path("run"))

    def expand(self, arg, release, previous, run_dir):
        values = {"python": sys.executable, "project": str(self.project), "target": self.target,
                  "release": release or "", "previous": previous or "", "run_dir": str(run_dir)}
        # Only named, literal placeholders; arbitrary braces remain valid argv characters.
        for token in re.findall(r"\{([a-z_]+)\}", arg):
            if token not in values:
                raise ValueError(f"Unknown command placeholder: {token}")
        return re.sub(r"\{([a-z_]+)\}", lambda match: values[match[1]], arg)

    @contextmanager
    def locked(self):
        self.state.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.state / "lock.sqlite3", timeout=0)
        try:
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                raise ValueError("Another run holds the lock on this state folder.") from exc
            yield
        finally:
            conn.rollback()
            conn.close()

    # -- running adapter commands -------------------------------------------------

    def _execute(self, phase, args, log_dir, number):
        """Run one adapter command with output in files, so stray children cannot hang us."""
        log_dir.mkdir(parents=True, exist_ok=True)
        out_path = log_dir / f"{number:02d}-{phase}.stdout.log"
        err_path = log_dir / f"{number:02d}-{phase}.stderr.log"
        with out_path.open("wb") as out, err_path.open("wb") as err:
            returncode = run_to_files(args, cwd=self.project, stdout=out, stderr=err,
                                      timeout=self.timeout)
        stdout = out_path.read_text(encoding="utf-8", errors="replace")
        return returncode, stdout, out_path, err_path

    def call(self, phase, release=None, previous=None, run_dir=None, events=None):
        args = [self.expand(arg, release, previous, run_dir or self.state)
                for arg in self.commands[phase]]
        started = time.monotonic()
        event = {"phase": phase, "started_at": stamp()}
        number = len(events) + 1 if events is not None else 1
        temporary = None
        if run_dir is None:
            temporary = tempfile.TemporaryDirectory(prefix="awkit-")
            log_dir = Path(temporary.name)
        else:
            log_dir = Path(run_dir) / "logs"
        try:
            returncode, stdout, out_path, err_path = self._execute(phase, args, log_dir, number)
            event["returncode"] = returncode
            if run_dir is not None:
                event["stdout"] = str(out_path.relative_to(run_dir))
                event["stderr"] = str(err_path.relative_to(run_dir))
            if returncode:
                raise StepError(phase, "command failed", returncode)
            return stdout
        except subprocess.TimeoutExpired:
            event["timeout"] = True
            raise StepError(phase, "timed out", uncertain=True) from None
        except OSError:
            raise StepError(phase, "command could not start") from None
        finally:
            event["seconds"] = round(time.monotonic() - started, 3)
            if events is not None:
                events.append(event)
            if temporary is not None:
                temporary.cleanup()

    # -- reading adapter reports --------------------------------------------------

    def preflight(self, **kwargs):
        raw = self.call("preflight", **kwargs)
        try:
            data = json.loads(raw)
            if data["target"] != self.target:
                raise ValueError()
            current = data["release"]
            if current is not None and (not isinstance(current, str) or not RELEASE.fullmatch(current)):
                raise ValueError()
            return current
        except (ValueError, KeyError, TypeError):
            raise StepError("preflight", "could not read the target or its current release") from None

    def inspect(self, expected=None, phase="verify", **kwargs):
        """Return the verifier's report, healthy or not. Malformed reports raise StepError."""
        raw = self.call("verify", release=expected, **kwargs)
        try:
            data = json.loads(raw)
            release = data["release"]
            checks = data["checks"]
            if data["target"] != self.target or not isinstance(release, str) or not RELEASE.fullmatch(release):
                raise ValueError()
            if expected and release != expected:
                raise ValueError()
            if not isinstance(checks, list) or not checks:
                raise ValueError()
            clean, names = [], set()
            for check in checks:
                name, ok = check["name"], check["ok"]
                if not isinstance(name, str) or not LABEL.fullmatch(name) or name in names:
                    raise ValueError()
                if type(ok) is not bool:
                    raise ValueError()
                names.add(name)
                clean.append({"name": name, "ok": ok})
            if not set(self.required_checks).issubset(names):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise StepError(phase, "target, release or check report does not match") from None
        failed = [check["name"] for check in clean if not check["ok"]]
        return {"target": self.target, "release": release, "checks": clean,
                "healthy": not failed, "failed_checks": failed}

    def verify(self, expected=None, phase="verify", **kwargs):
        report = self.inspect(expected, phase=phase, **kwargs)
        if not report["healthy"]:
            raise StepError(phase, "checks failed: " + ", ".join(report["failed_checks"]),
                            report=report)
        return report

    # -- local state ---------------------------------------------------------------

    def last(self):
        path = self.state / "last-run.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "status" not in data:
            raise ValueError("The last-run record is unreadable.")
        return data

    def history(self):
        """Releases that passed verification on this target, oldest first."""
        path = self.state / "history.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            releases = data.get("releases") if isinstance(data, dict) else None
            if (not isinstance(releases, list)
                    or not all(isinstance(r, str) and RELEASE.fullmatch(r) for r in releases)):
                raise ValueError("The release history file is unreadable.")
            return releases
        # State written by 0.1.0 has no history file; recover what the last run knew.
        last = self.last()
        if last and last.get("status") == "passed":
            if last.get("action") == "rollback":
                return [last["release"]]
            return [r for r in (last.get("previous"), last.get("release")) if r]
        return []

    def _settle(self, release):
        """Record that `release` is live and healthy; drop anything newer than it."""
        releases = self.history()
        if release in releases:
            releases = releases[:releases.index(release) + 1]
        else:
            releases.append(release)
        releases = releases[-HISTORY_LIMIT:]
        atomic_json(self.state / "history.json", {"releases": releases, "updated_at": stamp()})
        return releases

    @staticmethod
    def _rollback_target(releases, current):
        if current in releases:
            releases = releases[:releases.index(current)]
        candidates = [r for r in releases if r != current]
        return candidates[-1] if candidates else None

    # -- actions ---------------------------------------------------------------------

    def reconcile(self):
        """Record what is actually live after an interrupted or failed run."""
        with self.locked():
            run_id = uuid.uuid4().hex
            run_dir = self.state / "runs" / run_id
            run_dir.mkdir(parents=True)
            events = []
            current = self.preflight(run_dir=run_dir, events=events)
            if not current:
                raise ValueError("The target has no current release, so reconcile cannot confirm it.")
            report = self.inspect(current, run_dir=run_dir, events=events)
            record = {"run_id": run_id, "action": "reconcile",
                      "status": "reconciled" if report["healthy"] else "reconciled-unhealthy",
                      "at": stamp(), "release": current, "target": self.target,
                      "verification": report, "events": events}
            previous = self.last()
            if previous:
                record["previous_run_id"] = previous.get("run_id")
            if report["healthy"]:
                self._settle(current)
            atomic_json(run_dir / "result.json", record)
            atomic_json(self.state / "last-run.json", record)
            return record

    def run(self, action, release=None, allow_unhealthy_current=False):
        if action not in ("deploy", "rollback"):
            raise ValueError("Unsupported action.")
        if action == "deploy" and (not isinstance(release, str) or not RELEASE.fullmatch(release)):
            raise ValueError("deploy needs a release ID of 7 to 64 lowercase hex characters.")
        if action == "rollback" and release:
            raise ValueError("rollback does not take a release.")
        with self.locked():
            last = self.last()
            if last and last["status"] in BLOCKING:
                raise ValueError("The previous run left the target unconfirmed. Inspect the target, then run reconcile.")
            releases = self.history()
            if action == "rollback" and not releases:
                raise ValueError("No earlier healthy release to roll back to.")
            run_id = uuid.uuid4().hex
            run_dir = self.state / "runs" / run_id
            run_dir.mkdir(parents=True)
            record = {"run_id": run_id, "action": action, "release": release, "target": self.target,
                      "started_at": stamp(), "status": "running", "events": []}
            atomic_json(self.state / "last-run.json", record)
            atomic_json(run_dir / "result.json", record)
            current, changed, current_healthy = None, False, None
            try:
                current = self.preflight(run_dir=run_dir, events=record["events"])
                record["previous"] = current
                if current:
                    report = self.inspect(current, phase="verify-current",
                                          run_dir=run_dir, events=record["events"])
                    current_healthy = report["healthy"]
                    record["current_health"] = {"healthy": current_healthy,
                                                "failed_checks": report["failed_checks"]}
                if action == "rollback":
                    release = self._rollback_target(releases, current)
                    record["release"] = release
                    if not release:
                        raise StepError("preflight", "no healthy release before the current one in the history")
                elif current_healthy is False and not allow_unhealthy_current:
                    raise StepError("verify-current", "the current release fails its checks; "
                                    "pass --allow-unhealthy-current to deploy a fix")
                if current == release and current_healthy is not False:
                    record["outcome"] = "already-current"
                else:
                    self.call("backup", release, current, run_dir, record["events"])
                    changed = True
                    self.call("deploy" if action == "deploy" else "rollback",
                              release, current, run_dir, record["events"])
                    if action == "rollback":
                        record["outcome"] = "rolled-back"
                    else:
                        record["outcome"] = "redeployed" if current == release else "deployed"
                record["verification"] = self.verify(release, run_dir=run_dir, events=record["events"])
                record["status"] = "passed"
                self._settle(release)
            except StepError as exc:
                record["failure"] = {"phase": exc.phase, "code": exc.code, "uncertain": exc.uncertain}
                if exc.report:
                    record["failure"]["failed_checks"] = exc.report["failed_checks"]
                record["status"] = "failed"
                if changed and exc.uncertain:
                    record["status"] = "uncertain"
                elif changed and current and self.auto_rollback and current_healthy is False:
                    # Rolling back to a version that was already failing would not restore anything.
                    record["recovery"] = {"skipped": "current-unhealthy"}
                    record["status"] = "failed-unrecovered"
                elif changed and current and self.auto_rollback:
                    try:
                        self.call("rollback", current, release, run_dir, record["events"])
                        record["recovery"] = self.verify(current, run_dir=run_dir, events=record["events"])
                        record["status"] = "failed-restored"
                    except StepError as recovery:
                        record["status"] = "uncertain" if recovery.uncertain else "rollback-failed"
                elif changed:
                    record["status"] = "failed-unrecovered"
            except BaseException:
                record["status"] = "uncertain" if changed else "failed"
                raise
            finally:
                record["finished_at"] = stamp()
                atomic_json(run_dir / "result.json", record)
                atomic_json(self.state / "last-run.json", record)
            return record
