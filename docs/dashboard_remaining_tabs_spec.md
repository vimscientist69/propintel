# Dashboard Remaining Tabs Spec

This document defines the remaining dashboard tabs for PropIntel:

- Analytics
- Job History
- Data Explorer
- Engine Settings

It is intentionally product-first (what the final result should feel like), then implementation-first (how to build it safely with current API + pipeline architecture).

---

## 1) End Product Vision (High-Level Result)

After Week 4, the dashboard should feel like a complete lead-intelligence workstation, not just a job launcher:

- **Control Panel** (already built): create/monitor/terminate jobs.
- **Analytics**: immediate visibility into lead quality and pipeline outcomes (score distribution, contact quality, chatbot/freshness signals, source mix).
- **Job History**: reliable audit trail for every run, with timeline and run-level diagnostics.
- **Data Explorer**: searchable/filterable lead table across one or more jobs, optimized for lead triage and export.
- **Engine Settings**: editable runtime config profile for enrichment/scoring behavior, with validation and safe apply workflow.

The target user should be able to:

1. Launch a run
2. Diagnose quality/performance in Analytics
3. Compare with prior runs in Job History
4. Drill into rows in Data Explorer
5. Tune settings in Engine Settings
6. Re-run and verify improvements

---

## 2) Information Architecture + Navigation

### Tabs and purpose

- **Control Panel**
  - Job creation + live controls.
- **Analytics**
  - Read-only KPI and distribution dashboards.
- **Job History**
  - Run ledger + per-run detail (counts, status, errors).
- **Data Explorer**
  - Row-level exploration with filters and export.
- **Engine Settings**
  - Config management and profile controls.

### Routing proposal (React + Vite + React Router)

- `/` -> Control Panel
- `/analytics`
- `/jobs` (history list)
- `/jobs/:jobId` (job detail panel)
- `/explorer`
- `/settings`

---

## 3) Tab Specs

## 3.1 Analytics Tab

### End-state UX

Analytics should answer: "Is the pipeline producing good leads, and where is quality lost?"

Page layout:

- **Top KPI cards**:
  - Total jobs (window)
  - Completed jobs
  - Average lead score
  - Verified contact rate
- **Charts**:
  - Lead score histogram (0-100 buckets)
  - Contact quality split (`verified/likely/low`)
  - Chatbot signal split
  - Freshness signal split
  - Source composition (`input`, `google_maps`, mixed)
- **Ops diagnostics**:
  - Enrichment errors count
  - Google Maps match rate
  - Rejected row reasons top N

### Implementation details

#### Data requirements

Reuse existing data first:

- `GET /jobs` (paginated jobs + counts)
- `GET /jobs/{id}/results` (completed leads)
- `GET /jobs/{id}/rejected`

Short-term aggregation strategy:

- Fetch recent completed job IDs (limit configurable - input with values 10, 25, 50, 100, 1000, etc, default 10)
- Aggregate in frontend for MVP
- Cache in-memory per session

Future API (optional performance):

- `GET /analytics/summary?window=30d`
- `GET /analytics/distributions?...`

#### UI components

- `KpiCard`
- `MetricDelta` (optional trend vs previous window)
- `BarChart`, `DonutChart` (lightweight chart lib)
- `DiagnosticsList`

#### Empty/error states

- No completed jobs -> “Run first job” call-to-action
- Partial unavailable data -> show degraded cards with warning chip

---

## 3.2 Job History Tab

### End-state UX

Job History should be the system of record for runs.

Page layout:

- **Jobs table** with:
  - Job ID
  - Created/Started/Completed time
  - Status (`uploaded/processing/completed/failed/terminated`)
  - Input format
  - Key counts (`mapped_valid_rows`, `deduped_rows`, `rejected_rows`, `scored_rows`)
- **Filters**:
  - status, date range, input format
- **Row click detail drawer/panel**:
  - counts JSON (formatted)
  - rejected reason summary
  - error details
  - quick actions: open in Data Explorer, export csv/json, re-run with same settings (future)

### Implementation details

#### API usage

- Existing:
  - `GET /jobs` with `limit/offset/status`
  - `GET /jobs/{id}`
  - `GET /jobs/{id}/rejected`
  - `GET /jobs/{id}/export`
- Recommended extension:
  - add `created_at_from`, `created_at_to` query filters in `GET /jobs`

#### UI components

- `JobsTable`
- `StatusPill`
- `JobDetailDrawer`
- `PaginationBar`

#### Behavior

- Poll only for rows currently in `processing/uploaded`
- Preserve selected row in URL (`/jobs/:id`)

---

## 3.3 Data Explorer Tab

### End-state UX

Data Explorer should be the lead analyst’s workspace.

Page layout:

- **Scope selector**:
  - single job OR multiple recent jobs OR “all completed in window”
- **Filter bar**:
  - min/max score
  - contact quality
  - chatbot yes/no
  - freshness signal
  - source contains
  - text search (`company_name`, `location`, `email`, `website`)
