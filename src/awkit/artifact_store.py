"""Owned content-addressed payloads and checked access to retained evidence."""

from __future__ import annotations

import hashlib
import os
import stat
import uuid
from pathlib import Path

from .artifact_paths import (  # noqa: F401  (moved; importers keep working)
    COLLECTION,
    DEVICE,
    HEX,
    STORE,
    ArtifactCollision,
    SafeRoot,
    _constant,
    _pairs,
    _windows_directory,
    declaration,
    decode,
    distinct,
    encode,
    fingerprint,
    identity,
    linked,
    metadata,
    relative,
    store_descriptor,
    valid_entry,
)
from .export_format import validate_export
from .review_selection import classify


class ObjectStore:
    def __init__(self, collection, *, create=False):
        self.collection = SafeRoot(collection)
        if create:
            try:
                self.collection.mkdir(STORE)
            except FileExistsError:
                pass
        self.files = SafeRoot(Path(collection) / STORE)
        if create:
            try:
                raw = self.files.read("store.json")
            except FileNotFoundError:
                names = set(self.files.names())
                if "store.json" in names:
                    raw = self.files.read("store.json")  # Another initializer published first.
                elif names - {"staging"}:
                    raise ValueError("Missing shared store descriptor beside existing evidence; identity was not replaced.") from None
                else:
                    descriptor = dict(schema=1, kind="sha256", collection_id=uuid.uuid4().hex)
                    temporary = "staging/descriptor-" + uuid.uuid4().hex
                    self.files.write_new(temporary, encode(descriptor))
                    try:
                        try:
                            self.files.link_new(temporary, "store.json")
                        except FileExistsError:
                            pass
                    finally:
                        self.files.unlink(temporary)
                    raw = self.files.read("store.json")
        else:
            raw = self.files.read("store.json")
        self.descriptor_raw = raw
        self.collection_id = store_descriptor(decode(raw))
        if create:
            try:
                self.files.mkdir("objects")
            except FileExistsError:
                pass
        objects = self.files.info("objects")
        if linked(objects) or not stat.S_ISDIR(objects.st_mode):
            raise ValueError("Shared object namespace is linked or not a directory.")

    def unchanged(self):
        if self.files.read("store.json") != self.descriptor_raw:
            raise ValueError("Shared store identity changed during access.")

    def read(self, entry):
        if not valid_entry(entry):
            raise ValueError("Invalid shared payload declaration.")
        data = self.files.read("objects/" + entry["sha256"])
        if declaration(data) != entry:
            raise ValueError("Shared payload is corrupt: " + entry["sha256"])
        self.unchanged()
        return data

    def put(self, data):
        entry = declaration(data)
        target = "objects/" + entry["sha256"]
        temporary = "staging/payload-" + uuid.uuid4().hex
        self.files.write_new(temporary, data)
        try:
            try:
                self.files.link_new(temporary, target)
            except FileExistsError:
                pass
            if self.read(entry) != data:
                raise ValueError("Conflicting bytes at an existing content address.")
        finally:
            self.files.unlink(temporary)
        return entry


def collect(worktree, run, patterns, required, store):
    """Collect configured payloads; keep direct artifact diagnostics as local evidence."""
    source = SafeRoot(Path(worktree).resolve())
    destination = SafeRoot(run)
    try:
        destination.mkdir("artifacts")
    except FileExistsError:
        info = destination.info("artifacts")
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ArtifactCollision(["artifacts"], "Direct output collides with the artifact directory") from None
    artifacts = SafeRoot(Path(run) / "artifacts")
    local, directories = artifacts.walk()
    if any(name.casefold() == "manifest.json" for name in [*local, *directories]):
        raise ArtifactCollision([name for name in [*local, *directories] if name.casefold() == "manifest.json"],
                                "Direct output collides with the managed artifact manifest")
    selected, missing, skipped = {}, [], []
    for pattern in dict.fromkeys(patterns + required):
        matched = False
        for path in sorted(source.root.glob(pattern)):
            candidate = classify(source.root, path, source)
            if candidate is None:
                continue
            name, info, excluded = candidate
            if excluded:
                skipped.append(name)
                continue
            matched = True
            selected[name] = info
        if not matched and pattern in required:
            missing.append(pattern)
    distinct([*selected, *local, "manifest.json"])
    for name in selected:
        for directory in directories:
            if directory.casefold() == name.casefold() or directory.casefold().startswith(name.casefold() + "/"):
                raise ArtifactCollision([name, directory])
    files = {name: store.put(source.read(name, info)) for name, info in sorted(selected.items())}
    local_files = {name: declaration(artifacts.read(name, info)) for name, info in sorted(local.items())}
    if {n: fingerprint(i) for n, i in artifacts.walk()[0].items()} != {n: fingerprint(i) for n, i in local.items()}:
        raise ValueError("Direct artifact evidence changed during collection.")
    return files, missing, sorted(set(skipped)), local_files


