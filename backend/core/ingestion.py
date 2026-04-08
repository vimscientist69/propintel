from __future__ import annotations

import csv
import concurrent.futures
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from backend.core.deduplicator import deduplicate
from backend.core.logging_utils import get_logger
from backend.core.normalizer import normalize_lead
from backend.core.parser import CANONICAL_FIELDS, load_input
from backend.core.config_schema import validate_sources_config
from backend.core.rate_limit import ProviderLimiter, ProviderRetryConfig
from backend.services.conflict_resolver import (
    TRACKED_FIELDS,
    make_candidate,
    resolve_all_fields,
)
from backend.services.enrichment import enrich_lead
from backend.services.google_maps import enrich_lead_from_google_maps
from backend.services.scorer import confidence_from_score, score_lead
from backend.services.verifier import verify_lead


logger = get_logger(__name__)


class JobTerminationRequested(RuntimeError):
    """Raised when an external stop signal asks ingestion to halt."""


def _load_sources_config(config_path: str | Path) -> dict[str, Any]:
    import yaml

    with Path(config_path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    # Support both `{sources: {...}}` and `{...}` shapes for flexibility.
    if isinstance(payload, dict) and "sources" in payload and isinstance(payload["sources"], dict):
        return validate_sources_config(payload["sources"])
    if isinstance(payload, dict):
        return validate_sources_config(payload)
    return validate_sources_config({})


def ingest_to_structures_with_sources_config(
    *,
    input_path: str | Path,
    input_format: str,
    sources_cfg: dict[str, Any],
    should_stop: Callable[[], bool] | None = None,
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
    sources_cfg = validate_sources_config(sources_cfg)

    def _check_stop() -> None:
        if should_stop is not None and should_stop():
            raise JobTerminationRequested("job_termination_requested")

    input_mapping_cfg = (sources_cfg.get("input") or {}) if isinstance(sources_cfg, dict) else {}

    leads, rejected = load_input(
        path=input_path,
        input_format=input_format,
        mapping_config=input_mapping_cfg,
    )

    normalized_leads = [normalize_lead(lead) for lead in leads]
    deduped_leads = deduplicate(normalized_leads)
    website_cfg = (sources_cfg.get("website") or {}) if isinstance(sources_cfg, dict) else {}
    google_maps_cfg = (sources_cfg.get("google_maps") or {}) if isinstance(sources_cfg, dict) else {}
    scoring_cfg = (sources_cfg.get("scoring") or {}) if isinstance(sources_cfg, dict) else {}
    scoring_enabled = bool(scoring_cfg.get("enabled", True))
    scored_rows = 0
    runtime_cfg = (sources_cfg.get("runtime") or {}) if isinstance(sources_cfg, dict) else {}
    worker_concurrency = max(1, int(runtime_cfg.get("worker_concurrency", 1)))
    providers_cfg = runtime_cfg.get("providers") if isinstance(runtime_cfg, dict) else None
    providers_cfg = providers_cfg if isinstance(providers_cfg, dict) else {}

    def _provider_cfg(name: str) -> dict[str, Any]:
        value = providers_cfg.get(name)
        return value if isinstance(value, dict) else {}

    def _build_executor(name: str, *, default_rps: float, default_concurrent: int) -> Callable[[Callable[[], object]], object] | None:
        p_cfg = _provider_cfg(name)
        if p_cfg.get("enabled", True) is False:
            return None
        limiter = ProviderLimiter(
            rps=float(p_cfg.get("requests_per_second", default_rps)),
            burst=int(p_cfg.get("burst", max(1, int(default_rps * 2)))),
            max_concurrent=int(p_cfg.get("max_concurrent", default_concurrent)),
        )
        return lambda fn: limiter.run(fn)

    def _build_retry(name: str, *, default_attempts: int, default_base: int, default_max: int, default_jitter: int) -> ProviderRetryConfig:
        retry_cfg = _provider_cfg(name).get("retry")
        retry_cfg = retry_cfg if isinstance(retry_cfg, dict) else {}
        return ProviderRetryConfig(
            max_attempts=int(retry_cfg.get("max_attempts", default_attempts)),
            base_delay_ms=int(retry_cfg.get("base_delay_ms", default_base)),
            max_delay_ms=int(retry_cfg.get("max_delay_ms", default_max)),
            jitter_ms=int(retry_cfg.get("jitter_ms", default_jitter)),
        )

    runtime_context = {
        "serper_request_executor": _build_executor("serper", default_rps=1.5, default_concurrent=2),
        "google_maps_request_executor": _build_executor("google_maps", default_rps=2.0, default_concurrent=2),
        "serper_retry_cfg": _build_retry("serper", default_attempts=4, default_base=400, default_max=5000, default_jitter=300),
        "google_maps_retry_cfg": _build_retry("google_maps", default_attempts=4, default_base=300, default_max=4000, default_jitter=250),
    }

    enriched_leads: list[dict[str, Any]] = []
    if worker_concurrency <= 1 or len(deduped_leads) <= 1:
        for lead in deduped_leads:
            _check_stop()
            try:
                enriched_leads.append(enrich_lead(lead, website_cfg, runtime_context))
            except Exception as exc:  # noqa: BLE001
                fallback = dict(lead)
                fallback["enrichment_error"] = str(exc)
                enriched_leads.append(fallback)
    else:
        enriched_leads = [dict(lead) for lead in deduped_leads]
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_concurrency) as pool:
            futures = {
                pool.submit(enrich_lead, lead, website_cfg, runtime_context): idx
                for idx, lead in enumerate(deduped_leads)
            }
            for future in concurrent.futures.as_completed(futures):
                _check_stop()
                idx = futures[future]
                try:
                    enriched_leads[idx] = future.result()
                except Exception as exc:  # noqa: BLE001
                    fallback = dict(deduped_leads[idx])
                    fallback["enrichment_error"] = str(exc)
                    enriched_leads[idx] = fallback

    google_enriched_leads: list[dict[str, Any]] = enriched_leads
    google_attempted = 0
    google_failed = 0
    google_location_normalized = 0
    google_matched = 0
    conflicts_resolved = 0
    replacements_performed = 0
    invalid_candidates = 0
    schema_contacts_used = 0
    email_disposable_rejected = 0
    multi_page_fetch_success = 0
    phone_e164_valid = 0
    phone_e164_total = 0
    google_enabled = bool(google_maps_cfg.get("enabled", False))

    if google_enabled:
        if worker_concurrency <= 1 or len(enriched_leads) <= 1:
            google_enriched_leads = []
            for lead in enriched_leads:
                _check_stop()
                google_attempted += 1
                try:
                    updated = enrich_lead_from_google_maps(lead, google_maps_cfg, runtime_context)
                except Exception as exc:  # noqa: BLE001
                    updated = dict(lead)
                    updated["google_maps_error"] = str(exc)

                if updated.get("google_maps_error"):
                    google_failed += 1
                if updated.get("source") and "google_maps" in str(updated.get("source")):
                    google_matched += 1
                if (
                    str(updated.get("location") or "").strip()
                    and str(updated.get("location") or "").strip()
                    != str(lead.get("location") or "").strip()
                ):
                    google_location_normalized += 1

                google_enriched_leads.append(updated)
        else:
            google_enriched_leads = [dict(lead) for lead in enriched_leads]
            google_attempted = len(enriched_leads)
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_concurrency) as pool:
                futures = {
                    pool.submit(enrich_lead_from_google_maps, lead, google_maps_cfg, runtime_context): idx
                    for idx, lead in enumerate(enriched_leads)
                }
                for future in concurrent.futures.as_completed(futures):
                    _check_stop()
                    idx = futures[future]
                    lead = enriched_leads[idx]
                    try:
                        updated = future.result()
                    except Exception as exc:  # noqa: BLE001
                        updated = dict(lead)
                        updated["google_maps_error"] = str(exc)
                    if updated.get("google_maps_error"):
                        google_failed += 1
                    if updated.get("source") and "google_maps" in str(updated.get("source")):
                        google_matched += 1
                    if (
                        str(updated.get("location") or "").strip()
                        and str(updated.get("location") or "").strip()
                        != str(lead.get("location") or "").strip()
                    ):
                        google_location_normalized += 1
                    google_enriched_leads[idx] = updated

    resolved_leads: list[dict[str, Any]] = []
    for idx, base_lead in enumerate(deduped_leads):
        _check_stop()
        website_stage = enriched_leads[idx] if idx < len(enriched_leads) else dict(base_lead)
        current_stage = (
            google_enriched_leads[idx] if idx < len(google_enriched_leads) else dict(website_stage)
        )
        website_stage_values = dict(website_stage.get("_website_values") or {})
        website_stats = dict(website_stage.get("_website_contact_stats") or {})
        google_stage_values = dict(current_stage.get("_google_maps_values") or {})
        schema_contacts_used += int(website_stats.get("schema_contacts_used", 0))
        email_disposable_rejected += int(website_stats.get("email_disposable_rejected", 0))
        multi_page_fetch_success += int(website_stats.get("multi_page_fetch_success", 0))
        phone_e164_valid += int(website_stats.get("phone_valid_count", 0))
        phone_e164_total += int(website_stats.get("phone_total_candidates", 0))

        candidate_map: dict[str, list[dict[str, Any]]] = {k: [] for k in TRACKED_FIELDS}
        for field in TRACKED_FIELDS:
            base_value = base_lead.get(field)
            if base_value is not None:
                candidate_map[field].append(
                    make_candidate(
                        field=field,
                        source="input",
                        value=base_value,
                        validated=True,
                        confidence=0.35,
                        validation_reason="from_input",
                    )
                )

            w_value = website_stage.get(field)
            if field in ("email", "phone"):
                w_value = website_stage_values.get(field) if website_stage_values.get(field) is not None else w_value
            if w_value is not None and w_value != base_value:
                w_validated = not bool(website_stage.get("enrichment_error"))
                if not w_validated:
                    invalid_candidates += 1
                w_reason = str(website_stats.get(f"{field}_validation_reason") or "website_fetch_ok")
                candidate_map[field].append(
                    make_candidate(
                        field=field,
                        source="website_enrichment",
                        value=w_value,
                        validated=w_validated,
                        confidence=0.82 if (w_validated and field == "email") else (0.75 if w_validated else 0.2),
                        validation_reason=w_reason if w_validated else "website_fetch_failed",
                    )
                )

            g_value = google_stage_values.get(field)
            if g_value is None:
                g_value = current_stage.get(field)
                if g_value == w_value:
                    g_value = None
            if g_value is not None:
                g_validated = not bool(current_stage.get("google_maps_error"))
                if not g_validated:
                    invalid_candidates += 1
                candidate_map[field].append(
                    make_candidate(
                        field=field,
                        source="google_maps",
                        value=g_value,
                        validated=g_validated,
                        # Phone strategy: prefer validated Google Maps over input.
                        confidence=0.9 if (g_validated and field == "phone") else (0.75 if g_validated else 0.2),
                        validation_reason="google_maps_ok" if g_validated else "google_maps_error",
                    )
                )

        resolved, decisions = resolve_all_fields(candidate_map, current_stage)
        decision_list = list(decisions.values())
        conflicts_resolved += sum(1 for d in decision_list if d.get("tie_break_applied"))
        replacements_performed += sum(
            1 for f in TRACKED_FIELDS if resolved.get(f) != base_lead.get(f)
        )

        history = dict(current_stage.get("enrichment_history") or {})
        history["candidates"] = candidate_map
        history["decisions"] = decisions
        history.setdefault("stage_errors", {})
        history.setdefault("diagnostics", {})
        history["diagnostics"]["website"] = website_stats
        if current_stage.get("enrichment_error"):
            history["stage_errors"]["website_enrichment"] = current_stage.get("enrichment_error")
        if current_stage.get("google_maps_error"):
            history["stage_errors"]["google_maps"] = current_stage.get("google_maps_error")
        resolved["enrichment_history"] = history
        resolved.pop("_website_values", None)
        resolved.pop("_website_contact_stats", None)
        resolved.pop("_google_maps_values", None)
        verify_lead(resolved, in_place=True)
        resolved["enrichment_history"]["verification"] = resolved.get("verification")
        if scoring_enabled:
            ls, lr = score_lead(resolved, scoring_cfg)
            resolved["lead_score"] = ls
            resolved["lead_reason"] = lr
            resolved["confidence_score"] = confidence_from_score(ls)
            scored_rows += 1
        resolved_leads.append(resolved)

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
            "enriched_rows": len(enriched_leads),
            "google_maps_attempted": google_attempted,
            "google_maps_matched": google_matched,
            "google_maps_failed": google_failed,
            "google_maps_location_normalized": google_location_normalized,
            "conflicts_resolved": conflicts_resolved,
            "replacements_performed": replacements_performed,
            "invalid_candidates": invalid_candidates,
            "schema_contacts_used": schema_contacts_used,
            "email_disposable_rejected": email_disposable_rejected,
            "multi_page_fetch_success": multi_page_fetch_success,
            "phone_e164_valid_rate": (
                round(float(phone_e164_valid) / float(phone_e164_total), 4)
                if phone_e164_total
                else 0.0
            ),
            "scored_rows": scored_rows if scoring_enabled else 0,
        },
    }

    logger.info(
        "Ingestion summary: input_rows={} valid_rows={} rejected={} deduped={} enriched={} gmaps_attempted={} gmaps_matched={} gmaps_failed={} gmaps_location_normalized={}",
        summary["counts"]["input_rows"],
        summary["counts"]["mapped_valid_rows"],
        summary["counts"]["rejected_rows"],
        summary["counts"]["deduped_rows"],
        summary["counts"]["enriched_rows"],
        summary["counts"]["google_maps_attempted"],
        summary["counts"]["google_maps_matched"],
        summary["counts"]["google_maps_failed"],
        summary["counts"]["google_maps_location_normalized"],
    )

    return resolved_leads, rejected, summary


def ingest_to_structures(
    *,
    input_path: str | Path,
    input_format: str,
    config_path: str | Path,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    sources_cfg = _load_sources_config(config_path)
    return ingest_to_structures_with_sources_config(
        input_path=input_path,
        input_format=input_format,
        sources_cfg=sources_cfg,
        should_stop=should_stop,
    )


def ingest_rows_with_sources_config(
    *,
    rows: list[dict[str, Any]],
    sources_cfg: dict[str, Any],
    should_stop: Callable[[], bool] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    MVP helper for batch processing:
    process a pre-sliced row subset through the same ingestion logic.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        tmp_path = Path(handle.name)
        handle.write(json.dumps(rows))
    try:
        return ingest_to_structures_with_sources_config(
            input_path=tmp_path,
            input_format="json",
            sources_cfg=sources_cfg,
            should_stop=should_stop,
        )
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


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
        should_stop=None,
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