# Testing Week 3 verification end-to-end (CLI)

Week 3 verification runs **after** parse → normalize → dedupe → (optional) website enrichment → (optional) Google Maps → **conflict resolution**. It sets:

- `contact_quality`: `verified` | `likely` | `low`
- `verification`: per-field validity, normalized values, and reasons (from `contact_parser` rules)

This doc shows how to exercise that with `runner.py` and sample data.

## Why a separate config file?

`config/sources.yaml` sets **`input.strict_contact_validation: true`** (default). That rejects rows with obviously bad email/phone/website **before** enrichment, which is what you usually want for production CSV hygiene.

The verification sample **intentionally** includes bad emails (`not-an-email`, `@@@`) so **`verify_lead`** can mark them `low`. Those rows would be dropped as `invalid_email` unless contact validation is relaxed.

**`config/sources_verification_local.yaml`** sets **`strict_contact_validation: false`** so every row reaches the pipeline and Week 3 verification. Identity rules (`required_any: company_name`) still apply.

## Prerequisites

1. **Python 3.11+** and dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. **No API keys required** for the recommended “verification-only” run (website + Google Maps disabled in config).

3. Optional — full pipeline (enrichment + Maps): copy `.env.example` to `.env` and set `SERPER_API_KEY` and/or `GOOGLE_MAPS_API_KEY` as needed.

## Recommended: offline verification sample

Use the dedicated CSV and local config so results depend mainly on **input email/phone**, not live HTTP or Maps.

**Files:**

- `sample_data/sample_leads_verification.csv` — one row per scenario (see table below).
- `config/sources_verification_local.yaml` — `website.enabled: false`, `google_maps.enabled: false`.

**Run:**

```bash
python runner.py run \
  --input sample_data/sample_leads_verification.csv \
  --input-format csv \
  --config config/sources_verification_local.yaml \
  --output output \
  --log-level info
```

**Artifacts:** under `output/<timestamp>/`:

- `leads_<timestamp>.json` — full leads including `contact_quality`, `verification`, `enrichment_history`
- `run_summary_<timestamp>.json` — run metadata and paths

### Expected rows (with `sources_verification_local.yaml`)

| `company_name` | Expected `contact_quality` | Why |
|----------------|------------------------------|-----|
| `Scenario_Verified_ZA_Both` | `verified` | Valid email + valid ZA mobile (E.164 path). |
| `Scenario_Likely_Email_Only` | `likely` | Only email valid. |
| `Scenario_Likely_Phone_Only` | `likely` | Only phone valid. |
| `Scenario_Likely_DisposableEmail_ValidPhone` | `likely` | Disposable email rejected; phone still valid (one channel). |
| `Scenario_Low_BadEmail_NoPhone` | `low` | Invalid email format; no valid phone. |
| `Scenario_Low_NoContacts` | `low` | No email and no phone. |
| `Scenario_Verified_US_E164` | `verified` | Valid email + valid US E.164 (`phonenumbers`). |
| `Scenario_Low_BothInvalid` | `low` | Invalid email + invalid phone. |

If any row differs, inspect `verification.email.reason` and `verification.phone.reason` on that lead in `leads_*.json`.

## Inspect results quickly

**Pretty-print one lead (requires [jq](https://jqlang.github.io/jq/)):**

```bash
LEADS=output/*/leads_*.json
# or set exact path from run_summary JSON
jq '.[] | select(.company_name=="Scenario_Verified_ZA_Both") | {company_name, contact_quality, verification}' "$(ls -t output/*/leads_*.json | head -1)"
```

**Table of all scenarios:**

```bash
jq -r '.[] | [.company_name, .contact_quality, (.verification.email.valid|tostring), (.verification.phone.valid|tostring)] | @tsv' "$(ls -t output/*/leads_*.json | head -1)" | column -t -s $'\t'
```

**Check enrichment history copy of verification:**

```bash
jq '.[] | {company_name, contact_quality, hist_verification: .enrichment_history.verification}' "$(ls -t output/*/leads_*.json | head -1)"
```

## Full pipeline (optional)

To test verification **together** with website scraping and Google Maps (slower, needs keys and network):

```bash
python runner.py run \
  --input sample_data/sample_leads_basic.csv \
  --config config/sources.yaml \
  --output output \
  --log-level info
```

Canonical `email` / `phone` may change after enrichment and conflict resolution; `contact_quality` and `verification` still reflect **final** values. Compare against the offline sample when you want deterministic verification behavior.

## Automated tests

Unit coverage for the same rules lives in `tests/test_verifier.py` (including international E.164 cases). Run:

```bash
python3 -m unittest tests.test_verifier -v
```
