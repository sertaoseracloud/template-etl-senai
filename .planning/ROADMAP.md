# Roadmap: template_etl

## Overview

The journey is one closed loop, proven once and then reproduced twice. Phase 1 builds the ground a `.sh` file can safely stand on (CRLF enforcement, pinned images, `.env`-only configuration) and gets the emulated Data Catalog populated by a single `./run.sh` subcommand. Phase 2 closes the loop — pure transform, thin Glue entrypoint, sample data, and a test suite that asserts output *content* — which is the point at which the project's core value ("clone, run one command, everything green, offline") actually exists. Phases 3 and 4 do not extend that loop; they reproduce it elsewhere. Terraform codifies the same shape against real AWS and CI re-runs the same `./run.sh` on every PR and on a schedule. Phase 4 makes the whole thing legible to a stranger who clicked "Use this template" and states plainly what passing locally does and does not prove.

## Phase Structure Rationale

**Granularity conflict, resolved:** `config.json` sets `granularity: "coarse"` (3-5 phases). The research SUMMARY proposed 7 phases. **This roadmap uses 4 phases** — the configured granularity wins, and the consolidation is not arbitrary:

| Research phases | Merged into | Why the merge is honest |
|---|---|---|
| 2 (transforms + unit tests), 3 (job entrypoint), 4 (integration test) | **Phase 2** | These three share a single success criterion and cannot be independently verified in any user-meaningful way. Unit tests passing with no job to run, or a job running with no content assertions, is not an observable deliverable for a developer adopting the template — it is a checkpoint. The deliverable is "one command → green," which only exists when all three are done. They become plans inside one phase, in the research's build order. |
| 5 (Terraform), 6 (CI) | **Phase 3** | Research's own framing: "Terraform and CI follow — they reproduce the already-proven local loop rather than gate it." They are the same kind of work (encode the proven topology somewhere else) and they are coupled: IAC-04 requires the Terraform checks to run *in* CI, so splitting them creates a cross-phase dependency that a merge turns into simple plan ordering. |
| 1 (environment + bootstrap), 7 (docs) | **Phases 1 and 4**, unchanged | Both are already coherent single deliverables. No compression applied. |

**What was deliberately not compressed:** Phase 4 (documentation) was not folded into Phase 3. For a public GitHub template repository the README, the known-differences table, and the rename instructions *are* the product surface — a developer's entire first experience is documentation. Folding it into an infrastructure phase would make it a trailing chore rather than a deliverable with its own success criteria.

## Ordering Constraints (non-negotiable)

These come from research and shape the sequence. They are not preferences.

1. **`.gitattributes` with `*.sh text eol=lf` must be committed before the first `.sh` file exists.** A CRLF checkout breaks the shebang (`bad interpreter` / `exec format error`) on any Windows clone. This is the first task of the first plan of Phase 1, not a later cleanup.
2. **The local loop must be green before Terraform and CI are written.** Both are designed to reproduce what `./run.sh` already does; building them against an unproven topology would encode an unverified shape in two more places.
3. **Transformation logic is separable from Glue wiring.** `transforms/` imports only `pyspark.sql`; `jobs/*/job.py` is the only file importing `awsglue`. This is what makes unit tests runnable without Glue or AWS at all (JOB-02, TEST-01), not a style preference — `awsglue` is not on PyPI.
4. **`from_catalog` is unavailable locally** (verified independently by two researchers). Local job I/O uses explicit `s3a://` paths via `from_options`. No phase or success criterion assumes a catalog-driven read from the job.
5. **Floci does not support `BatchCreatePartition`.** Partition registration is a `CreatePartition` loop — which is also forward-compatible with real AWS.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Local Environment, Entrypoint & Catalog Bootstrap** - Clean clone to a healthy emulator and a populated Data Catalog with one command, no AWS credentials
- [x] **Phase 2: ETL Job & Green Test Suite** - The core value: one documented command takes a clean clone all the way to green, offline
- [ ] **Phase 3: Terraform Module & Continuous Integration** - The proven loop codified for real AWS and re-proven on every PR and on a schedule
- [ ] **Phase 4: Public Documentation & Template Launch** - A stranger can adopt it, adapt it, and knows exactly what local green does not prove

