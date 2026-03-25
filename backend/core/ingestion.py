from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.deduplicator import deduplicate
from backend.core.normalizer import normalize_lead
from backend.core.parser import CANONICAL_FIELDS, load_input


def _load_sources_config(config_path: str | Path) -> dict[str, Any]:
    import yaml

    with Path(config_path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    # Support both `{sources: {...}}` and `{...}` shapes for flexibility.
    if isinstance(payload, dict) and "sources" in payload and isinstance(payload["sources"], dict):
        return payload["sources"]
    return payload if isinstance(payload, dict) else {}


def ingest_to_structures_with_sources_config(
    *,
    input_path: str | Path,
    input_format: str,
    sources_cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    Core ingestion for the API layer.

    Returns in-memory structures only:
      - leads (deduplicated, normalized)
      - rejected rows (invalid or failed validation/mapping)
      - summary (counts + timestamps, no filesystem output)
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    input_mapping_cfg = (sources_cfg.get("input") or {}) if isinstance(sources_cfg, dict) else {}

    leads, rejected = load_input(
        path=input_path,
        input_format=input_format,
        mapping_config=input_mapping_cfg,
    )

    normalized_leads = [normalize_lead(lead) for lead in leads]
    deduped_leads = deduplicate(normalized_leads)

    summary = {
        "started_at": datetime.now().isoformat(),
        "input": {
            "path": str(input_path),
            "format": input_format,
        },
        "counts": {
            "input_rows": None if rejected is None else (len(rejected) + len(leads)),
            "mapped_valid_rows": len(leads),
            "rejected_rows": len(rejected),
            "deduped_rows": len(deduped_leads),
        },
    }

    return deduped_leads, rejected, summary


def ingest_to_structures(
    *,
    input_path: str | Path,
    input_format: str,
    config_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    sources_cfg = _load_sources_config(config_path)
    return ingest_to_structures_with_sources_config(
        input_path=input_path,
        input_format=input_format,
        sources_cfg=sources_cfg,
    )


def run_ingestion(
    *,
    input_path: str | Path,
    input_format: str,
    config_path: str | Path,
    output_summary_path: str | Path,
) -> dict[str, Any]:
    """
    Week 1 ingestion pipeline:
      parse -> schema map -> basic validation -> normalize -> dedup -> emit outputs
    """
    input_path = Path(input_path)
    config_path = Path(config_path)
    output_summary_path = Path(output_summary_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    sources_cfg = _load_sources_config(config_path)
    return run_ingestion_with_sources_config(
        input_path=input_path,
        input_format=input_format,
        sources_cfg=sources_cfg,
        output_summary_path=output_summary_path,
    )


def run_ingestion_with_sources_config(
    *,
    input_path: str | Path,
    input_format: str,
    sources_cfg: dict[str, Any],
    output_summary_path: str | Path,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_summary_path = Path(output_summary_path)

    deduped_leads, rejected, summary = ingest_to_structures_with_sources_config(
        input_path=input_path,
        input_format=input_format,
        sources_cfg=sources_cfg,
    )

    out_dir = output_summary_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # When the caller uses a timestamp-named output directory, bake the same
    # timestamp into filenames so artifacts are unique and easy to sort.
    run_ts = out_dir.name

    leads_json_path = out_dir / f"leads_{run_ts}.json"
    leads_csv_path = out_dir / f"leads_{run_ts}.csv"
    rejected_path = out_dir / f"rejected_rows_{run_ts}.json"

    leads_json_path.write_text(json.dumps(deduped_leads, indent=2), encoding="utf-8")

    # Emit CSV with canonical field ordering.
    with leads_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CANONICAL_FIELDS))
        writer.writeheader()
        for lead in deduped_leads:
            writer.writerow({k: lead.get(k) for k in CANONICAL_FIELDS})

    rejected_path.write_text(json.dumps(rejected, indent=2), encoding="utf-8")

    summary_with_outputs = {
        **summary,
        "output": {
            "leads_json": str(leads_json_path),
            "leads_csv": str(leads_csv_path),
            "rejected_rows": str(rejected_path),
            "summary": str(output_summary_path),
        },
    }

    output_summary_path.write_text(json.dumps(summary_with_outputs, indent=2), encoding="utf-8")
    return summary_with_outputs

