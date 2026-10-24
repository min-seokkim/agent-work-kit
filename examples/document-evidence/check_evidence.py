"""Validate this example's declared coverage and byte identities, not review truth or quality."""

import argparse
import json
import re
import struct

import preview

# F1: missing or stale review declarations cannot establish coverage of the selected version.
PREVENTS = {"document-evidence/check_evidence.py": ("F1",)}

RENDERED = (*preview.PREVIEW, "evidence/preview.html", "evidence/preview.json", "evidence/render.json",
            "evidence/wide.png", "evidence/narrow.png")
DUTIES = {"source": preview.SOURCE, "preservation": preview.SOURCE, "rendered": RENDERED}
HASH = re.compile(r"[0-9a-f]{64}\Z")


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} needs a nonempty string.")
    return value


def object_record(root, name):
    value = json.loads(preview.path(root, name).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != 1:
        raise ValueError(f"{name} needs schema 1.")
    return value


def hash_map(value, names):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError("Hash keys must match the fixed duty input names.")
    if any(not isinstance(item, str) or not HASH.fullmatch(item) for item in value.values()):
        raise ValueError("Invalid SHA256 identity.")


def inspect(root, *, allow_simulated=False):
    issues, duties = [], {}
    simulated = False

    def issue(kind, location, detail):
        issues.append(dict(kind=kind, location=location, detail=detail))

    def load(name):
        try:
            return object_record(root, name)
        except FileNotFoundError:
            issue("missing", name, "Required record is absent.")
            return None

    def match(expected, names, location):
        hash_map(expected, names)
        matches = True
        for name in names:
            try:
                actual = preview.digest(preview.path(root, name).read_bytes())
            except FileNotFoundError:
                issue("missing", name, f"Input of {location} is absent.")
                matches = False
                continue
            if actual != expected[name]:
                issue("identity-mismatch", location, name)
                matches = False
        return matches

    requirements = load("requirements.json")
    if requirements is None:
        return dict(schema=1, duties={}, diagnostics=issues, simulated=False, passed=False), 1
    if (requirements.get("document") != "note.md"
            or requirements.get("source_inputs") != list(preview.SOURCE[2:])
            or set(requirements.get("render_inputs", [])) != set(preview.PREVIEW)
            or requirements.get("required_duties") != list(DUTIES)
            or requirements.get("excluded_inputs") != ["inputs/unrelated-source.md"]
            or requirements.get("preview_viewports") != [dict(width=1200, height=900), dict(width=390, height=844)]):
        raise ValueError("Requirements do not match this fixed example contract.")
    for field in ("audience", "intended_decision"):
        text(requirements.get(field), field)
    preservation = requirements.get("preserve")
    if not isinstance(preservation, list) or not preservation:
        raise ValueError("Preservation duties must be fixed before production.")
    for item in preservation:
        text(item, "preserve")

    generated = load("evidence/preview.json")
    if generated is not None:
        if generated.get("generator") != dict(name="preview.py", format=1):
            raise ValueError("Unknown preview generator format.")
        match(generated.get("inputs"), preview.PREVIEW, "preview inputs")
        output = generated.get("output")
        if not isinstance(output, dict) or output.get("path") != "evidence/preview.html":
            raise ValueError("Unknown preview output.")
        match({"evidence/preview.html": output.get("sha256")}, ("evidence/preview.html",), "preview output")
        try:
            if preview.html_bytes(root) != preview.path(root, "evidence/preview.html").read_bytes():
                issue("stale-preview", "evidence/preview.html", "Frozen HTML differs from the selected current inputs.")
        except FileNotFoundError as error:
            issue("missing", "preview inputs", str(error))

    render = load("evidence/render.json")
    if render is not None:
        status = render.get("status")
        if status not in ("performed", "unavailable", "missing"):
            raise ValueError("Invalid render status.")
        if status != "performed":
            if status == "unavailable":
                text(render.get("reason"), "render reason")
            issue(status, "render", render.get("reason", "Rendering is missing."))
        else:
            match(render.get("inputs"), ("evidence/preview.html", "evidence/preview.json"), "render inputs")
            renderer = render.get("renderer")
            if not isinstance(renderer, dict):
                raise ValueError("Renderer identity is required.")
            for field in ("application", "version", "os", "method", "font_conditions"):
                text(renderer.get(field), "renderer " + field)
            captures = render.get("captures")
            if not isinstance(captures, list) or len(captures) != 2:
                raise ValueError("Both fixed viewport captures are required.")
            for capture, name, viewport in zip(captures, ("evidence/wide.png", "evidence/narrow.png"),
                                               requirements["preview_viewports"], strict=True):
                if (not isinstance(capture, dict) or capture.get("path") != name
                        or capture.get("viewport") != viewport or capture.get("full_page") is not True
                        or type(capture.get("image_height")) is not int or capture["image_height"] < viewport["height"]):
                    raise ValueError("Capture must identify the fixed path, viewport and full image height.")
                match({name: capture.get("sha256")}, (name,), "render output")
                try:
                    data = preview.path(root, name).read_bytes()
                except FileNotFoundError:
                    continue
                if (len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n"
                        or struct.unpack(">II", data[16:24]) != (viewport["width"], capture["image_height"])):
                    issue("changed-output", name, "PNG signature or dimensions do not match the capture declaration.")
            simulated = render.get("provenance") == "simulated-test"

    review = load("evidence/review.json")
    entries = {} if review is None else review.get("duties")
    if not isinstance(entries, dict) or set(entries) - set(DUTIES):
        raise ValueError("Review duty keys must be source, preservation and rendered.")
    for name, inputs in DUTIES.items():
        entry = entries.get(name)
        if entry is None:
            duties[name] = dict(status="missing", identities="unverified")
            issue("missing", name, "Required review entry is absent.")
            continue
        if not isinstance(entry, dict) or entry.get("status") not in ("performed", "unavailable", "missing"):
            raise ValueError("Invalid declared review status.")
        status = entry["status"]
        duties[name] = dict(status=status, identities="unverified")
        if status != "performed":
            if status == "unavailable":
                text(entry.get("reason"), "review reason")
            issue(status, name, entry.get("reason", "Review is missing."))
            continue
        for field in ("reviewer", "method", "limitations"):
            text(entry.get(field), "review " + field)
        simulated = simulated or entry.get("provenance") == "simulated-test"
        duties[name]["identities"] = "matching" if match(entry.get("inputs"), inputs, name) else "mismatched"
        findings = entry.get("findings")
        if not isinstance(findings, list):
            raise ValueError("Performed reviews need a findings list.")
        for finding in findings:
            if not isinstance(finding, dict) or finding.get("status") not in ("resolved", "unresolved"):
                raise ValueError("Finding status must be resolved or unresolved.")
            text(finding.get("detail"), "finding detail")
            if finding["status"] == "unresolved":
                issue("unresolved-finding", name, finding["detail"])
    if simulated and not allow_simulated:
        issue("simulated-evidence", "review/render", "Simulated test metadata cannot complete the normal example.")
    report = dict(schema=1, duties=duties, diagnostics=issues, simulated=simulated, passed=not issues,
                  limit="Matching declarations establish recorded coverage only; truth, quality and reader acceptance are unverified.")
    return report, 0 if report["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result, code = inspect(preview.root_path())
    except (ValueError, OSError, TypeError) as error:
        result, code = dict(schema=1, passed=False, diagnostics=[dict(kind="invalid", detail=str(error))]), 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for name, row in result.get("duties", {}).items():
            print(f"{name}: {row['status']} | identities {row['identities']}")
        for row in result["diagnostics"]:
            print(json.dumps(row))
        print(result.get("limit", "Invalid example evidence."))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
