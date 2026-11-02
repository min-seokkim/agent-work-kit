"""Paths, identities and manifest entries of retained evidence, read without following links. The shared object
store, the collectors and exports build on these."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import stat
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
