import csv
import json
import re
from typing import Any, Mapping, TypeAlias
from pathlib import Path


REQUIRED_FIELDS = {"company_name"}


# Canonical lead contract used internally across ingestion, enrichment, and scoring.
# Keep this stable to make downstream logic (normalization, dedup, scoring) deterministic.
CanonicalField: TypeAlias = str
Lead: TypeAlias = dict[CanonicalField, Any]

CANONICAL_FIELDS: tuple[str, ...] = (
    # identity
    "company_name",
    "agent_name",
    "website",
    # contacts
    "email",
    "phone",
    # context
    "location",
    # provenance
    "source",
    # enrichment / verification
    "confidence_score",
    "has_chatbot",
    "website_speed_score",
    "last_updated_signal",
    "contact_quality",
    # lead intelligence
    "lead_score",
    "lead_reason",
)

# Business identity rule: at least one of these must be present after mapping.
IDENTITY_FIELDS: tuple[str, ...] = ("company_name",)


def is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def normalize_str(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized if normalized else None
    return None


def normalize_row_keys(row: Mapping[str, Any]) -> dict[str, Any]:
    """
    Normalize incoming key names to increase matching success later (case/whitespace).
    Does not perform alias mapping yet; it only standardizes keys.
    """
    out: dict[str, Any] = {}
    for k, v in row.items():
        if not isinstance(k, str):
            continue
        normalized_key = k.strip().lower()
        out[normalized_key] = v
    return out


def _get_mapping_config(mapping_config: Mapping[str, Any] | None) -> dict[str, Any]:
    if mapping_config is None:
        return {}
    return dict(mapping_config)


def map_row_to_canonical(
    row: Mapping[str, Any],
    mapping_config: Mapping[str, Any] | None,
) -> tuple[Lead | None, str | None]:
    """
    Map a single input row into the canonical lead schema using alias mapping.

    Returns:
      - (lead_dict, None) when mapping + required identity is satisfied
      - (None, reason) when row should be rejected
    """
    cfg = _get_mapping_config(mapping_config)
    required_any = cfg.get("required_any") or list(IDENTITY_FIELDS)
    schema_aliases = cfg.get("schema_aliases") or {}
    defaults = cfg.get("defaults") or {}

    normalized_row = normalize_row_keys(row)

    lead: dict[str, Any] = {}
    for canonical_field in CANONICAL_FIELDS:
        canonical_key = canonical_field.strip().lower()

        value: Any = None
        if canonical_key in normalized_row:
            value = normalized_row[canonical_key]
        else:
            for alias in schema_aliases.get(canonical_field, []) or []:
                alias_norm = str(alias).strip().lower()
                if alias_norm in normalized_row:
                    value = normalized_row[alias_norm]
                    break

        lead[canonical_field] = normalize_str(value)  # store canonical values as strings/None

    # Apply defaults for missing/empty fields.
    for default_key, default_value in defaults.items():
        if default_key not in CANONICAL_FIELDS:
            continue
        if not is_non_empty_str(lead.get(default_key)):
            if isinstance(default_value, str):
                lead[default_key] = normalize_str(default_value)
            else:
                lead[default_key] = default_value

    # Required identity check happens at the row level.
    if required_any:
        if not any(is_non_empty_str(lead.get(field)) for field in required_any):
            return None, "missing_required_identity"

    return lead, None


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_mapped_lead(lead: Mapping[str, Any]) -> str | None:
    """
    Lightweight validation used in Week 1.

    Rules (intentionally basic; full verification is a later MVP stage):
    - `email` must match a basic email regex if present
    - `phone` must contain at least 7 digits if present
    - `website` must look like a domain or URL if present
    """
    email = lead.get("email")
    if is_non_empty_str(email) and not _EMAIL_RE.match(email or ""):
        return "invalid_email"

    phone = lead.get("phone")
    if is_non_empty_str(phone):
        digits = re.sub(r"\D", "", str(phone))
        if len(digits) < 7:
            return "invalid_phone"

    website = lead.get("website")
    if is_non_empty_str(website):
        website_str = str(website)
        if " " in website_str:
            return "invalid_website"
        if not (website_str.startswith("http://") or website_str.startswith("https://")):
            # Domain-ish heuristic for non-URL values.
            if "." not in website_str:
                return "invalid_website"

    return None


def load_csv_mapped(
    path: str | Path,
    mapping_config: Mapping[str, Any] | None = None,
) -> tuple[list[Lead], list[dict[str, Any]]]:
    """
    Load a CSV file and map each row into canonical leads.
    Invalid rows are returned as `rejected` with reasons.
    """
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return [], []

    leads: list[Lead] = []
    rejected: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        lead, reason = map_row_to_canonical(row, mapping_config)
        if lead is None:
            rejected.append({"row_index": idx, "reason": reason or "invalid_row"})
            continue
        validation_reason = validate_mapped_lead(lead)
        if validation_reason is not None:
            rejected.append({"row_index": idx, "reason": validation_reason})
            continue
        leads.append(lead)

    return leads, rejected


def load_csv(path: str | Path) -> list[dict[str, str]]:
    """
    Backwards-compatible CSV loader that returns rows as-is.
    Prefer `load_csv_mapped` for schema mapping and validation.
    """
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return []

    missing = REQUIRED_FIELDS - set(rows[0].keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")

    return rows


def _extract_json_records(payload: Any, list_keys: tuple[str, ...]) -> list[Any] | None:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return None

    for key in list_keys:
        if key in payload and isinstance(payload[key], list):
            return payload[key]

    return None


def load_json_mapped(
    path: str | Path,
    mapping_config: Mapping[str, Any] | None = None,
) -> tuple[list[Lead], list[dict[str, Any]]]:
    """
    Load a JSON file into canonical leads.

    Supported shapes:
    - a list of lead objects
    - a dict containing one of the known list keys
    """
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records = _extract_json_records(payload, list_keys=("leads", "data", "results", "items"))
    if records is None:
        return [], [{"row_index": None, "reason": "invalid_json_root"}]

    leads: list[Lead] = []
    rejected: list[dict[str, Any]] = []

    for idx, record in enumerate(records):
        if not isinstance(record, Mapping):
            rejected.append({"row_index": idx, "reason": "invalid_record_type"})
            continue
        lead, reason = map_row_to_canonical(record, mapping_config)
        if lead is None:
            rejected.append({"row_index": idx, "reason": reason or "invalid_row"})
            continue
        validation_reason = validate_mapped_lead(lead)
        if validation_reason is not None:
            rejected.append({"row_index": idx, "reason": validation_reason})
            continue
        leads.append(lead)

    return leads, rejected


def load_propflux_mapped(
    path: str | Path,
    mapping_config: Mapping[str, Any] | None = None,
) -> tuple[list[Lead], list[dict[str, Any]]]:
    """
    PropFlux output adapter.

    Expected format (from PropFlux export example):
    - The JSON root is a list of listing objects.
    - Listing objects contain keys like:
      - `listing_url`
      - `agency_name`
      - `agent_name`, `agent_phone`
      - `location` (free text)
      - `source_site`
    """
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records = _extract_json_records(
        payload,
        list_keys=("leads", "leadList", "data", "results", "items", "records"),
    )
    if records is None:
        return [], [{"row_index": None, "reason": "invalid_propflux_root"}]

    leads: list[Lead] = []
    rejected: list[dict[str, Any]] = []

    for idx, record in enumerate(records):
        if not isinstance(record, Mapping):
            rejected.append({"row_index": idx, "reason": "invalid_record_type"})
            continue

        # Convert PropFlux listing object -> canonical "lead-like" dict.
        # Keep this mapping explicit and stable for the MVP.
        canonical_row: dict[str, Any] = {
            "company_name": record.get("agency_name"),
            "agent_name": record.get("agent_name"),
            "phone": record.get("agent_phone"),
            "email": record.get("agent_email") or record.get("email"),
            "source": record.get("source_site") or record.get("source"),
        }

        lead, reason = map_row_to_canonical(canonical_row, mapping_config)
        if lead is None:
            rejected.append({"row_index": idx, "reason": reason or "invalid_row"})
            continue
        validation_reason = validate_mapped_lead(lead)
        if validation_reason is not None:
            rejected.append({"row_index": idx, "reason": validation_reason})
            continue
        leads.append(lead)

    return leads, rejected


def load_input(
    path: str | Path,
    input_format: str,
    mapping_config: Mapping[str, Any] | None = None,
) -> tuple[list[Lead], list[dict[str, Any]]]:
    """
    Unified loader for supported input formats.
    """
    normalized_format = input_format.strip().lower()
    if normalized_format == "csv":
        return load_csv_mapped(path, mapping_config)
    elif normalized_format == "json":
        return load_json_mapped(path, mapping_config)
    elif normalized_format == "propflux":
        return load_propflux_mapped(path, mapping_config)
    else:
        raise ValueError(f"Unsupported input_format: {input_format}")