- **Results table**:
  - sortable columns
  - sticky header
  - row expansion for `enrichment_history` / `verification` / `lead_reason`
- **Actions**:
  - export current filtered set
  - copy selected fields

### Implementation details

#### MVP data path

- Start with selected job:
  - `GET /jobs/{id}/results`
- For multi-job mode:
  - pull N job results and merge client-side
  - include `job_id` per row in view-model

#### Recommended backend extension (for scale)

- `GET /leads/query` endpoint:
  - supports pagination, sort, filters
  - optionally backed by a normalized leads table in SQLite/Postgres

#### UI components

- `ExplorerFilterBar`
- `LeadsDataTable`
- `LeadDetailPanel`
- `ColumnVisibilityMenu`

#### Performance guardrails

- Virtualized table once >1000 rows
- Debounced text search
- Memoized filtered datasets

---

## 3.4 Engine Settings Tab (Needed)

### Why this tab is needed

As soon as multiple runs exist, users will want controlled tuning without editing YAML manually. Engine Settings turns config into a first-class product surface.

### End-state UX

Page layout:

- **Profiles**:
  - default
  - staging
  - custom profile(s)
- **Config sections**:
  - Website enrichment settings
  - Google Maps settings
  - Scoring weights
  - Input strictness flags
- **Actions**:
  - Validate
  - Save draft
  - Activate profile
  - Reset section

### Implementation details

#### Backend requirements

Add settings endpoints:

- `GET /settings` -> current active settings (redacted secrets)
- `PUT /settings` -> validate + save
- `POST /settings/validate` -> dry-run validation only
- `POST /settings/activate-profile`

Config safety:

- Strict schema validation (Pydantic)
- Redact secrets from API responses
- Version settings changes (`updated_at`, `updated_by`, `version`)

#### Persistence strategy

- MVP: store editable settings JSON in SQLite table:
  - `settings_profiles(id, name, payload_json, is_active, created_at, updated_at)`
- Runtime load:
  - API job runner reads active profile
  - CLI may continue using YAML path by default, with optional profile override later

#### UI components

- `SettingsProfileSwitcher`
- `SettingsFormSection`
- `ValidationBanner`
- `DiffPreview` (optional but valuable before apply)

---

## 4) Shared UI/UX Standards For All Tabs

- Consistent 8px spacing system (`4/8/12/16/24/32`)
- Stable typography scale (Inter, predictable heading hierarchy)
- Unified control primitives:
  - `Button`, `Input`, `Select`, `Card`, `Table`, `Badge`, `Tabs`
- Loading states:
  - skeletons for cards/table
  - inline spinner for panel actions
- Error states:
  - actionable text + retry
- URL-driven state:
  - filters, sort, pagination in query params
- Accessibility:
  - keyboard nav, visible focus, semantic labels, aria attributes

---

## 5) Technical Architecture (React)

Recommended stack evolution:

- React + Vite
- React Router (tab/page routes)
- TanStack Query (server-state + caching + polling control)
- TanStack Table (Data Explorer and Job History)
- Recharts (or similar) for Analytics visualizations
- Component styling:
  - Tailwind + shadcn-style primitives OR
  - current CSS with component-level modularization

Suggested structure:

- `src/pages/{ControlPanel,Analytics,JobHistory,Explorer,Settings}.jsx`
- `src/components/ui/*`
- `src/components/analytics/*`
- `src/components/history/*`
- `src/components/explorer/*`
- `src/components/settings/*`
- `src/lib/api.js`
- `src/lib/formatters.js`

---

## 6) API + Data Gaps To Close

Current API is enough for a baseline, but these additions unlock better tabs:

1. `GET /jobs` date range filters
2. aggregated analytics endpoint(s) to avoid heavy client joins
3. leads query endpoint with server-side filtering/pagination
4. settings CRUD/validate endpoints
5. consistent status semantics for terminal states (`completed`, `failed`, `terminated`)

---

## 7) Phased Implementation Plan

### Phase A (fast value)

- Build Job History + Data Explorer from existing endpoints.
- Add React Router and page shells.
- Add shared UI primitives and spacing tokens.

### Phase B (analytics)

- Build Analytics page with client aggregation over recent jobs.
- Add cached query layer and chart components.

### Phase C (engine settings)

- Implement backend settings endpoints + SQLite profile table.
- Build Settings page with validation + activate flow.

### Phase D (scale/perf)

- Add server-side leads query endpoint.
- Move heavy analytics aggregation to backend endpoint(s).
- Add virtualization and advanced filtering.

---

## 8) Definition of Done (Remaining Tabs)

- [ ] Analytics tab provides KPI cards + at least 3 distribution views.
- [ ] Job History tab supports pagination, status filter, and detail panel.
- [ ] Data Explorer supports score/quality/search filters and export.
- [ ] Engine Settings supports view/edit/validate/save/activate profile.
- [ ] Shared spacing/typography/components are consistent across tabs.
- [ ] All new backend endpoints are tested and documented.
- [ ] A user can run -> analyze -> inspect -> tune -> rerun entirely from dashboard.
