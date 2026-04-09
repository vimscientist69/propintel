# Final Project Polishing Checklist

Purpose: move PropIntel from "working MVP" to "publish-ready portfolio project" for GitHub, LinkedIn, and Upwork **today**.

This checklist is intentionally pragmatic: robust enough to build trust, small enough to finish quickly.

---

## 1) Inverse review: what a client/reviewer will question

If someone evaluates this project for real work, they will ask:

1. Can I run it fast with confidence?
2. Is it safe with API limits and failures?
3. Can I see proof it works (tests + demo flow)?
4. Is deployment clearly explained?
5. Are outputs stable and understandable for non-authors?

This doc closes those gaps without expanding scope.

---

## 2) Must-do before publishing today (high impact)

## A. Add CI pipeline (currently missing)

- Add GitHub Actions workflow to run:
  - `python -m unittest`
  - optional frontend build check (`npm run build` in `frontend/dashboard`)
- Cache pip/npm dependencies for speed.
- Fail PRs on test failure.

Acceptance:
- Every push/PR shows a green or red CI status badge.

---

## B. Harden environment + secrets hygiene (no docs task)

- Ensure `.env.example` is complete and current:
  - `GOOGLE_MAPS_API_KEY`
  - `SERPER_API_KEY`
- Verify no secrets in git-tracked files and no accidental credential artifacts.
- Rotate any real keys used during development before going public.

Acceptance:
- No secrets in repository/worktree.

---

## C. Add concurrency/rate-limit tests (new feature coverage)

You already implemented runtime concurrency + provider limiters. Add focused tests:

- config schema tests for provider runtime options (partially done; extend edge cases)
- ingestion tests:
  - worker concurrency >1 preserves output order
  - limiter-constrained execution does not crash with many rows
  - provider retry defaults apply when advanced knobs omitted

Acceptance:
- New concurrency path has direct test coverage (not only happy path).

---

## 3) Should-do next (after publish today)

## A. Structured error taxonomy

- Normalize common errors into stable codes:
  - `rate_limited_google_maps`
  - `rate_limited_serper`
  - `network_timeout`
  - `invalid_input_schema`
- Return code + message in API responses and job error fields.

Why: clients care about operability, not stack traces.

---

## B. Basic observability counters

- Add run summary counters for:
  - retries attempted per provider
  - rate-limit hits (429s) per provider
  - per-batch elapsed seconds
- Expose these in job metadata (or batch endpoint) for dashboard visibility.

Why: shows production engineering maturity with little extra complexity.

---

## 4) UX polish items worth one small pass

- Add explicit "partial results" badge in Control Panel/Data Explorer when job status is processing.
- Show job progress in job list rows (`completed/total batches`) for active processing jobs.
- Add empty-state helper text for settings JSON payload with a minimal valid template.
- Increase vertical spacing rhythm in Data Explorer rows/cards for better scanability on mobile/tablet.
- Fix Control Panel horizontal overflow on mobile:
  - slightly reduce heading/body font sizes on narrow screens
  - reduce button/input padding and minimum widths
  - ensure action buttons wrap cleanly without forcing x-axis scroll
  - keep file-picker and filter controls at `width: 100%` on small screens

---

## 5) Suggested publish gate (Definition of Ready-to-Share)

Publish when all checks below pass:

- [x] CI workflow exists and is green on default branch.
- [x] Concurrency/rate-limit feature has dedicated tests.
- [x] No secrets in repository; `.env.example` complete.
- [x] Dashboard responsive behavior verified on mobile/tablet/desktop.

---

## 6) 2-day execution plan (small, realistic)

Day 1:
- CI workflow + badges + quick lint/test commands in README.

Day 2:
- Concurrency/rate-limit tests.
- Secrets hygiene check + final sanity pass + publish.

---

## 7) Final note

The project already has strong core value: ingestion, enrichment, scoring, batching, resume, dashboard, and settings profiles.

The remaining work is mostly trust-building polish (CI, runtime safety, and UX consistency). That is enough for a strong "publish today" version.