## Phase Details

### Phase 1: Local Environment, Entrypoint & Catalog Bootstrap

**Goal**: A developer who has never seen the repo clones it, runs one subcommand, and has a healthy emulated AWS with a populated Glue Data Catalog — with no AWS credentials configured anywhere on their machine.
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02, ENV-03, ENV-04, ENV-05, ENV-06, ENV-07, RUN-01, RUN-02, RUN-03, CAT-01, CAT-02, CAT-03, CAT-04
**Success Criteria** (what must be TRUE):

  1. From a clean clone with no AWS credentials present, `./run.sh up` starts Floci (version-pinned tag, never `latest`) and reports it healthy before returning; no other container is started; `./run.sh down` leaves nothing running.
  2. `./run.sh bootstrap` runs in an ephemeral `python:3.11-slim` tools container that exits and removes itself, creating the database, table, and partitions in the emulated Catalog from a single versioned schema definition; running it a second time succeeds with no error and no duplicates (create-if-absent, update-if-present), confirmed by a boto3 `get_table`/`get_partitions` call against the endpoint. The ~4.77 GB Glue image is NOT pulled during this phase. *(Revised in phase discussion — see 01-CONTEXT.md D-05.)*
  3. `./run.sh --help` lists all eight subcommands (`up`, `down`, `bootstrap`, `seed`, `job`, `test`, `lint`, `demo`) with descriptions; `up`, `down`, `bootstrap`, `seed`, and `lint` complete successfully on a clean clone, and any subcommand that fails exits non-zero rather than continuing. *(Revised in phase discussion — see 01-CONTEXT.md D-11.)*
  4. Endpoint, region, credentials, bucket names, and database name appear in `.env` and nowhere else; copying `.env.example` unchanged is sufficient to satisfy criteria 1-3, and `.env.example` documents every variable the project reads.
  5. `.gitattributes` forcing `*.sh text eol=lf` exists in the repository history at or before the commit introducing the first `.sh` file, and `run.sh` behaves identically when invoked from Git Bash on Windows and bash on Linux.

**Plans**: 3/3 plans executed

Plans:

- [x] 01-01-PLAN.md — Repo scaffolding and container topology (complete 2026-08-06)
- [x] 01-02-PLAN.md — `run.sh` eight subcommands and preflight checks (complete 2026-08-07)
- [x] 01-03-PLAN.md — catalog/bootstrap.py, seed.py, sample CSVs, schema source of truth (complete 2026-08-07)

**Open questions to settle during planning**:

- **Single source of truth for the table schema between `bootstrap.py` and Terraform (CAT-03).** Highest-stakes open question in the project — if it is not settled here, the two definitions diverge silently and the divergence only surfaces in production. Research proposes `catalog/schema/*.json` consumed by both; the mechanism by which Terraform consumes it is *not* decided. Whatever is chosen here is binding on Phase 3.
- **`MSYS_NO_PATHCONV` effectiveness across Git Bash versions.** Only verifiable by hand on a real Windows machine — Linux CI cannot catch this class of bug. Plan an explicit manual verification step, not a CI check.
- **Floci operation fidelity beyond `BatchCreatePartition`.** Floci is a 2026 project with little third-party validation; "supported" in its docs may not mean "behaves like AWS" for every error shape and edge case. Mitigated structurally by endpoint-only isolation — plan to use standard boto3 calls only, never Floci-specific admin endpoints, so an emulator swap costs one env var.

### Phase 2: ETL Job & Green Test Suite

