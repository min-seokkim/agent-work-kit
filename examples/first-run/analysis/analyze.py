"""Compute the peak acceleration from raw sensor counts and write a report.

Usage: python analyze.py <readings.csv> <assumptions.toml> <report.json>
The report keeps observed values, assumptions, computed values and the human interpretation
apart. The analysis stops with exit code 2 when an assumption disagrees with the data.
"""

import csv
import json
import sys
import tomllib
from pathlib import Path


def read_counts(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["time_s", "raw_count"]:
            raise ValueError(f"expected the columns time_s and raw_count, found {reader.fieldnames}")
        return [(float(row["time_s"]), int(row["raw_count"])) for row in reader]


def observed_interval(samples):
    gaps = [b[0] - a[0] for a, b in zip(samples, samples[1:], strict=False)]
    return round(sum(gaps) / len(gaps), 4) if gaps else None


def main(argv):
    source, assumptions_path, target = Path(argv[1]), Path(argv[2]), Path(argv[3])
    samples = read_counts(source)
    assumptions = tomllib.loads(assumptions_path.read_text(encoding="utf-8"))
    counts_per_g = assumptions["scale"]["counts_per_g"]
    gravity = assumptions["scale"]["gravity_m_s2"]
    assumed_rate = assumptions["sampling"]["sample_rate_hz"]
    interval = observed_interval(samples)
    observed = {"samples": len(samples), "interval_s": interval,
                "rest_count": samples[0][1], "max_count": max(count for _, count in samples)}
    if interval and abs(1 / interval - assumed_rate) > 0.01 * assumed_rate:
        print(f"assumed sample_rate_hz = {assumed_rate}, but the data shows an interval of {interval} s "
              f"({round(1 / interval, 2)} Hz). Fix {assumptions_path.name} before computing anything.")
        return 2
    peak_counts = observed["max_count"] - observed["rest_count"]
    peak_g = round(peak_counts / counts_per_g, 4)
    report = {
        "observed": observed,
        "assumptions": {"counts_per_g": counts_per_g, "gravity_m_s2": gravity, "sample_rate_hz": assumed_rate,
                        "source": assumptions_path.name},
        "computed": {"peak_above_rest_counts": peak_counts, "peak_g": peak_g,
                     "peak_m_s2": round(peak_g * gravity, 4),
                     "peak_time_s": next(t for t, c in samples if c == observed["max_count"])},
        "interpretation": None,
        "interpretation_status": "unverified",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"peak {peak_g} g at {report['computed']['peak_time_s']} s; report written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
