import csv
from pathlib import Path


REQUIRED_FIELDS = {"company_name"}


def load_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return []

    missing = REQUIRED_FIELDS - set(rows[0].keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")

    return rows