**Goal**: The core value exists — one documented command takes a clean clone from nothing to fully green (environment up, catalog populated, job executed, tests passing) with no AWS account, no credentials, and no manual step.
**Depends on**: Phase 1
**Requirements**: RUN-04, JOB-01, JOB-02, JOB-03, JOB-04, JOB-05, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):

  1. `./run.sh job` reads the sample CSV from the emulated S3 and writes Parquet back, succeeding with no AWS credentials present, using explicit `s3a://` paths via `from_options` (never `from_catalog`) with the complete S3A block — endpoint, `path.style.access`, SSL disabled, and `SimpleAWSCredentialsProvider` — applied as one unit.
  2. The transformation logic runs under `pytest` with a session-scoped `SparkSession` fixture and **no** `awsglue` import and no AWS reachable — a developer with only `pyspark` installed, outside any container, can run the unit tests and see them pass.
  3. The integration test asserts the **content** of the output (row count and values match the input), not merely a zero exit code, and separately queries the result through Athena so the Data Catalog path is exercised end to end.
  4. On a clean clone with no AWS credentials and no network access beyond the initial image pull, the single command documented for this purpose ends with every test green.
  5. Re-pointing the same job source at real AWS requires changing environment variables only — no source file contains an endpoint, bucket name, database name, or credential (checkable by grep).

**Plans**: 3 plans (indicative)

Plans:

- [x] 02-01: `transforms/csv_to_parquet.py` (pure, `DataFrame` in/out) + `tests/conftest.py` session-scoped Spark fixture + `tests/unit/` — TEST-01, TEST-02, TEST-05 delivered
- [x] 02-02: `data/sample/input.csv` + thin `jobs/csv_to_parquet/job.py` + `./run.sh job` wiring and the full S3A configuration block
- [x] 02-03: `tests/integration/` — content assertions via boto3 plus a dialect-portable Athena query; `./run.sh test` runs unit + integration

**Open questions to settle during planning**:

- **DuckDB vs Athena/Trino SQL dialect compatibility (TEST-04).** Floci runs Athena through a DuckDB sidecar; DuckDB, Presto, and Trino are genuinely different dialects. This decides whether the Athena assertion is real validation or theatre. Decide the portable SQL subset the template is allowed to ship as "verified" (research suggests `SELECT`/`WHERE`/`COUNT`/basic aggregates) and what gets documented as untested in Phase 4.
- Open: which committer algorithm to pin for local runs. S3A commit semantics on an emulator can produce silently incomplete output — content assertions (criterion 3) are the backstop, but the committer choice should be deliberate.

### Phase 3: Terraform Module & Continuous Integration

**Goal**: The loop proven in Phase 2 is reproduced in the two places it must survive without the author present — codified as Terraform for a real AWS account, and re-executed automatically on every pull request and on a schedule.
**Depends on**: Phase 2
**Requirements**: IAC-01, IAC-02, IAC-03, IAC-04, CI-01, CI-02, CI-03
**Success Criteria** (what must be TRUE):

  1. On a clean clone with no AWS credentials, `terraform init -backend=false`, `terraform fmt -check`, and `terraform validate` all pass for a module that declares the Glue Job, IAM role, S3 buckets, and Catalog database/table, pinning `hashicorp/aws ~> 6.0` (below 5.92.0 the provider rejects `python_version = "3.11"` with `glue_version = "5.0"`).
  2. Terraform's Catalog resources derive from the same schema definition `catalog/bootstrap.py` consumes — a developer changing a column in one place sees both paths change, with no second definition to keep in sync.
  3. The IAM policy names only the specific Glue, S3, and logging actions the sample job needs, scoped to named resources — no wildcard action and no wildcard resource, verifiable by reading the policy.
  4. Opening a pull request runs lint, the Terraform checks, and the full suite against Floci and reports green, with the workflow invoking `./run.sh` subcommands rather than restating compose and pytest steps.
  5. A scheduled workflow runs the same full loop on a cron with no repository change, so an upstream image or dependency breaking the template fails visibly in the Actions tab instead of in an adopter's first clone.

**Plans**: 2 plans (indicative)

Plans:

- [ ] 03-01: `terraform/` module — Glue Job, IAM least-privilege role, S3 buckets, Catalog resources fed by the Phase 1 schema source of truth
- [ ] 03-02: `.github/workflows/ci.yml` (PR: lint + terraform checks + full `run.sh` loop) and the scheduled drift-detection workflow

