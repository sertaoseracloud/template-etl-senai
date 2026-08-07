---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
status: completed
stopped_at: Phase 02 context gathered
last_updated: "2026-08-07T14:31:35.284Z"
last_activity: 2026-08-07
last_activity_desc: Phase 01 marked complete
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
current_phase_name: local-environment-entrypoint-catalog-bootstrap
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-06)

**Core value:** Clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.
**Current focus:** Phase 01 — local-environment-entrypoint-catalog-bootstrap

## Current Position

Phase: 01 — COMPLETE
Plan: 3 of 3
Status: Phase 01 complete
Last activity: 2026-08-07 — Phase 01 marked complete

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 36m | 3 tasks | 7 files |
| Phase 01 P02 | 25m | 2 tasks | 2 files |
| Phase 01 P03 | 75min | 4 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 4 phases, not the research's 7 — `granularity: coarse` respected. Research phases 2/3/4 merged into Phase 2 (they share one success criterion and are not independently verifiable); 5/6 merged into Phase 3 (both reproduce the proven loop; IAC-04 couples them). Rationale recorded in ROADMAP.md.
- [Roadmap]: Core value lands at end of Phase 2. Terraform and CI reproduce the local loop, they do not gate it.
- [Roadmap]: `terraform plan` is not a success criterion anywhere — it needs real credentials, and PROJECT.md excludes applying to a real account from "done". `init -backend=false` + `fmt -check` + `validate` are the offline-verifiable checks.
- [Phase ?]: boto3/ruff pinned by compatible-release range (~=), not exact ==, per checkpoint-approved operator decision (01-01). Formally accepted as an override in `01-VERIFICATION.md` (2026-08-07) — accepted_by "operador (sessão 2026-08-07), checkpoint de legitimidade de pacotes, commit 1826d3c".
- [Phase ?]: floci's built-in HEALTHCHECK confirmed via docker image inspect; no healthcheck: key authored in compose (01-01)
- [Phase ?]: run.sh preflight/dispatcher/eight subcommands built exactly per 01-CONTEXT.md D-05/D-09-D-13, verified end-to-end against real Docker Desktop
- [Phase ?]: pyproject.toml: extend-exclude=['.planning'] added to [tool.ruff] — ruff 0.16 formats Python fences in Markdown by default, which broke 'run.sh lint' against research docs (Rule 3 auto-fix)
- [Phase ?]: [Phase 01-03] D-08 assumed Glue UpdateDatabase/UpdateTable; Floci implements neither (InvalidAction). Resolution: keep update_* calls (correct against real AWS), catch InvalidAction specifically, diff current vs desired and log drift instead of silently claiming sync. Schema edits require an emulator restart (./run.sh down && ./run.sh up) to apply locally. MUST land in docs/KNOWN_DIFFERENCES.md in Phase 4.
- [Phase ?]: [Phase 01-03] Task 4 (ENV-06 manual Windows Git Bash verification) executed for real and approved: bash 5.3.15(1)-release (x86_64-pc-cygwin), Docker 28.4.0, Compose v2.39.2-desktop.1. MSYS_NO_PATHCONV=1 confirmed to neutralize real MSYS2 path-rewriting on this specific Git Bash version - not a general claim, other versions remain untested.
- [Phase ?]: [Phase 01-03] Phase 4 harvest: any docker compose invocation with a container-side path argument run OUTSIDE run.sh breaks on Git Bash (MSYS2 rewrites the path before Docker sees it). Must land in docs/KNOWN_DIFFERENCES.md AND get a README line - it's the first thing an adopter debugging an ad hoc docker compose command on Windows will hit.
- [Verification, 2026-08-07]: Phase 1's two `verification: backstop` concurrency truths (concurrent `./run.sh up`, concurrent `./run.sh bootstrap`) are resolved with live evidence — see `01-CONCURRENCY-EVIDENCE.log` (commit `b3888fa`) and independent reproduction recorded in `01-VERIFICATION.md`. Both close phase 1 with no further action.
- [Phase 2 scope — informs Phase 2 planning only, not a Phase 1 requirement]: the `csv_to_parquet` job writes in **append** mode. Consequently `spark.sql.sources.partitionOverwriteMode` is **N/A** — there is no dynamic-overwrite behavior to configure. The project's stated scope is an academic/local simulation environment, not a daily-refresh production pipeline: the job reprocesses the same three dates already seeded by Phase 1's `catalog/schema/temperaturas.json`, so the fixed three-partition `CreatePartition` loop built in Phase 1 is adequate by design — it exists to demonstrate the loop, not to operate a rolling daily pipeline, and this closes the "partition drift" concern raised during Phase 1 planning without further work. **Phase 4 README consequence to write down:** with `append` mode, running `./run.sh demo` twice without a `./run.sh down` in between duplicates rows within the same partition. This is the chosen mode working as intended, not a defect — but an adopter who runs `demo` twice and sees the row count double needs this explained, or they will conclude the template is broken.

