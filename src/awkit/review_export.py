"""Export retained evidence as an independent, attributable ordinary-file bundle."""

import copy
import hashlib
import os
import re
import tempfile
import tomllib
from pathlib import Path

from .artifact_store import (
    ArtifactCollision,
    SafeRoot,
    declaration,
    decode,
    distinct,
    encode,
    fingerprint,
    metadata,
    relative,
    shared_run,
    valid_entry,
)

PREVENTS = {"awkit review export": ("F7", "F16", "F17")}
PROVENANCE = ".awkit-export"
PROVENANCE_FILE = PROVENANCE + "/provenance.json"
ORIGINAL_RESULT = PROVENANCE + "/original-result.json"
ORIGINAL_MANIFEST = PROVENANCE + "/original-manifest.json"
MANIFEST = "artifacts/manifest.json"
IDENTITY = ("run_id", "snapshot", "config_sha256", "subdir")
EXPORT_METADATA = ("result.json", MANIFEST, "config.toml", PROVENANCE_FILE, ORIGINAL_RESULT, ORIGINAL_MANIFEST)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _legacy_metadata(result, manifest, config):
    if manifest is None:
        from .review import validate_settings
        settings = tomllib.loads(config.decode("utf-8"))
        validate_settings(settings)
        if (settings.get("artifact_storage", "copy") != "copy"
                or settings.get("artifacts", []) != [] or settings.get("required_artifacts", []) != []
                or result.get("artifacts", {}) != {}):
            raise ValueError("A missing copied manifest is allowed only for an artifactless check.")
        recorded_dir = result.get("run_dir")
        recorded_id = recorded_dir.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] if isinstance(recorded_dir, str) else None
        manifest = {key: result.get(key) for key in IDENTITY[1:]}
        manifest.update(schema=1, run_id=result.get("run_id", recorded_id), files={})
    if (type(manifest.get("schema")) is not int or manifest["schema"] != 1
            or not isinstance(manifest.get("files"), dict)
            or not isinstance(manifest.get("run_id"), str)
            or not re.fullmatch(r"review-[A-Za-z0-9_-]+", manifest["run_id"])
            or not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", str(result.get("snapshot", "")))
            or not isinstance(result.get("status"), str)
            or result["status"] not in {"passed", "failed", "uncertain", "cleanup-failed"}
            or result.get("artifact_storage", "copy") != "copy"
            or "artifact_publication" in result or "artifact_export" in result
            or any(manifest.get(key) != result.get(key) for key in IDENTITY[1:])
            or ("run_id" in result and result["run_id"] != manifest["run_id"])
            or _digest(config) != result.get("config_sha256")):
        raise ValueError("Export requires complete, matching copied-run metadata and configuration.")
    files = manifest["files"]
    distinct([*files, "manifest.json"])
    if any(not valid_entry(value) or set(value) != {"size", "sha256"} for value in files.values()):
        raise ValueError("Invalid copied artifact declaration.")
    if "artifacts" in result and result["artifacts"] != files:
        raise ValueError("Copied result and manifest artifact declarations disagree.")
    return manifest


def _optional_manifest(root, name):
    try:
        return root.read(name)
    except FileNotFoundError:
        return None


def _walk_run(root):
    def managed(name):
        first, separator, rest = name.partition("/")
        if os.name == "nt":
            if first.casefold() in {"artifacts", "worktree", "result.json", "config.toml"}:
                first = first.casefold()
            if first == "artifacts" and rest.casefold() == "manifest.json":
                rest = "manifest.json"
        return first + separator + rest

    excluded = tuple(name for name in root.names() if managed(name) == "worktree")
    files, directories = root.walk(exclude=excluded)
    # Also exclude an alias introduced between the root listing and the walk.
    return tuple({managed(name): value for name, value in entries.items()
                  if managed(name).split("/", 1)[0] != "worktree"} for entries in (files, directories))


