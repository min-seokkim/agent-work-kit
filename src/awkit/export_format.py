"""The format of an exported review run: its provenance files and their validation. The artifact store reads
exports through this module, so it does not depend on the exporter."""

import hashlib
import re
import tomllib
from pathlib import Path

from .artifact_paths import SafeRoot, declaration, decode, distinct, metadata, valid_entry
from .check_config import validate_settings

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


def _inventory(root, expected):
    files, _ = root.walk()
    if set(files) != set(expected):
        raise ValueError("Export evidence inventory changed before publication.")
    for name, entry in expected.items():
        if declaration(root.read(name, files[name])) != entry:
            raise ValueError("Export evidence changed before publication: " + name)


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