class SharedRun:
    def __init__(self, run):
        self.run = Path(run).resolve()
        self.root = SafeRoot(self.run)
        self.result_raw = self.root.read("result.json")
        self.result = decode(self.result_raw)
        publication = self.result.get("artifact_publication")
        if not isinstance(publication, dict) or publication.get("state") != "complete":
            raise ValueError("Shared artifact publication is incomplete.")
        self.manifest_raw = self.root.read("artifacts/manifest.json")
        self.manifest = decode(self.manifest_raw)
        collection_id = metadata(self.manifest, self.result)
        if hashlib.sha256(self.manifest_raw).hexdigest() != self.result["artifact_publication"]["manifest_sha256"]:
            raise ValueError("Published shared manifest changed.")
        if self.result["status"] == "running":
            raise ValueError("Shared run has not finished publication.")
        self.config_raw = self.root.read("config.toml")
        if hashlib.sha256(self.config_raw).hexdigest() != self.result["config_sha256"]:
            raise ValueError("Retained check configuration changed.")
        self.store = ObjectStore(self.run.parent)
        if self.store.collection_id != collection_id:
            raise ValueError("The selected collection is not this run's shared artifact store.")
        self.files = self.manifest["files"]
        self.local = self.manifest["local_files"]

    def unchanged(self):
        if (self.root.read("result.json") != self.result_raw
                or self.root.read("artifacts/manifest.json") != self.manifest_raw
                or self.root.read("config.toml") != self.config_raw):
            raise ValueError("Run metadata changed during artifact access.")
        self.store.unchanged()

    def read(self, name, *, local=False):
        if local:
            entry = self.local[name]
            data = self.root.read("artifacts/" + name)
            if declaration(data) != entry:
                raise ValueError("Direct artifact evidence changed: " + name)
        else:
            data = self.store.read(self.files[name])
        self.unchanged()
        return data

    def verify(self):
        report = dict(run_dir=str(self.run), snapshot=self.result["snapshot"], config_sha256=self.result["config_sha256"],
                      check_status=self.result["status"], interrupted=False, artifacts=[], local_artifacts=[], unexpected=[])
        for local, entries, key in ((False, self.files, "artifacts"), (True, self.local, "local_artifacts")):
            for name in sorted(entries):
                item = dict(path=name, status="ok")
                try:
                    self.read(name, local=local)
                except FileNotFoundError:
                    item["status"] = "missing"
                except ValueError as exc:
                    item.update(status="changed", error=str(exc))
                report[key].append(item)
        actual, _ = SafeRoot(self.run / "artifacts").walk()
        if os.name == "nt" and "manifest.json" not in actual:
            aliases = [name for name in actual if name.casefold() == "manifest.json"]
            if len(aliases) == 1:
                actual["manifest.json"] = actual.pop(aliases[0])
        report["unexpected"] = sorted(set(actual) - set(self.local) - {"manifest.json"})
        self.unchanged()
        report["verified"] = not report["unexpected"] and all(item["status"] == "ok"
            for item in [*report["artifacts"], *report["local_artifacts"]])
        return report

    def materialize(self, folder):
        target = SafeRoot(folder)
        for name in sorted(self.files):
            target.write_new(name, self.read(name))
        self.unchanged()
        manifest = {key: self.manifest[key] for key in ("snapshot", "config_sha256", "subdir", "run_id", "files")}
        manifest["schema"] = 1
        target.write_new("manifest.json", encode(manifest))


def shared_run(run, *, legacy_compare=False):
    """Select the shared reader without changing legacy plain comparison semantics."""
    try:
        root = SafeRoot(Path(run).resolve())
    except FileNotFoundError:
        return None
    try:
        record = decode(root.read("result.json"))
    except (OSError, ValueError) as exc:
        if not legacy_compare and not isinstance(exc, FileNotFoundError):
            raise
        # Legacy plain comparison did not require metadata. A declared shared format still must.
        import tomllib
        try:
            manifest = decode(root.read("artifacts/manifest.json"))
        except (OSError, ValueError):
            manifest = {}
        try:
            configured = tomllib.loads(root.read("config.toml").decode("utf-8")).get("artifact_storage")
        except (OSError, ValueError):
            configured = None
        if "storage" in manifest or configured == "shared":
            raise ValueError("Shared artifacts require their original result metadata.") from None
        return None
    mode = record.get("artifact_storage", "copy")
    if mode not in ("copy", "shared"):
        raise ValueError("Unknown artifact storage mode.")
    if mode == "shared":
        try:
            return SharedRun(run)
        except OSError as exc:
            raise ValueError("Cannot read shared artifact evidence: " + str(exc)) from exc
    if "artifact_export" in record:
        validate_export(run)
        return None
    if "artifact_publication" in record:
        raise ValueError("Artifact storage mode and publication metadata disagree.")
    try:
        manifest = decode(root.read("artifacts/manifest.json"))
    except (OSError, ValueError):
        manifest = {}
    if "storage" in manifest:
        raise ValueError("Shared manifest and result storage mode disagree.")
    return None
