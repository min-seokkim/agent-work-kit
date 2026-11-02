"""Export retained evidence as an independent, attributable ordinary-file bundle."""

import copy
import os
import tempfile
from pathlib import Path

from .artifact_store import (
    ArtifactCollision,
    SafeRoot,
    declaration,
    decode,
    distinct,
    encode,
    fingerprint,
    relative,
    shared_run,
)
from .export_format import (  # noqa: F401  (moved; importers keep working)
    EXPORT_METADATA,
    IDENTITY,
    MANIFEST,
    ORIGINAL_MANIFEST,
    ORIGINAL_RESULT,
    PROVENANCE,
    PROVENANCE_FILE,
    _digest,
    _inventory,
    _legacy_metadata,
    _optional_manifest,
    export_metadata,
    validate_export,
)

PREVENTS = {"awkit review export": ("F1", "F7", "F16")}


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