**Open questions to settle during planning**:

- **Caching the ~4.77 GB Glue image in CI.** It will dominate CI wall-clock time. Research recommends *against* `actions/cache` for the image itself (one entry would consume roughly half a repo's cache quota and likely lose to a direct pull from ECR Public) but flags this as reasoned, not measured. Measure the actual pull time first, then decide; small dependency caches (lint tooling, boto3) are worth caching regardless.
- **Carried from Phase 1:** the schema single-source mechanism chosen in Phase 1 planning is binding here. If Phase 1 left it unresolved, resolving it is a prerequisite for plan 03-01, not a Phase 3 decision.
- Note: `terraform plan` is deliberately **not** a success criterion — it requires real credentials, and PROJECT.md excludes applying to a real account from the definition of done. `validate` is the strongest check available offline, and this boundary must be stated in Phase 4's documentation.

### Phase 4: Public Documentation & Template Launch

**Goal**: A developer who clicked "Use this template" and has never spoken to the author can get to green, understand precisely which guarantees are real and which are emulated, and replace the sample pipeline with their own.
**Depends on**: Phase 3
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06
**Success Criteria** (what must be TRUE):

  1. A developer following only the README quick start reaches green without reading any source file, and every command the README shows appears in `./run.sh --help` (no drifted or invented subcommands).
  2. `docs/KNOWN_DIFFERENCES.md` states each local-vs-AWS divergence explicitly — IAM not enforced locally, job bookmarks nonexistent, no crawlers or `StartJobRun`, `from_catalog` unavailable locally, Athena-via-DuckDB dialect gap, Terraform validated but never applied — so a reader knows that passing locally proves the Spark logic and proves nothing about IAM.
  3. The README states exactly what an adopter must rename or replace after using the template (project name, bucket names, database name, job name, module paths), with no step left implicit — there is no cookiecutter to do it for them.
  4. LICENSE (MIT), CONTRIBUTING.md, and issue templates are present, and CONTRIBUTING states the maintenance boundary: PRs improving the scaffolding are welcome, PRs elaborating the sample job's business logic are redirected.
  5. The README carries a live CI status badge pointing at the Phase 3 workflow, so a visitor can see at a glance whether the template currently works.

**Plans**: 1 plan (indicative)

Plans:

- [ ] 04-01: README (quick start, structure, architecture, "how to adapt", rename checklist, badge), `docs/KNOWN_DIFFERENCES.md`, LICENSE, CONTRIBUTING.md, issue templates

**Open questions to settle during planning**:

- **Carried from Phase 2:** whatever the DuckDB/Athena dialect investigation concluded must land verbatim in `docs/KNOWN_DIFFERENCES.md`. If the boundary was never characterised, this phase cannot honestly document it.
- **Carried, continuous:** Floci fidelity gaps discovered during Phases 1-3 belong in the known-differences table rather than being quietly absorbed.

## Scope Guardrail

Research flagged over-scaffolding as a planning-discipline pitfall rather than an implementation bug: every "realistic touch" added to the sample job is something an adopter must first understand and then delete. PROJECT.md's Out of Scope list (no medallion pipeline, no Iceberg, no second table, no joins, no partitioned-write demo) is a hard boundary during phase planning and code review. If a plan grows the sample job beyond "read CSV, minimal transform, write Parquet, register in Catalog," challenge it against a requirement ID — if none exists, it is v2.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

Core value is delivered at the end of Phase 2. Phases 3 and 4 reproduce and explain that loop; neither gates it.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Local Environment, Entrypoint & Catalog Bootstrap | 3/3 | Complete | 2026-08-07 |
| 2. ETL Job & Green Test Suite | 2/3 | In Progress | — |
| 3. Terraform Module & Continuous Integration | 0/2 | Not started | — |
| 4. Public Documentation & Template Launch | 0/1 | Not started | — |

---
*Roadmap created: 2026-08-06*
