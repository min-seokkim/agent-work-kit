"""Check a summary against the orders it was produced from.

Usage: python check_output.py <input.csv> <summary.csv>
Recomputes the totals from the input and compares them with the summary. Exit code 1 when
the summary is missing, has the wrong columns or disagrees with the input.
"""

import csv
import sys
from pathlib import Path

COLUMNS = ["item", "total_quantity", "total_amount"]


def read(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def main(argv):
    source, summary = Path(argv[1]), Path(argv[2])
    if not summary.is_file():
        print(f"summary not found: {summary}")
        return 1
    columns, rows = read(summary)
    if columns != COLUMNS:
        print(f"unexpected columns: {columns}; expected {COLUMNS}")
        return 1
    expected = {}
    for row in read(source)[1]:
        entry = expected.setdefault(row["item"], [0, 0])
        entry[0] += int(row["quantity"])
        entry[1] += int(row["quantity"]) * int(row["unit_price"])
    problems = []
    seen = set()
    for row in rows:
        seen.add(row["item"])
        want = expected.get(row["item"])
        got = [int(row["total_quantity"]), int(row["total_amount"])]
        if want is None:
            problems.append(f"{row['item']}: not in the input")
        elif got != want:
            problems.append(f"{row['item']}: summary says {got}, input gives {want}")
    for item in sorted(set(expected) - seen):
        problems.append(f"{item}: missing from the summary")
    for line in problems:
        print(line)
    print(f"compared {len(rows)} summary rows with {len(expected)} items, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