class _Source:
    def __init__(self, run):
        self.shared = shared_run(run)
        self.run = Path(run).resolve()
        self.root = SafeRoot(self.run)
        self.result_raw = self.root.read("result.json")
        self.manifest_raw = _optional_manifest(self.root, MANIFEST)
        self.config_raw = self.root.read("config.toml")
        self.result = decode(self.result_raw)
        self.manifest = decode(self.manifest_raw) if self.manifest_raw is not None else None
        if "artifact_export" in self.result:
            raise ValueError("Source already uses the reserved export provenance namespace.")
        if self.shared is None:
            self.manifest = _legacy_metadata(self.result, self.manifest, self.config_raw)
            self.files, self.local = self.manifest["files"], {}
        else:
            self.shared.unchanged()
            if (self.result_raw, self.manifest_raw, self.config_raw) != (
                    self.shared.result_raw, self.shared.manifest_raw, self.shared.config_raw):
                raise ValueError("Run changed while opening export source.")
            self.files, self.local = self.shared.files, self.shared.local
        self.observed, self.directories = _walk_run(self.root)
        reserved = [name for name in [*self.observed, *self.directories]
                    if name.split("/", 1)[0].casefold() == PROVENANCE.casefold()]
        if reserved:
            raise ArtifactCollision(reserved, "Direct evidence collides with export provenance")
        actual = {name[len("artifacts/"):] for name in self.observed if name.startswith("artifacts/")}
        expected = set(self.local if self.shared else self.files)
        if self.manifest_raw is not None:
            expected.add("manifest.json")
        if actual != expected:
            raise ValueError("Unexpected or missing local artifact evidence prevents export.")
        self.unchanged()

    def read_artifact(self, name, *, local=False):
        if self.shared:
            return self.shared.read(name, local=local)
        data = self.root.read("artifacts/" + name, self.observed["artifacts/" + name])
        if declaration(data) != self.files[name]:
            raise ValueError("Copied artifact changed: " + name)
        return data

    def unchanged(self):
        if self.shared:
            self.shared.unchanged()
        if (self.root.read("result.json"), _optional_manifest(self.root, MANIFEST), self.root.read("config.toml")) != (
                self.result_raw, self.manifest_raw, self.config_raw):
            raise ValueError("Source metadata changed during export.")
        files, directories = _walk_run(self.root)
        if (directories != self.directories or {n: fingerprint(i) for n, i in files.items()}
                != {n: fingerprint(i) for n, i in self.observed.items()}):
            raise ValueError("Source evidence changed during export.")


def _destination(output, source):
    lexical = Path(os.path.abspath(output))
    relative(lexical.name)
    parent = SafeRoot(lexical.parent.resolve(strict=True))
    destination = parent.root / lexical.name
    if destination.is_relative_to(source.run):
        raise ValueError("Export destination cannot be inside the source run.")
    if source.shared and destination.is_relative_to(source.shared.store.files.root):
        raise ValueError("Export destination cannot be inside the shared payload store.")
    try:
        parent.info(lexical.name)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("Export destination already exists: " + str(destination))
    return parent, destination


def _prepare_output(destination):
    # The export can be outside Git. Apply existing exclusion rules only to managed outputs.
    from .local_state import prepare
    for ancestor in (destination, *destination.parents):
        if ancestor.name == ".awkit":
            prepare(ancestor.parent, destination, recursive=True)
            break


def _inventory(root, expected):
    files, _ = root.walk()
    if set(files) != set(expected):
        raise ValueError("Export evidence inventory changed before publication.")
    for name, entry in expected.items():
        if declaration(root.read(name, files[name])) != entry:
            raise ValueError("Export evidence changed before publication: " + name)


