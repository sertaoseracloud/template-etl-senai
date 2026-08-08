# Phase 04: Public Documentation & Template Launch - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the public-facing surface of a GitHub template repository: a README that lets a stranger clone, adapt, and run without reading source code; a KNOWN_DIFFERENCES table; CONTRIBUTING.md; MIT LICENSE; and GitHub issue templates.

**In scope:** `README.md` (onion structure: Quick Start → Architecture → Project Structure → How to Adapt → Known Differences → Contributing), `docs/KNOWN_DIFFERENCES.md`, `LICENSE`, `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/` (bug report, feature request).

**Out of scope:** Any new code, infrastructure, or tests. This phase wraps what Phases 1–3 built.
</domain>

<decisions>
## Implementation Decisions

### README structure — onion (user selected)

- **D-01:** README sections in this order:
  1. **Quick Start** — clone → Docker → one command (`./run.sh demo`) → green. Stops there; no more steps.
  2. **Architecture** — explains the Floci emulator, the S3 (raw / curated) flow, the Glue job, and the Glue Data Catalog. The pipeline shape is `s3 (raw) → event bridge → Glue job → s3 (curated)`; the sample job is the only job.
  3. **Project Structure** — top-level directories and files, one sentence each.
  4. **How to Adapt** — rename checklist (PROJECT_NAME, cities, columns, Glue version). Minimal.
  5. **Known Differences** — cross-references `docs/KNOWN_DIFFERENCES.md`, does not duplicate it.
  6. **Contributing** — cross-references `CONTRIBUTING.md`.
  Every command shown in the README must appear in `./run.sh --help` — no invented subcommands.
  — **Reversibility:** reversible — restructuring headings costs a rewrite pass.

### Rename/adapting section — minimal list (user selected)

- **D-02:** The "How to Adapt" section is a checklist, not a guide. Enumerates exactly what must change:
  - `PROJECT_NAME` in `.env` (the single variable that drives all names per D-16 Phase 1)
  - `PROJECT_NAME` in `.env.example` (keep in sync)
  - City data in `data/sample/` (synthetic dataset, must be relabelled if adapted)
  - Temperature column logic in `transforms/csv_to_parquet.py` if column names change
  - Database, bucket, and job names derived automatically from `PROJECT_NAME`
  - Glue version in `terraform/variables.tf` if needed
  Decision guide and copy-paste commands were rejected — the template's job is scaffolding, not teaching.
  — **Reversibility:** reversible — adding more detail costs a rewrite; removing detail costs nothing.

### CI status badge — ci.yml only (user selected)

- **D-03:** README carries one Shields.io badge pointing at the `ci.yml` workflow.
  Format: `[![CI](https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/<repo>/actions/workflows/ci.yml)`
  Shows whether the template currently passes its PR checks on `main`. Drift badge excluded — it runs on schedule and its failures are a maintenance concern, not a template health signal.
  — **Reversibility:** reversible — adding/removing a badge costs one line.

### Contributing scope — scaffolding only (user selected)

- **D-04:** CONTRIBUTING.md states the maintenance boundary explicitly:
  - **In scope:** PRs that improve the scaffolding (run.sh, tests, Terraform, docs, CI)
  - **Out of scope:** PRs that elaborate the sample job's business logic — those belong in the adopter's own project or a fork
  MIT LICENSE.
  — **Reversibility:** one-way — the license and contributing scope are published contracts; changing them after launch requires a major version bump and community notice.

### Three known-differences items already documented in STATE.md

These three items have exact wording drafted. They must appear verbatim (or substantively equivalent) in `docs/KNOWN_DIFFERENCES.md`:

