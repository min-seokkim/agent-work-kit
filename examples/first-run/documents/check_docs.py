"""Check that every Markdown file in a folder has a title and only links to files that exist.

Usage: python check_docs.py <folder>
Exit code 0 when every document passes, 1 when a problem was found.
"""

import re
import sys
from pathlib import Path

LINK = re.compile(r"\]\(([^)\s]+)\)")


def problems(folder):
    found = []
    for document in sorted(folder.rglob("*.md")):
        text = document.read_text(encoding="utf-8")
        first = next((line for line in text.splitlines() if line.strip()), "")
        if not first.startswith("# "):
            found.append(f"{document}: the first line must be a '# ' title")
        for target in LINK.findall(text):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if path and not (document.parent / path).exists():
                found.append(f"{document}: link target not found: {target}")
    return found


def main(argv):
    folder = Path(argv[1]) if len(argv) > 1 else Path("docs")
    if not folder.is_dir():
        print(f"folder not found: {folder}")
        return 2
    found = problems(folder)
    for line in found:
        print(line)
    print(f"checked {len(list(folder.rglob('*.md')))} documents, {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
