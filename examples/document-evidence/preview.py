"""Constrained local preview generator for this example, using only the standard library."""

import argparse
import hashlib
import html
import json
import os
import sys
from pathlib import Path

SOURCE = ("note.md", "requirements.json", "inputs/source-facts.md", "inputs/measurements.csv")
PREVIEW = ("note.md", "requirements.json", "styles/shared.css", "preview.py")
OUTPUTS = ("evidence/preview.html", "evidence/preview.json", "evidence/render.json", "evidence/review.json",
           "evidence/wide.png", "evidence/narrow.png")
ALLOW = frozenset((*SOURCE, *PREVIEW, *OUTPUTS))


def root_path():
    return Path(os.path.abspath(__file__)).parent


def path(root, name):
    """Records can only name fixed files; links cannot expand that boundary."""
    if not isinstance(name, str) or name not in ALLOW:
        raise ValueError(f"File is outside the fixed allowlist: {name!r}")
    anchor = Path(os.path.abspath(root))
    target = anchor / name
    if any(part.is_symlink() for part in (target, *target.parents)):
        raise ValueError(f"Links are not allowed: {name}")
    if not target.resolve().is_relative_to(anchor.resolve()):
        raise ValueError(f"File escapes the example: {name}")
    return target


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identities(root, names):
    return {name: digest(path(root, name).read_bytes()) for name in names}


def html_bytes(root):
    note = path(root, "note.md").read_text(encoding="utf-8")
    css = path(root, "styles/shared.css").read_text(encoding="utf-8")
    # CSS is a fixed authored dependency, never a URL or command from a record.
    if any(token in css.lower() for token in ("url(", "@import", "</style", "expression(")):
        raise ValueError("The example CSS must be self-contained.")
    blocks = []
    for paragraph in note.strip().split("\n\n"):
        if paragraph.startswith("# "):
            blocks.append("<h1>" + html.escape(paragraph[2:]) + "</h1>")
        elif paragraph.startswith("## "):
            blocks.append("<h2>" + html.escape(paragraph[3:]) + "</h2>")
        elif all(line.startswith("|") and line.endswith("|") for line in paragraph.splitlines()):
            rows = []
            for index, line in enumerate(paragraph.splitlines()):
                if all(cell.strip() and set(cell.strip()) <= {"-", ":"} for cell in line.strip("|").split("|")):
                    continue
                tag = "th" if index == 0 else "td"
                rows.append("<tr>" + "".join(f"<{tag}>{html.escape(cell.strip())}</{tag}>"
                                            for cell in line.strip("|").split("|")) + "</tr>")
            blocks.append("<table>" + "".join(rows) + "</table>")
        else:
            blocks.append("<p>" + html.escape(" ".join(paragraph.splitlines())) + "</p>")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; font-src \'none\'">'
            '<title>Cache pilot decision</title><style>' + css + '</style></head><body><article>'
            + "\n".join(blocks) + '</article></body></html>\n').encode("utf-8")


def build(root):
    data = html_bytes(root)
    record = dict(schema=1, generator=dict(name="preview.py", format=1), inputs=identities(root, PREVIEW),
                  output=dict(path="evidence/preview.html", sha256=digest(data)))
    destination = path(root, "evidence/preview.html")
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(data)
    path(root, "evidence/preview.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    args = parser.parse_args()
    try:
        if args.action == "build":
            print(json.dumps(build(root_path()), indent=2))
        else:
            root = root_path()
            data = html_bytes(root)
            expected = dict(schema=1, generator=dict(name="preview.py", format=1), inputs=identities(root, PREVIEW),
                            output=dict(path="evidence/preview.html", sha256=digest(data)))
            actual = json.loads(path(root, "evidence/preview.json").read_text(encoding="utf-8"))
            matched = actual == expected and path(root, "evidence/preview.html").read_bytes() == data
            print("Preview bytes and declared inputs match." if matched else "Preview evidence is stale or changed.")
            sys.exit(0 if matched else 1)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
