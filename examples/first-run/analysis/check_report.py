"""Check an analysis report against the input it was computed from.

Usage: python check_report.py <readings.csv> <assumptions.toml> <report.json>
Recomputes the peak from the input and assumptions, compares it with the report, and makes
sure the interpretation is not presented as a computed value. Exit code 1 on any problem.
"""

import csv
import json
import sys
import tomllib
from pathlib import Path

SECTIONS = ("observed", "assumptions", "computed", "interpretation", "interpretation_status")


def main(argv):
    source, assumptions_path, report_path = Path(argv[1]), Path(argv[2]), Path(argv[3])
    if not report_path.is_file():
        print(f"report not found: {report_path}")
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    problems = [f"missing section: {name}" for name in SECTIONS if name not in report]
    if problems:
        print("\n".join(problems))
        return 1
    with source.open(encoding="utf-8", newline="") as handle:
        counts = [int(row["raw_count"]) for row in csv.DictReader(handle)]
    assumptions = tomllib.loads(assumptions_path.read_text(encoding="utf-8"))
    expected_g = round((max(counts) - counts[0]) / assumptions["scale"]["counts_per_g"], 4)
    if report["computed"]["peak_g"] != expected_g:
        problems.append(f"peak_g {report['computed']['peak_g']} differs from recomputed {expected_g}")
    if report["assumptions"]["counts_per_g"] != assumptions["scale"]["counts_per_g"]:
        problems.append("the report's counts_per_g differs from assumptions.toml")
    if report["observed"]["samples"] != len(counts):
        problems.append("the report's sample count differs from the input")
    if report["interpretation"] is not None and report["interpretation_status"] != "reviewed":
        problems.append("an interpretation is present but not marked as reviewed by a person")
    for line in problems:
        print(line)
    print(f"checked {len(counts)} samples, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