def export_run(run_dir, output):
    """Publish a complete copied representation to an exclusively claimed new directory."""
    source = _Source(run_dir)
    parent, destination = _destination(output, source)
    combined = {**source.files, **source.local}
    exported_manifest = {key: source.manifest[key] for key in IDENTITY}
    exported_manifest.update(schema=1, files=combined)
    manifest_raw = encode(exported_manifest)
    evidence = {}
    mappings = {name: {"association": "configured", "source": "artifacts/" + name}
                for name in source.files}
    mappings.update({name: {"association": "direct-diagnostic", "source": "artifacts/" + name}
                     for name in source.local})
    with tempfile.TemporaryDirectory(prefix="awkit-export-") as temporary:
        stage = SafeRoot(Path(temporary).resolve())

        def retain(name, data):
            stage.write_new(name, data)
            evidence[name] = declaration(data)

        for name, info in sorted(source.observed.items()):
            if name == "result.json" or name.startswith("artifacts/"):
                continue
            retain(name, source.root.read(name, info))
        for local, entries in ((False, source.files), (True, source.local)):
            for name in sorted(entries):
                retain("artifacts/" + name, source.read_artifact(name, local=local))
        retain(MANIFEST, manifest_raw)
        retain(ORIGINAL_RESULT, source.result_raw)
        original_manifest = dict(present=False, path=None)
        if source.manifest_raw is not None:
            retain(ORIGINAL_MANIFEST, source.manifest_raw)
            original_manifest = dict(present=True, path=ORIGINAL_MANIFEST, schema=source.manifest["schema"],
                                     **declaration(source.manifest_raw))
        provenance = dict(schema=1, kind="awkit-review-export", source_storage=source.result.get("artifact_storage", "copy"),
            original_result=dict(path=ORIGINAL_RESULT, **declaration(source.result_raw)),
            original_manifest=original_manifest,
            rewritten_result="result.json", rewritten_manifest=MANIFEST, artifacts=mappings,
            evidence_files=dict(evidence), excluded=["worktree"])
        provenance_raw = encode(provenance)
        retain(PROVENANCE_FILE, provenance_raw)
        result = copy.deepcopy(source.result)
        result.update(run_id=source.manifest["run_id"], run_dir=str(destination), worktree=None,
            worktree_retained=False, artifact_storage="copy", artifacts=combined,
            artifact_publication=dict(state="complete", manifest_sha256=_digest(manifest_raw)),
            artifact_export=dict(schema=1, provenance=PROVENANCE_FILE, provenance_sha256=_digest(provenance_raw)))
        result_raw = encode(result)
        distinct([*evidence, "result.json"])
        for directory in source.directories:
            if any(name.casefold() == directory.casefold() or directory.casefold().startswith(name.casefold() + "/")
                   for name in [*evidence, "result.json"]):
                raise ArtifactCollision([directory], "Direct directory collides with exported evidence")
        source.unchanged()
        _inventory(stage, evidence)
        stage.write_new("result.json", result_raw)
        validate_export(stage.root)
        _prepare_output(destination)
        parent.mkdir(destination.name)  # Exclusive claim; never merge into an existing directory.
        target = SafeRoot(destination)
        try:
            for name in sorted(evidence):
                target.write_new(name, stage.read(name))
            source.unchanged()
            _inventory(target, evidence)
            target.write_new("result.json", result_raw)  # A partial export has no usable result.
        except BaseException as exc:
            if isinstance(exc, Exception):
                raise ValueError(f"Export is incomplete at {destination}; retained files were not removed: {exc}") from exc
            raise
    return dict(run_dir=str(destination), source_run_id=source.manifest["run_id"],
                provenance=str(destination / PROVENANCE_FILE), artifact_files=len(combined), status="exported")


