"""Summarise orders by item.

Usage: python process.py <input.csv> <output.csv>
The input needs the columns date, item, quantity and unit_price. The output has one row
per item with total_quantity and total_amount. Exit code 2 when the input is not usable.
"""

import csv
import sys
from pathlib import Path

REQUIRED = ("date", "item", "quantity", "unit_price")


def summarise(rows):
    totals = {}
    for number, row in enumerate(rows, 2):
        try:
            quantity, price = int(row["quantity"]), int(row["unit_price"])
        except ValueError:
            raise ValueError(f"line {number}: quantity and unit_price must be integers") from None
        entry = totals.setdefault(row["item"], {"total_quantity": 0, "total_amount": 0})
        entry["total_quantity"] += quantity
        entry["total_amount"] += quantity * price
    return [{"item": item, **entry} for item, entry in sorted(totals.items())]


def main(argv):
    source, target = Path(argv[1]), Path(argv[2])
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        missing = [name for name in REQUIRED if name not in columns]
        if missing:
            print(f"missing column(s): {', '.join(missing)}; found: {', '.join(columns)}")
            return 2
        try:
            summary = summarise(reader)
        except ValueError as exc:
            print(exc)
            return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["item", "total_quantity", "total_amount"])
        writer.writeheader()
        writer.writerows(summary)
    print(f"wrote {len(summary)} item rows to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
