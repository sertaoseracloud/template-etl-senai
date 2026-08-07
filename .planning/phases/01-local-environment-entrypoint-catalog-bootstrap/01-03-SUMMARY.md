---
phase: 01-local-environment-entrypoint-catalog-bootstrap
plan: 03
subsystem: infra
tags: [boto3, glue, s3, floci, catalog, idempotency, synthetic-data, msys, git-bash]

requires:
  - phase: 01-01
    provides: docker-compose.yml (tools service, python:3.11-slim, read-only .:/workspace mount), .env.example, pyproject.toml (ruff config)
  - phase: 01-02
    provides: run.sh (cmd_bootstrap invokes `python catalog/bootstrap.py`, cmd_seed invokes `python catalog/seed.py`, both in the tools service; MSYS_NO_PATHCONV=1 platform guard)
provides:
  - catalog/schema/temperaturas.json (single source of truth for the temperaturas table - CAT-03)
  - catalog/config.py (PROJECT_NAME-derived resource names, endpoint-bound boto3 clients, read-only schema loader)
  - catalog/bootstrap.py (idempotent database/table/partition registration)
  - catalog/seed.py (bucket creation and sample CSV upload)
  - data/sample/*.csv + README.md (three synthetic daily-temperature CSVs, labelled synthetic)
  - Empirical, machine-specific evidence that run.sh's MSYS_NO_PATHCONV=1 guard neutralizes real MSYS2 path-rewriting (ENV-06)
affects: [phase-3-terraform (consumes catalog/schema/temperaturas.json), phase-4-docs (docs/KNOWN_DIFFERENCES.md must record two items - the Floci Update-action gap and the docker-compose-outside-run.sh MSYS path-rewrite gotcha; the latter also merits a README line)]

actuals:
  tokens: 6300
  tasks: 4
  commits: 8

tech-stack:
  added: []
  patterns:
    - "sys.path.insert(0, str(Path(__file__).resolve().parent.parent)) at the top of every catalog/*.py entrypoint script - `python catalog/bootstrap.py` puts the script's own directory on sys.path[0], not the repo root, so a bare `from catalog import config` fails without this"
    - "create-if-absent, then attempt update, then on InvalidAction specifically compare current vs desired and log drift instead of swallowing the failure (see Deviations)"
    - "MSYS_NO_PATHCONV=1 must be exported before ANY docker compose invocation that passes a POSIX-looking path argument on Git Bash - run.sh does this centrally; a docker compose command typed directly in the terminal, outside run.sh, does NOT get the guard and can path-rewrite and fail"

key-files:
  created:
    - catalog/__init__.py
    - catalog/config.py
    - catalog/schema/temperaturas.json
    - catalog/bootstrap.py
    - catalog/seed.py
    - data/sample/temperaturas_2026-01-15.csv
    - data/sample/temperaturas_2026-01-16.csv
    - data/sample/temperaturas_2026-01-17.csv
    - data/sample/README.md
  modified:
    - .planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-03-PLAN.md (Task 4 step 6 corrected post-verification, see Deviations)

key-decisions:
  - "D-08's update-if-present could not be implemented against Floci (no UpdateDatabase/UpdateTable support, confirmed empirically). Operator-approved resolution: keep calling update_database/update_table (correct against real AWS, keeps Phase 3 Terraform honest); on InvalidAction specifically, compare current vs desired and log a drift warning instead of silently reporting sync. See Deviations."
  - "Schema-edit propagation is verified via `./run.sh down && ./run.sh up` (emulator restart), not a bare `./run.sh bootstrap` re-run - authorized acceptance-criterion revision, safe because FLOCI_STORAGE_MODE=memory already makes every restart a fresh catalog."
  - "Task 4 step 6 (as originally written: run a raw `docker compose ... ls /workspace/...` and expect it to pass) could never pass with any run.sh, because it invoked docker OUTSIDE run.sh where the MSYS_NO_PATHCONV guard is exported. Corrected to two explicit checks: (a) point to step 5's green `./run.sh up` as proof the mount resolves through the normal, guarded path; (b) a deliberate without-guard/with-guard comparison run directly in the terminal as the diagnostic demonstration. This is a plan defect fix, not a deliverable defect - the deliverable (run.sh) was correct throughout."

patterns-established:
  - "Every catalog/*.py script inserts the repo root onto sys.path before importing catalog.config, so it works identically whether run as `python catalog/x.py` (run.sh's invocation) or imported as a module"
  - "ensure_database/ensure_table never delete; on an update the emulator can't perform, they diff current vs desired and log, never raise"

requirements-completed: [ENV-01, CAT-01, CAT-02, CAT-03, CAT-04]

coverage:
  - id: D1
    description: "catalog/schema/temperaturas.json is the single source of truth: 9 required top-level keys, 4 columns, 1 partition key, 3 partitions, parquet storage descriptor; opened read-only at runtime (no write/append mode anywhere in catalog/*.py)"
    requirement: "CAT-03"
    verification:
      - kind: integration
        ref: "python -c schema structure assertions (partitions==3, columns==4, partition_keys==['data_medicao']); grep -cE for write-mode open() returns 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "catalog/config.py derives raw/curated bucket names and database name from PROJECT_NAME via exactly two replace() calls; refuses to build a boto3 client without an explicit AWS_ENDPOINT_URL"
    requirement: "CAT-03"
    verification:
      - kind: integration
        ref: "docker compose --profile tools run --rm tools python -c ... (template-etl -> template-etl-raw/curated/template_etl_db; my_project -> my-project-raw/my_project_db); RuntimeError raised and message contains PROJECT_NAME / AWS_ENDPOINT_URL when unset"
        status: pass
    human_judgment: false
  - id: D3
    description: "./run.sh bootstrap registers the database, table (4 columns in schema order), and exactly 3 partitions against real Floci; a second run exits 0 with no duplicates; CreatePartition is called in a loop (grep for batch_create_partition returns 0, no delete_* calls anywhere)"
    requirement: "CAT-01, CAT-02, CAT-04"
    verification:
      - kind: integration
        ref: "docker compose up -d --wait floci; ./run.sh bootstrap x2; boto3 get_table/get_partitions against http://floci:4566 confirm columns and 3 partition values; grep checks on catalog/bootstrap.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Malformed schema input produces named errors (empty columns, mismatched partition values length) or a defined zero-partition report (empty partitions array), never a crash or silent degenerate catalog object"
    requirement: "CAT-01, CAT-02"
    verification:
      - kind: integration
        ref: "temporarily emptied columns -> exit 1 naming 'columns'; temporarily emptied partitions -> exit 0, '0 partitions registered'; temporarily mismatched partition values -> exit 1 naming the offending entry; schema file restored via git checkout -- afterward, confirmed byte-identical to HEAD"
        status: pass
    human_judgment: false
  - id: D5
    description: "Editing temp_media's type in the schema JSON and restarting the emulator (./run.sh down && ./run.sh up) is reflected in the next get_table; a live re-run of bootstrap without a restart logs a drift warning naming the current vs desired columns instead of silently reporting sync"
    requirement: "CAT-04"
    verification:
      - kind: integration
        ref: "temp_media double->float edit: bare bootstrap re-run logged a WARNING with current=[...double] desired=[...float]; ./run.sh down && ./run.sh up then get_table reported float; edit reverted, schema file restored via git checkout"
        status: pass
    human_judgment: false
  - id: D6
    description: "Three synthetic daily-temperature CSVs (one per registered partition date, six SC cities each) and a README stating plainly the data is synthetic, not INMET, not Epagri"
    requirement: "CAT-01"
    verification:
      - kind: integration
        ref: "python csv.DictReader assertions per file (7 lines, temp_min<temp_max, Lages temp_max below every other city in the same file, data_medicao matches filename); grep for 'synthetic'/INMET/Epagri in README.md"
        status: pass
    human_judgment: false
  - id: D7
    description: "./run.sh seed creates both buckets and uploads the three CSVs to a flat temperaturas/ prefix in the raw bucket, idempotently; ./run.sh up completes green end to end with no AWS credential in the host environment; seed-before-bootstrap and bootstrap-before-seed converge; ./run.sh lint stays green with all four Python files present"
    requirement: "ENV-01, CAT-01"
    verification:
      - kind: integration
        ref: "./run.sh seed x2 (3 keys both times); env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u AWS_PROFILE ./run.sh up exits 0; seed-then-bootstrap and bootstrap-then-seed both produce columns=[cidade,temp_min,temp_max,temp_media], 3 partitions, 3 keys; ./run.sh lint exits 0; docker images grep -c aws-glue-libs returns 0"
        status: pass
    human_judgment: false
  - id: D8
    description: "Manual Windows Git Bash verification of the full loop (ENV-06's empirical evidence) - fresh clone, CRLF/shebang integrity, --help, up, MSYS path-rewrite behavior (guarded vs unguarded), second bootstrap, lint, down, Glue-image-absence"
    requirement: "ENV-06"
    verification:
      - kind: manual_procedural
        ref: "01-03-PLAN.md Task 4, 11-step procedure, executed against a real clone at /c/tmp/template_etl_check (removed after) in Git Bash on Windows - bash 5.3.15(1)-release (x86_64-pc-cygwin), Docker 28.4.0, Docker Compose v2.39.2-desktop.1"
        status: pass
    human_judgment: true
    rationale: "Requires a human confirming CRLF/MSYS behavior on an actual Windows Git Bash install; Linux CI structurally cannot reproduce this (this is exactly why ENV-06's open design question named it a Phase 1 manual step, not a CI check). Executed for real and approved by the operator. Step 6 as originally written could not pass with ANY run.sh implementation - it ran docker outside run.sh, where the MSYS_NO_PATHCONV guard isn't exported - a plan defect, now fixed (see Deviations); the deliverable itself was never at fault."

duration: "~75min (Tasks 1-3: ~70min; Task 4: real-world ./run.sh up measured at 21.6s, full manual procedure additional)"
completed: 2026-08-07
status: complete
---

# Phase 01 Plan 03: Catalog Schema, Idempotent Bootstrap & Seed Summary

**Schema single source of truth (`catalog/schema/temperaturas.json`) consumed directly by `catalog/bootstrap.py`, which registers the Glue database/table/partitions idempotently against Floci — including a discovered-and-resolved gap where Floci implements no `Update*` Glue action at all — plus three synthetic Santa Catarina temperature CSVs seeded into the emulated S3, and a real Windows Git Bash run confirming `run.sh`'s `MSYS_NO_PATHCONV=1` guard actually neutralizes MSYS2 path-rewriting on this machine's Git Bash version.**

## Performance

- **Duration:** ~75 min total (Tasks 1-3 ~70 min; Task 4 manual verification run separately, `./run.sh up` itself measured at 21.6s real time)
- **Tasks:** 4 of 4 — all complete
- **Files modified:** 9 created, 1 plan file corrected post-verification (`01-03-PLAN.md` Task 4 step 6)

## Accomplishments

- `catalog/schema/temperaturas.json` — the single source of truth for the `temperaturas` table (CAT-03): 4 columns, 1 partition key (`data_medicao`), 3 partitions, parquet storage descriptor. No build step, no generated copy.
- `catalog/config.py` — `project_name`, `raw_bucket`, `curated_bucket`, `database_name`, `endpoint_url`, `glue_client`, `s3_client`, `load_schema`. Exactly two `.replace()` calls derive every resource name from `PROJECT_NAME`; every boto3 client raises a named `RuntimeError` rather than falling through to real AWS endpoint resolution.
- `catalog/bootstrap.py` — `validate_schema`, `build_table_input`, `ensure_database`, `ensure_table`, `ensure_partitions`, `main`. Registers the database, table, and three partitions via a `CreatePartition` loop (Floci has no `BatchCreatePartition`). Verified idempotent against real Floci across repeated runs.
- `catalog/seed.py` — `ensure_bucket`, `upload_samples`, `main`. Creates the raw and curated buckets and uploads the three CSVs to a flat `temperaturas/` prefix.
- `data/sample/temperaturas_2026-01-{15,16,17}.csv` and `data/sample/README.md` — synthetic daily temperatures for six Santa Catarina cities, explicitly labelled as invented and not INMET/Epagri data.
- Full loop verified against real Docker/Floci: `./run.sh up` green end to end, including with every AWS credential env var unset on the host; `./run.sh bootstrap`/`seed` both idempotent; order-independence (seed-before-bootstrap == bootstrap-before-seed); `./run.sh lint` green; `docker images | grep aws-glue-libs` returns 0 throughout.
- **Task 4 (ENV-06 manual verification) executed for real on this Windows machine, in Git Bash, against a fresh clone — 10 of 11 steps green as written; the 11th step's procedure (not the deliverable) had a defect, corrected in the plan. See below.**

## Task Commits

1. **Task 1: The schema single source of truth and the configuration seam** - `09e32be` (feat)
2. **Task 2: Idempotent Data Catalog bootstrap** - `9bca102` (feat) — includes the operator-approved Rule 4 deviation, see below
3. **Task 3: Synthetic sample data and the seed step** - `8baee42` (feat)
4. **Task 4: Manual Windows Git Bash verification of the full loop (ENV-06)** — checkpoint task, no code commit; executed by the human operator directly against a real clone (see below). Plan-file correction to Task 4 step 6 and this SUMMARY update are committed as part of plan completion.

**Plan metadata:** plan-complete commit follows this SUMMARY update (see repository log for hash).

## Files Created/Modified

- `catalog/__init__.py` - makes `catalog/` an explicit importable package
- `catalog/config.py` - configuration seam: resource-name derivation, endpoint-bound boto3 clients, schema loader
- `catalog/schema/temperaturas.json` - the neutral schema shape Terraform will also consume in Phase 3
- `catalog/bootstrap.py` - idempotent Data Catalog registration
- `catalog/seed.py` - bucket creation and sample CSV upload
- `data/sample/temperaturas_2026-01-15.csv`, `temperaturas_2026-01-16.csv`, `temperaturas_2026-01-17.csv` - synthetic daily temperatures, six cities each
- `data/sample/README.md` - synthetic-data disclaimer
- `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-03-PLAN.md` - Task 4 step 6 corrected after the real verification run exposed a procedural defect in how it was written (see Deviations)

## Decisions Made

- Kept `update_database`/`update_table` in the call path even though Floci cannot execute them, because they are correct against real AWS Glue and Phase 3's Terraform depends on that behavior staying honest in the reference implementation. This was an explicit operator decision at the Task 2 checkpoint (see Deviations).
- Compared current-vs-desired columns (name + type, in order) rather than building a generic structural diff, per operator instruction to keep template code "enxuto e legível."
- Task 4 step 6 rewritten to test two things separately (mount resolution through the normal `run.sh` path, and the guard's effect demonstrated directly) rather than one command that could never pass as originally phrased.

## Task 4: Manual Windows Git Bash Verification (ENV-06) — COMPLETE

Executed for real, in Git Bash on Windows, against a fresh clone at `/c/tmp/template_etl_check` (removed after the session). Not simulated.

**Resume-signal versions (as required by the plan):**
- `bash`: GNU bash, version 5.3.15(1)-release (x86_64-pc-cygwin)
- `docker`: Docker version 28.4.0, build d8eb465
- `docker compose`: Docker Compose version v2.39.2-desktop.1

**Per-step results:**

| Step | What | Result |
|------|------|--------|
| 1 | Fresh clone into an unused directory | OK |
| 2 | `file run.sh` (no CRLF) / shebang byte check / execute bit | OK — `file run.sh` reported "Bourne-Again shell script, Unicode text, UTF-8 text executable" (no "CRLF"); `head -c 20 run.sh \| od -c` → `#!/usr/bin/env bash\n` with no `\r`; `grep -c $'\r' run.sh` → 0; execute bit preserved |
| 3 | `cp .env.example .env` | OK |
| 4 | `./run.sh --help` | OK — eight subcommands in fixed order, readable descriptions, no mojibake, exit 0 |
| 5 | `./run.sh up` | OK — green in **21.6s real time**: `[ok] start emulator` / `[ok] bootstrap catalog` / `[ok] seed sample data` |
| 6 | MSYS path-rewrite check (guarded vs unguarded) | **Failed as originally written — plan defect, not a deliverable defect. See below.** |
| 7 | `./run.sh bootstrap` a second time | OK — `[ok] bootstrap catalog`, exit 0, no duplicate |
| 8 | `./run.sh lint` | OK — `[ok] ruff check` / `[ok] ruff format --check`, exit 0 |
| 9 | `./run.sh down` | OK — exit 0; `docker compose ps` → 0 services |
| 10 | `docker images \| grep aws-glue-libs` | OK — no output; the Glue image was never pulled in the entire phase |
| 11 | Record versions | OK — recorded above |

**Step 6 — the actual finding of this phase, and why it matters.**

The plan's Task 4 originally instructed running `docker compose --profile tools run --rm tools ls /workspace/catalog/schema` directly in the terminal and expecting it to list `temperaturas.json`. Run exactly as written, it failed:

```
ls: cannot access 'C:/Program Files/Git/workspace/catalog/schema': No such file or directory
(exit 2)
```

**This is MSYS2 path-rewriting, reproduced for real on this machine's Git Bash — not a theoretical risk.** But the command was run *outside* `run.sh`, which is precisely where `MSYS_NO_PATHCONV=1` is exported (per-platform, in `run.sh`'s `case "${OSTYPE:-}"` guard). Running the identical command with the guard applied explicitly:

```
MSYS_NO_PATHCONV=1 docker compose --profile tools run --rm tools ls /workspace/catalog/schema
→ temperaturas.json   (exit 0)
```

**Conclusion: the deliverable (`run.sh`) is correct and the guard is sufficient on this Git Bash version.** What was defective was step 6 of the *procedure* — as originally phrased, no `run.sh`, however correct, could ever make that specific raw command pass, because the guard it was meant to demonstrate is scoped to `run.sh`'s own invocations, not to a bare `docker compose` typed by a human. **Approval was granted on the deliverable; the plan needed the fix.**

**Fix applied to `01-03-PLAN.md` Task 4 step 6:** split into two explicit, separately-labelled checks — (a) point to step 5's already-green `./run.sh up` as the evidence that the mount resolves correctly through the normal, guarded path (no new command needed — a green `up` already proves it, since `bootstrap.py`/`seed.py` could only have read their files through that same mount); (b) the without-guard/with-guard pair above, run deliberately outside `run.sh`, kept in the procedure as the diagnostic demonstration of *why* the guard is needed — not as a compliance check on `run.sh` itself.

## Flagged Assumption Update — `MSYS_NO_PATHCONV` Efficacy

REQUIREMENTS.md's Open Design Questions table and the 01-CONTEXT.md carried this forward as `verification: backstop` — impossible to prove in Linux CI. **This plan supplies the first positive empirical evidence**, not a general resolution:

- **Confirmed:** `MSYS_NO_PATHCONV=1` neutralizes MSYS2's path-rewriting for `docker compose ... run --rm tools <posix-path-arg>`, specifically on **`bash 5.3.15(1)-release (x86_64-pc-cygwin)`**, paired with Docker 28.4.0 / Docker Compose v2.39.2-desktop.1, on this machine.
- **NOT confirmed, and explicitly out of scope of this evidence:** any other Git Bash / MSYS2 version. The Open Design Question's underlying risk — behavior drift across Git Bash releases — remains real and untested beyond this one version. Do not read this plan's result as "MSYS_NO_PATHCONV is proven sufficient in general." It is proven sufficient *on the version tested*.

## Phase 4 Harvest Items (do not let these die in this SUMMARY)

Two items, both empirically discovered during this plan's execution against real infrastructure, both **must** land in `docs/KNOWN_DIFFERENCES.md` when Phase 4 writes it:

1. **Floci implements no Glue `Update*` action** (`UpdateDatabase`, `UpdateTable` both return `InvalidAction`). Locally, a schema edit requires an emulator restart (`./run.sh down && ./run.sh up`) to take effect; against real AWS Glue this limitation does not exist. Full detail in the Deviations section below and in `catalog/bootstrap.py`'s module docstring "KNOWN DIFFERENCE" block.
2. **Any `docker compose` invocation with an absolute/POSIX-looking container-side path argument, run OUTSIDE `run.sh`, breaks on Git Bash** — MSYS2 rewrites the path before Docker sees it (reproduced directly above: `ls: cannot access 'C:/Program Files/Git/workspace/...'`). `run.sh` itself is unaffected because it exports `MSYS_NO_PATHCONV=1` before every invocation it makes. **This one additionally merits a line in the README** (not just `KNOWN_DIFFERENCES.md`) — it is exactly what an adopter debugging their own ad hoc `docker compose` command on Windows will hit first, and without a pointer to the guard, the natural conclusion is "the template is broken" rather than "I ran this outside run.sh."

## Deviations from Plan

### Auto-fixed Issues (Rules 1-3, no permission needed)

**1. [Rule 3 - Blocking] `sys.path` insertion needed in every `catalog/*.py` entrypoint**
- **Found during:** Task 2, first `./run.sh bootstrap` run.
- **Issue:** `python catalog/bootstrap.py` (the exact invocation `run.sh` uses) puts the script's own directory on `sys.path[0]`, not the repository root, so `from catalog import config` raised `ModuleNotFoundError`.
- **Fix:** Added `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` before the `catalog` import in both `bootstrap.py` and `seed.py`.
- **Files modified:** `catalog/bootstrap.py`, `catalog/seed.py`.
- **Verification:** `./run.sh bootstrap` and `./run.sh seed` both run cleanly via the fixed `run.sh` invocation.
- **Committed in:** `9bca102` (Task 2), `8baee42` (Task 3).

**2. [Rule 3 - Blocking] ruff PTH rules (flake8-use-pathlib) on `os.path.*`/`open()`**
- **Found during:** Task 2, `./run.sh lint`.
- **Issue:** `pyproject.toml`'s `select` list includes `PTH`; `os.path.dirname`/`os.path.abspath` in `bootstrap.py`'s sys.path fix and `open()` in `config.py`'s `load_schema` both flagged.
- **Fix:** Switched to `pathlib.Path` throughout (`Path(__file__).resolve().parent.parent`, `Path(path).open(...)`).
- **Files modified:** `catalog/bootstrap.py`, `catalog/config.py`.
- **Verification:** `./run.sh lint` exits 0.
- **Committed in:** `9bca102` (Task 2).

**3. [Rule 3 - Blocking] Literal string `CreateBucketConfiguration` in a docstring failed the acceptance-criteria grep**
- **Found during:** Task 3, running the plan's own acceptance-criteria checks.
- **Issue:** `grep -c 'CreateBucketConfiguration' catalog/seed.py` must return 0; my explanatory docstring for `ensure_bucket` spelled out the literal API name it deliberately avoids passing, which the grep can't distinguish from actual usage.
- **Fix:** Reworded the docstring to describe the constraint without naming the literal parameter.
- **Files modified:** `catalog/seed.py`.
- **Verification:** grep returns 0; `./run.sh lint` still green.
- **Committed in:** `8baee42` (Task 3).

**4. [Rule 1 - Bug, in the plan text itself] Task 4 step 6 could never pass as written**
- **Found during:** Task 4, the human operator's real execution of the plan's procedure.
- **Issue:** Step 6 instructed running `docker compose --profile tools run --rm tools ls /workspace/catalog/schema` directly in the terminal and expecting success. On this Git Bash, MSYS2 genuinely rewrites the POSIX-looking path argument before Docker sees it, and the command fails — correctly, because it was run outside `run.sh`, where the `MSYS_NO_PATHCONV=1` guard is exported. No `run.sh` implementation, however correct, could make that specific raw invocation pass; the procedure was testing the wrong thing.
- **Fix:** Rewrote step 6 into two explicit, separately-explained checks: (a) cite step 5's green `./run.sh up` as proof the mount resolves through the normal, guarded path; (b) keep the without-guard/with-guard pair as a deliberate diagnostic run outside `run.sh`, with both expected outcomes spelled out (fails without the guard, succeeds with it).
- **Files modified:** `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-03-PLAN.md`.
- **Verification:** the corrected two-part check was demonstrated live during the same session — see "Task 4" section above for both command outputs.
- **Committed in:** the plan-complete commit for this SUMMARY update.

### Architectural Deviation (Rule 4 — operator-approved via checkpoint, NOT auto-applied)

**5. [Rule 4 - Architectural] Floci implements no Glue `Update*` action at all**

- **Found during:** Task 2, verifying `./run.sh bootstrap` idempotency (a mandatory acceptance criterion) by running it twice against real Floci.
- **Issue:** The plan's D-08 idempotency model is create-if-absent, **update-if-present**. The second `bootstrap` run raised `botocore.errorfactory.AlreadyExistsException` on `create_database` (expected) and then `ClientError: InvalidAction — Action UpdateDatabase is not supported` on the follow-up `update_database` call. Confirmed identically for `update_table`. This matches PROJECT.md's own documented Floci Glue operation list, which lists no `Update*` verb for either database or table. The plan's `flagged_assumptions` only flagged `AlreadyExistsException` error-code fidelity, not the wholesale absence of update support — this was a genuine, previously-unverified gap. Catalog state was not corrupted by the failed call.
- **Why I stopped instead of picking a fix:** the plan's own critical guard on CAT-03/CAT-04 ("if the plan is genuinely ambiguous... stop and raise a checkpoint rather than picking a shape yourself") applied directly — no resolution could satisfy all three of the plan's explicit constraints simultaneously (idempotent second run; schema edit visible via a `bootstrap` re-run; zero `delete_*` calls in the file, which D-08 forbids for production-safety reasons independent of Floci).
- **Operator-approved resolution:**
  1. `ensure_database`/`ensure_table` still call `create_*` first, catch `AlreadyExistsException`, then still call `update_*` — the update call remains in the code because it is correct against real AWS Glue, keeping the Phase 3 Terraform path honest.
  2. The `update_*` call's `ClientError` is caught, but only `InvalidAction` is treated specially; any other error code (bad credential, wrong endpoint, etc.) is re-raised, never swallowed generically.
  3. On `InvalidAction`, `get_database`/`get_table` is called and compared against the desired definition (database: description equality; table: column name+type list, in order) — **not** a generic structural diff, per operator instruction to keep the comparison "enxuto e legível." If they match, `logger.info(...)` "already current"; if they differ, `logger.warning(...)` naming both the current and desired values and the literal remedy `./run.sh down && ./run.sh up`.
  4. Zero `delete_table`/`delete_database`/`delete_partition` calls anywhere in the file — unchanged, verified by grep.
- **Acceptance-criterion revision (operator-authorized):** "editing `temp_media`'s type and re-running `./run.sh bootstrap`" is now verified via `./run.sh down && ./run.sh up` (an emulator restart) rather than a bare `bootstrap` re-run — cheap and honest because `FLOCI_STORAGE_MODE=memory` already makes every restart a fresh catalog.
- **Files modified:** `catalog/bootstrap.py` (`ensure_database`, `ensure_table`, module docstring "KNOWN DIFFERENCE" section).
- **Verification (all against real Floci, not simulated):** fresh catalog → `bootstrap` (created) → `bootstrap` again (both `[ok]`, database/table logged "already current", partitions still 3, no duplicates) → live schema edit (`temp_media` double→float) → bare `bootstrap` re-run (still exits 0, logs a `WARNING` naming `current=[...double]` vs `desired=[...float]`, does NOT silently claim sync) → `./run.sh down && ./run.sh up` → `get_table` confirms `float` → edit reverted, schema file restored via `git checkout --` and confirmed byte-identical to `HEAD`.
- **Committed in:** `9bca102` (Task 2).

### Assunção sinalizada — DOCUMENTAÇÃO OBRIGATÓRIA PARA A FASE 4 (pt-BR, conforme solicitado)

**D-08 pressupunha `UpdateDatabase`/`UpdateTable` do Glue; o Floci não suporta nenhuma das duas.** Localmente, edições de schema exigem restart do emulador (`./run.sh down && ./run.sh up`) para valer; contra o AWS Glue real a limitação não existe — `update_database`/`update_table` permanecem no código exatamente porque são o caminho correto lá. **Isto precisa entrar em `docs/KNOWN_DIFFERENCES.md` na Fase 4** — se ficar apenas registrado aqui, no SUMMARY de uma fase já encerrada, a informação morre e um adopter reproduzindo o template localmente é surpreendido por um `WARNING` de drift sem saber por quê. O módulo `catalog/bootstrap.py` traz a mesma explicação em um bloco `KNOWN DIFFERENCE` no docstring de topo, para quem for escrever a Fase 4 encontrar direto na fonte.

**Segundo item para a Fase 4 (achado da Task 4, verificação manual real):** qualquer `docker compose` com path absoluto de container executado FORA do `run.sh` quebra em Git Bash — o MSYS2 reescreve o argumento de path antes do Docker recebê-lo (reproduzido de fato: `ls: cannot access 'C:/Program Files/Git/workspace/...'`). Isto também precisa entrar em `docs/KNOWN_DIFFERENCES.md` **e merece uma linha no README** — é exatamente o primeiro tropeço de um adotante depurando um `docker compose` ad hoc no Windows, e sem essa explicação a conclusão natural é "o template está quebrado" em vez de "eu rodei isso fora do run.sh."

---

**Total deviations:** 4 auto-fixed (Rule 3 - blocking, includes the plan-text fix in Task 4) + 1 architectural (Rule 4 - operator-approved via checkpoint)
**Impact on plan:** The Rule 4 deviation changes *how* CAT-04's idempotency and schema-edit-propagation acceptance criteria are satisfied (drift-warning + restart-to-apply, instead of a silent in-place update Floci cannot actually perform), but changes nothing about `catalog/schema/temperaturas.json`'s shape or its Phase 3 Terraform contract, and does not weaken any safety property (still zero deletes, still explicit endpoint isolation, still create-first). The Task 4 procedure fix changes only the verification text, not any deliverable. No scope creep in either case.

## Issues Encountered

- Docker Desktop was already running at session start; no environment setup blocker.
- CSV/JSON file edits made for edge-case testing (empty `columns`, empty `partitions`, mismatched partition `values`, `temp_media` type change) were all reverted via `git checkout -- <file>` immediately after each test and confirmed byte-identical to the committed version before moving on — no stray working-tree changes carried into commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four tasks complete. `catalog/schema/temperaturas.json`, `catalog/config.py`, `catalog/bootstrap.py`, `catalog/seed.py`, and the synthetic sample data are all in place, committed, and verified against real Floci and real Windows Git Bash.
- **ENV-06 note:** already marked `[x]` Complete in `REQUIREMENTS.md` from Plan 01-02's execution (that plan built and verified `run.sh` itself end-to-end on Windows). This plan's Task 4 supplies the specific empirical evidence the Open Design Question demanded (MSYS path-rewrite behavior under a real container mount) — not re-marked here since `ENV-06` is not part of `01-03`'s own `requirements:` frontmatter field, and it was already checked. See "Flagged Assumption Update" above for the precise scope of that evidence.
- Two items now owed to Phase 4's `docs/KNOWN_DIFFERENCES.md` (and one of them to the README too) — see "Phase 4 Harvest Items" above. Do not let either die in this SUMMARY.
- Phase 3's Terraform must reproduce `catalog/config.py`'s exact two `.replace()` calls and must consume `catalog/schema/temperaturas.json` directly (`jsondecode(file(...))`), per CAT-03/D-01/D-02.
- No blockers for Phase 2.

---
*Phase: 01-local-environment-entrypoint-catalog-bootstrap*
*Status: Complete — all 4 tasks, including Task 4 human-verify checkpoint*