### Pending Todos

None yet.

### Blockers/Concerns

- **REQUIREMENTS.md stated 36 v1 requirements; the actual count is 38.** Corrected in the traceability section. No requirement was lost — the header count was simply wrong.
- **RESOLVED (01-03): Schema single source of truth (CAT-03).** `catalog/schema/temperaturas.json` is the single file, consumed directly by `catalog/bootstrap.py` via `json.load`; Phase 3's Terraform must reproduce `catalog/config.py`'s exact two `.replace()` calls when it consumes the same file.
- **PARTIALLY RESOLVED (01-03): `MSYS_NO_PATHCONV` efficacy.** The Phase 1 manual verification step ran for real on Windows Git Bash and confirmed the guard neutralizes MSYS2 path-rewriting — but scoped to `bash 5.3.15(1)-release (x86_64-pc-cygwin)` specifically. Cross-version drift across other Git Bash releases remains genuinely untested; do not treat this as resolved in general.
- **DuckDB vs Athena/Trino dialect gap (TEST-04) undetermined.** Decides whether the Athena assertion in Phase 2 is validation or theatre; the conclusion must reach `docs/KNOWN_DIFFERENCES.md` in Phase 4.
- **Floci is a 2026 project with little third-party validation.** `BatchCreatePartition` is already known missing; 01-03 additionally found no `Update*` Glue action is implemented at all (see decisions above). Mitigation is structural: standard boto3 calls only, endpoint-only isolation, pinned image tag.
- **IAM is never enforced locally.** No local run can validate the Terraform policy. Phase 3 authors it on faith; Phase 4 must say so plainly.
- **RESOLVED (verification, 2026-08-07): both Phase 1 concurrency backstops.** `./run.sh up` x2: one invocation completes green (`[ok] start emulator` / `[ok] bootstrap catalog` / `[ok] seed sample data`), the other fails fast at the compose-up step with a Docker daemon container-name conflict (`Error response from daemon: Conflict. The container name "/template_etl-floci-1" is already in use...`) and never reaches bootstrap/seed — catalog stays whole (3 tables, 3 distinct partitions, both buckets, 3 raw objects). `./run.sh bootstrap` x2-x3 concurrent: both/all exit 0, catalog converges to exactly 3 partitions with no duplicates every round. Confirmed twice independently: the persisted `01-CONCURRENCY-EVIDENCE.log` (commit `b3888fa`) and a live re-run during Phase 1 verification with fresh container SHAs (not replayed). Full detail in `01-VERIFICATION.md`.
- **NEW (verification, 2026-08-07): third Phase 4 `docs/KNOWN_DIFFERENCES.md` item — Floci `GetTables` fidelity gap.** `GetTables` on a nonexistent database returns an empty list (`[]`) where real AWS Glue raises `EntityNotFoundException`. Verified live: `get_tables('template_etl_db')` → `['temperaturas']`; `get_tables('template-etl_db')` (the wrong derivation — hyphen not replaced by `catalog/config.py`'s `.replace('-','_')`) → `[]`; `get_tables('nao_existe_de_jeito_nenhum')` → `[]`. Practical consequence, worth stating plainly in the docs: against Floci, a nonexistent database and an empty one are indistinguishable through `GetTables` — confirm the database name (via `catalog/config.py`'s derivation, not string concatenation) before suspecting the data itself. This is exactly the mistake a first-time forker is likely to repeat.
- **Phase 4 owes three `docs/KNOWN_DIFFERENCES.md` entries now** (Floci `Update*` gap; `docker compose` outside `run.sh` breaking on Git Bash — needs a README line too; Floci `GetTables` fidelity gap on a nonexistent database — see above). See decisions above for exact wording of the first two.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-07T14:31:35.262Z
Stopped at: Phase 02 context gathered
Resume file: .planning/phases/02-etl-job-green-test-suite/02-CONTEXT.md