- **D-05:** **Floci Update* gap:** No Glue `UpdateDatabase` or `UpdateTable` is implemented by Floci. Schema edits locally require `./run.sh down && ./run.sh up` — a running container cannot absorb schema changes. This does not affect `bootstrap.py`'s idempotency (create-if-absent / update-if-present catches `AlreadyExistsException` correctly); it only affects schema edits to a live environment.
- **D-06:** **Docker commands outside run.sh break on Git Bash:** Running `docker compose` (or `docker-compose`) with a container-side path argument directly in Git Bash on Windows silently misinterprets the path via MSYS2 path rewriting before Docker sees it. `run.sh` guards this with `MSYS_NO_PATHCONV=1` internally. Any ad-hoc `docker compose` command typed outside `./run.sh` is unreliable on Windows. A README callout is warranted.
- **D-07:** **Floci GetTables fidelity gap:** `GetTables` on a nonexistent database returns an empty list (`[]`) where real AWS Glue raises `EntityNotFoundException`. Against Floci, a nonexistent database and an empty one are indistinguishable through `GetTables` alone — confirm the database name before suspecting the data itself.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase decisions that define what this phase must document
- `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-CONTEXT.md` — D-01 (schema JSON single source), D-07 (Glue image first-pull warning), D-11 (8 subcommands), D-14 (SC cities, synthetic data), D-15 (synthetic data labelled), D-16 (PROJECT_NAME drives all names)
- `.planning/phases/02-etl-job-green-test-suite/02-CONTEXT.md` — D-01 (portable SQL subset), D-05 (append mode + row duplication), D-09 (reads prefix, not a single CSV), D-12 (compound partitioning, 18 partitions)
- `.planning/phases/03-terraform-module-continuous-integration/03-CONTEXT.md` — D-09 (CI invokes run.sh), D-10 (drift workflow), D-11 (IAM least-privilege, no wildcard)
- `.planning/STATE.md` §"Accumulated Context / Decisions" — exact wording for three KNOWN_DIFFERENCES entries (Floci Update*, docker compose outside run.sh, GetTables gap)

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` §"Documentação" — DOC-01…DOC-06; D-03 links DuckDB/Athena dialect conclusion here
- `.planning/ROADMAP.md` §"Phase 4" — goal, success criteria, and the two carried open questions

### What must NOT be claimed
- Terraform is validated offline, never applied in CI (IAC-04, confirmed in ROADMAP Phase 3 open questions)
- IAM is never enforced locally (no local run validates the Terraform policy)
- `./run.sh demo` twice without `down` in between duplicates rows — this consequence of append mode must be stated (D-05 Phase 2)
</canonical_refs>

<code_context>
## Existing Code Insights

### What's already in the repo
- `docs/LOCAL_DEV.md` — existing local dev guide; README should not duplicate it, may cross-reference
- `.github/workflows/ci.yml` and `.github/workflows/drift.yml` — exist from Phase 3; ci.yml is the badge target
- `catalog/config.py` — the single place where `PROJECT_NAME` derives all names (D-16 Phase 1); README's rename checklist mirrors this
- `data/sample/` — three CSVs with SC cities (Florianópolis, Joinville, Blumenau, Chapecó, Lages, Criciúma); synthetic data must be relabelled if adapted
- `terraform/` — validated but never applied; this boundary must be stated plainly

### Patterns established by prior phases
- Lean output with full detail on failure (D-12 Phase 1) — README's quick start should mirror this ethos: minimal surface, no walls of text
- Eight subcommands (D-11 Phase 1) — the `--help` output is the authoritative subcommand list
- Synthetic data labelled as synthetic (D-15 Phase 1) — README must state this explicitly, same as `data/sample/`

### What stays in scope vs. what goes in KNOWN_DIFFERENCES
KNOWN_DIFFERENCES must cover:
- IAM not enforced locally
- Job bookmarks nonexistent locally
- No crawlers or `StartJobRun` (Floci doesn't emulate them)
- `from_catalog` unavailable locally (JVM closed-source client)
- Athena-via-DuckDB dialect gap (portable SQL subset: SELECT/WHERE/COUNT/AVG/GROUP BY/ORDER BY only)
- Terraform validated offline, never applied
- Three STATE.md items (D-05, D-06, D-07 above)

KNOWN_DIFFERENCES must NOT cover:
- Any capability that the template claims to offer but doesn't deliver
- Any behavior that is correctly documented elsewhere in the README
</code_context>

<specifics>
## Specific Ideas

- **Placeholder values:** README and workflows will contain `<org>/<repo>` as placeholders; the planner decides the exact form (search-and-replace tokens, or explicit template-org/template-repo in the initial commit)
- **Badge URL:** `https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg` — the planner inserts the actual org/repo before commit
- **Known differences table format:** one table with columns: What's different | Local (Floci) | Real AWS | Impact | Workaround
- **Issue templates:** bug report (with environment info: OS, Docker version, Floci version) and feature request (with "does this belong in the template or your project?" prompt)
- **docs/LOCAL_DEV.md relationship:** README is for strangers; LOCAL_DEV.md is for people already in the repo. README should not duplicate LOCAL_DEV.md content; cross-reference if needed.
</specifics>

<deferred>
## Deferred Ideas

### Phase 2/v2 items not in scope for Phase 4
- **AD2-01:** GitHub Action that renames the project after "Use this template" — acknowledged in Out of Scope
- **AD2-02:** SQL portability guide between DuckDB and Athena/Trino — Phase 2 concluded the portable subset; the full guide is its own Phase 2/v2 item

### Could be added later without touching the scaffold
- `docs/ARCHITECTURE.md` — deep dive on the pipeline shape, for adopters who want to understand before touching code
- `docs/TROUBLESHOOTING.md` — common failure modes and fixes, populated from real adopter questions after launch
- Badges for Terraform validation and Drift detection in addition to CI — deferred until there's evidence adopters need them
</deferred>

---

*Phase: 04-Public Documentation & Template Launch*
*Context gathered: 2026-08-09*