def export_metadata(raw):
    """Validate metadata bytes, with explicit original-manifest absence, without opening paths."""
    if (not isinstance(raw, dict) or any(not isinstance(raw.get(name), bytes) for name in EXPORT_METADATA[:-1])
            or ORIGINAL_MANIFEST not in raw or not isinstance(raw[ORIGINAL_MANIFEST], (bytes, type(None)))):
        raise ValueError("Export requires its complete metadata and original provenance files.")
    result = decode(raw["result.json"])
    marker, publication = result.get("artifact_export"), result.get("artifact_publication")
    if (result.get("artifact_storage") != "copy" or not isinstance(marker, dict)
            or type(marker.get("schema")) is not int or marker["schema"] != 1
            or marker.get("provenance") != PROVENANCE_FILE or not isinstance(publication, dict)
            or publication.get("state") != "complete" or "collection_id" in publication):
        raise ValueError("Unknown or incomplete exported evidence format.")
    provenance_raw, manifest_raw = raw[PROVENANCE_FILE], raw[MANIFEST]
    if (_digest(provenance_raw) != marker.get("provenance_sha256")
            or _digest(manifest_raw) != publication.get("manifest_sha256")):
        raise ValueError("Export manifest or provenance changed.")
    provenance, manifest = decode(provenance_raw), decode(manifest_raw)
    if (type(provenance.get("schema")) is not int or provenance["schema"] != 1
            or provenance.get("kind") != "awkit-review-export"
            or provenance.get("rewritten_result") != "result.json" or provenance.get("rewritten_manifest") != MANIFEST):
        raise ValueError("Unknown export provenance format.")
    originals = []
    for key, name in (("original_result", ORIGINAL_RESULT), ("original_manifest", ORIGINAL_MANIFEST)):
        entry = provenance.get(key)
        original_raw = raw[name]
        if name == ORIGINAL_MANIFEST and original_raw is None:
            if entry != {"present": False, "path": None}:
                raise ValueError("Missing original manifest was not explicitly declared absent.")
            originals.append(None)
            continue
        if not isinstance(entry, dict) or entry.get("path") != name or any(
                entry.get(field) != value for field, value in declaration(original_raw).items()):
            raise ValueError("Original export evidence changed: " + name)
        if name == ORIGINAL_MANIFEST and entry.get("present", True) is not True:
            raise ValueError("Original manifest presence disagrees with provenance.")
        originals.append(decode(original_raw))
    original_result, original_manifest = originals
    config = raw["config.toml"]
    if original_manifest is not None and original_manifest.get("schema") == 2:
        metadata(original_manifest, original_result)
        if _digest(raw[ORIGINAL_MANIFEST]) != original_result["artifact_publication"]["manifest_sha256"]:
            raise ValueError("Original shared publication hash does not match.")
        configured, local = original_manifest["files"], original_manifest["local_files"]
    else:
        original_manifest = _legacy_metadata(original_result, original_manifest, config)
        configured, local = original_manifest["files"], {}
    combined = {**configured, **local}
    mappings = {name: {"association": "configured", "source": "artifacts/" + name} for name in configured}
    mappings.update({name: {"association": "direct-diagnostic", "source": "artifacts/" + name} for name in local})
    if (type(manifest.get("schema")) is not int or manifest["schema"] != 1
            or manifest.get("files") != combined or result.get("artifacts") != combined
            or any(manifest.get(key) != original_manifest.get(key) or result.get(key) != original_manifest.get(key)
                   for key in IDENTITY)
            or result.get("status") != original_result.get("status") or result.get("status") == "running"
            or _digest(config) != result.get("config_sha256") or result.get("worktree_retained") is not False
            or result.get("worktree") is not None or provenance.get("excluded") != ["worktree"]
            or provenance.get("artifacts") != mappings
            or provenance.get("source_storage") != original_result.get("artifact_storage", "copy")
            or (raw[ORIGINAL_MANIFEST] is not None
                and provenance["original_manifest"].get("schema") != original_manifest["schema"])):
        raise ValueError("Exported representation does not preserve its original evidence identity.")
    expected = provenance.get("evidence_files")
    if not isinstance(expected, dict) or any(not valid_entry(entry) or set(entry) != {"size", "sha256"}
                                             for entry in expected.values()):
        raise ValueError("Invalid export evidence inventory.")
    distinct([*expected, PROVENANCE_FILE, "result.json"])
    for name in ("config.toml", MANIFEST, ORIGINAL_RESULT, ORIGINAL_MANIFEST):
        if raw[name] is None:
            if name in expected:
                raise ValueError("Export inventory fabricates an absent original manifest.")
            continue
        if expected.get(name) != declaration(raw[name]):
            raise ValueError("Export inventory omits or changes required evidence: " + name)
    if any(expected.get("artifacts/" + name) != entry for name, entry in combined.items()):
        raise ValueError("Export inventory and artifact declarations disagree.")
    return result


def validate_export(run):
    """Check export provenance and bytes before the ordinary schema-1 reader is used."""
    root = SafeRoot(Path(run).resolve())
    raw = {name: _optional_manifest(root, name) if name == ORIGINAL_MANIFEST else root.read(name)
           for name in EXPORT_METADATA}
    result = export_metadata(raw)
    expected = decode(raw[PROVENANCE_FILE])["evidence_files"]
    complete = {**expected, PROVENANCE_FILE: declaration(raw[PROVENANCE_FILE]), "result.json": declaration(raw["result.json"])}
    _inventory(root, complete)
    return result
