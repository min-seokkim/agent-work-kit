"""Owned content-addressed payloads and checked access to retained evidence."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath

STORE = ".awkit-artifacts"
HEX = re.compile(r"[0-9a-f]{64}\Z")
COLLECTION = re.compile(r"[0-9a-f]{32}\Z")
DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)


class ArtifactCollision(ValueError):
    def __init__(self, paths, reason="Evidence paths collide"):
        self.paths = sorted(set(paths))
        super().__init__(reason + ": " + ", ".join(self.paths))


def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def identity(info):
    return info.st_dev, info.st_ino


def fingerprint(info):
    return *identity(info), info.st_size, info.st_mtime_ns


def relative(value):
    """Use the same unambiguous relative spelling on Windows and Linux."""
    if (not isinstance(value, str) or not value or value.startswith("/")
            or any(c in value for c in '\\:<>"|?*') or any(ord(c) < 32 for c in value)):
        raise ValueError("Evidence paths must be portable relative paths.")
    parts = value.split("/")
    if any(p in {"", ".", ".."} or p.casefold() == ".git" or p.endswith((".", " "))
           or DEVICE.match(p) for p in parts):
        raise ValueError("Evidence path contains an unsafe or aliased component: " + value)
    return PurePosixPath(value)


def distinct(paths):
    """Reject case aliases and file/directory prefix collisions before writing."""
    entries, spellings = [], {}
    for value in paths:
        relative(value)
        prefix = ""
        for part in value.split("/"):
            prefix = prefix + "/" + part if prefix else part
            key = prefix.casefold()
            if key in spellings and spellings[key][0] != prefix:
                raise ArtifactCollision([spellings[key][1], value])
            spellings[key] = prefix, value
        entries.append((value.casefold(), value))
    entries.sort()
    for (before, original), (after, current) in zip(entries, entries[1:], strict=False):
        if before == after or after.startswith(before + "/"):
            raise ArtifactCollision([original, current])


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate metadata key: " + key)
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-finite metadata number: " + value)


def decode(data):
    value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict):
        raise ValueError("Evidence metadata must be an object.")
    return value


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def declaration(data):
    return dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())


def valid_entry(entry):
    return (isinstance(entry, dict) and type(entry.get("size")) is int and entry["size"] >= 0
            and isinstance(entry.get("sha256"), str) and HEX.fullmatch(entry["sha256"]))


@contextmanager
def _windows_directory(path):
    # No delete sharing keeps each checked directory in place while descendants are used.
    # https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilew
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    before = path.lstat()
    if linked(before) or not stat.S_ISDIR(before.st_mode):
        raise ValueError("Evidence directory is linked or not a directory: " + str(path))
    handle = create(str(path), 0x80 | 0x1, 0x1 | 0x2, None, 3, 0x02000000 | 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        after = path.lstat()
        if linked(after) or identity(after) != identity(before):
            raise ValueError("Evidence directory changed while opening it.")
        yield
    finally:
        close(handle)


class SafeRoot:
    """Anchor POSIX operations to directory descriptors; pin Windows directory names."""

    def __init__(self, root):
        self.root = Path(root)
        info = self.root.lstat()
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError("Evidence root must be an ordinary directory.")
        self.original = identity(info)

    @contextmanager
    def parent(self, name, *, create=False):
        rel = relative(name)
        with ExitStack() as stack:
            if os.name == "nt":
                # The selected root is canonical; descendant reparse points are never resolved.
                for ancestor in [*reversed(self.root.parents), self.root]:
                    stack.enter_context(_windows_directory(ancestor))
                if identity(self.root.lstat()) != self.original:
                    raise ValueError("Selected evidence root changed.")
                folder = self.root
                for part in rel.parts[:-1]:
                    folder /= part
                    if create:
                        folder.mkdir(exist_ok=True)
                    stack.enter_context(_windows_directory(folder))
                yield folder / rel.name, None
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                descriptor = os.open(self.root, flags)
                stack.callback(os.close, descriptor)
                if identity(os.fstat(descriptor)) != self.original:
                    raise ValueError("Selected evidence root changed.")
                parents = []
                for part in rel.parts[:-1]:
                    if create:
                        try:
                            os.mkdir(part, dir_fd=descriptor)
                        except FileExistsError:
                            pass
                    parent = descriptor
                    descriptor = os.open(part, flags, dir_fd=parent)
                    stack.callback(os.close, descriptor)
                    parents.append((parent, part, identity(os.fstat(descriptor))))
                yield rel.name, descriptor
                current_root = self.root.lstat()
                if linked(current_root) or identity(current_root) != self.original:
                    raise ValueError("Selected evidence root changed during access.")
                for parent, part, original in parents:
                    current = os.stat(part, dir_fd=parent, follow_symlinks=False)
                    if linked(current) or identity(current) != original:
                        raise ValueError("Evidence parent changed during access: " + name)

    def info(self, name):
        with self.parent(name) as (path, parent):
            return os.stat(path, dir_fd=parent, follow_symlinks=False)

    def read(self, name, expected=None):
        with self.parent(name) as (path, parent):
            before = os.stat(path, dir_fd=parent, follow_symlinks=False)
            if linked(before) or not stat.S_ISREG(before.st_mode):
                raise ValueError("Evidence is linked or not a regular file: " + name)
            if expected is not None and fingerprint(before) != fingerprint(expected):
                raise ValueError("Evidence changed before reading: " + name)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            with os.fdopen(os.open(path, flags, dir_fd=parent), "rb") as stream:
                opened = os.fstat(stream.fileno())
                current = os.stat(path, dir_fd=parent, follow_symlinks=False)
                if linked(current) or fingerprint(opened) != fingerprint(before) or identity(current) != identity(before):
                    raise ValueError("Evidence was replaced before reading: " + name)
                data = stream.read()
                if fingerprint(os.fstat(stream.fileno())) != fingerprint(opened):
                    raise ValueError("Evidence changed while reading: " + name)
                current = os.stat(path, dir_fd=parent, follow_symlinks=False)
                if linked(current) or fingerprint(current) != fingerprint(opened):
                    raise ValueError("Evidence was replaced while reading: " + name)
                return data

    def write_new(self, name, data):
        with self.parent(name, create=True) as (path, parent):
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags, 0o600, dir_fd=parent), "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())

    def link_new(self, source, destination):
        with self.parent(source) as (src, src_parent), self.parent(destination, create=True) as (dst, dst_parent):
            os.link(src, dst, src_dir_fd=src_parent, dst_dir_fd=dst_parent, follow_symlinks=False)

    def unlink(self, name):
        with self.parent(name) as (path, parent):
            os.unlink(path, dir_fd=parent)

    def mkdir(self, name):
        with self.parent(name) as (path, parent):
            os.mkdir(path, dir_fd=parent)

    def names(self, name=""):
        with self.parent(name + "/probe" if name else "probe") as (path, parent):
            return sorted(os.listdir(Path(path).parent if parent is None else parent))

    def walk(self, *, exclude=()):
        files, directories = {}, {}

        def visit(prefix):
            for part in self.names(prefix):
                name = prefix + "/" + part if prefix else part
                if name in exclude:
                    continue
                try:
                    relative(name)
                except ValueError as exc:
                    raise ArtifactCollision([name], "Direct evidence path is not portable") from exc
                info = self.info(name)
                if linked(info):
                    raise ValueError("Linked or reparse evidence was not followed: " + name)
                if stat.S_ISDIR(info.st_mode):
                    directories[name] = identity(info)
                    visit(name)
                    if identity(self.info(name)) != directories[name]:
                        raise ValueError("Evidence directory changed during inspection: " + name)
                elif stat.S_ISREG(info.st_mode):
                    files[name] = info
                else:
                    raise ValueError("Evidence is not a regular file: " + name)
        visit("")
        distinct(files)
        return files, directories


def store_descriptor(value):
    if (type(value.get("schema")) is not int or value["schema"] != 1 or value.get("kind") != "sha256"
            or not isinstance(value.get("collection_id"), str) or not COLLECTION.fullmatch(value["collection_id"])):
        raise ValueError("Unknown or invalid shared artifact store descriptor.")
    return value["collection_id"]


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
    from .review_selection import classify
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


def metadata(manifest, result):
    """Validate shared declarations and their exact result/collection associations."""
    publication = result.get("artifact_publication")
    storage = manifest.get("storage")
    if (result.get("artifact_storage") != "shared" or not isinstance(publication, dict)
            or publication.get("state") != "complete" or not isinstance(storage, dict)
            or type(manifest.get("schema")) is not int or manifest["schema"] != 2
            or storage.get("kind") != "sha256" or not isinstance(storage.get("collection_id"), str)
            or not COLLECTION.fullmatch(storage["collection_id"])
            or publication.get("collection_id") != storage["collection_id"]
            or not isinstance(publication.get("manifest_sha256"), str)
            or not HEX.fullmatch(publication["manifest_sha256"])):
        raise ValueError("Shared artifact publication is incomplete or uses an unknown format.")
    if (not isinstance(result.get("run_id"), str) or not re.fullmatch(r"review-[A-Za-z0-9_-]+", result["run_id"])
            or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", str(result.get("snapshot", "")))
            or not isinstance(result.get("config_sha256"), str) or not HEX.fullmatch(result["config_sha256"])
            or not isinstance(result.get("subdir"), str)
            or not isinstance(result.get("status"), str)
            or result.get("status") not in {"running", "passed", "failed", "uncertain", "cleanup-failed"}
            or any(manifest.get(key) != result.get(key) for key in ("run_id", "snapshot", "config_sha256", "subdir"))):
        raise ValueError("Shared manifest identity does not match result.json.")
    files, local = manifest.get("files"), manifest.get("local_files")
    if not isinstance(files, dict) or not isinstance(local, dict) or result.get("artifacts") != files:
        raise ValueError("Shared artifact declarations do not match result.json.")
    distinct([*files, *local, "manifest.json"])
    if any(not valid_entry(entry) or set(entry) != {"size", "sha256"} for entry in [*files.values(), *local.values()]):
        raise ValueError("Invalid shared artifact size or SHA-256 declaration.")
    return storage["collection_id"]


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
        from .review_export import validate_export
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
