# Phase 1: Local Environment, Entrypoint & Catalog Bootstrap - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the ground a `.sh` file can safely stand on, plus a populated emulated Data Catalog. A developer who has never seen the repo clones it, runs one subcommand, and ends up with a healthy Floci emulator, a Glue database and table registered, three partitions, and sample data in the emulated S3 — with no AWS credentials anywhere on their machine.

**In scope:** repo scaffolding, `.gitattributes`, `.gitignore`, `docker-compose.yml`, `.env.example`, `run.sh` subcommand surface, the schema single-source-of-truth file, `catalog/bootstrap.py`, sample CSV data and the `seed` step.

**Out of scope (later phases):** the PySpark job and any Spark configuration (Phase 2), transformation logic and tests (Phase 2), Terraform (Phase 3), CI (Phase 3), README and public docs (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Schema single source of truth (CAT-03)

- **D-01:** Schema lives in `catalog/schema/*.json`, consumed directly by both sides with no build step and no generated file. Python reads it with `json.load`; Terraform reads it with `jsondecode(file(...))` and iterates with `dynamic` blocks over `columns` and `partition_keys`. — **Reversibility:** costly — undoing this after Phase 3 means rewriting the Terraform catalog resources and the bootstrap script together, and any adopter who already forked the template inherits the old shape.
- **D-02:** The JSON uses a **neutral, minimal shape** — not the Glue API `TableInput` shape. Each side maps from the neutral form to its own API. Rationale: the file is meant to be read and edited by an adopter, and `TableInput` is verbose with fields that carry no meaning for someone adapting a template.
- **D-03:** The schema file defines **everything about the catalog object**: table name, columns with types, partition keys, SerDe, input/output format, and relative location. Nothing about the table is defined outside this file — that is the only way the single source is actually single.
- **D-04:** **Two consumers only.** The Spark job (Phase 2) declares its own schema and does NOT read this file. Rationale: `transforms/` must stay pure and free of file I/O to remain testable without Glue or AWS (TEST-01). The Glue-type → Spark-type correspondence becomes a documented mapping in Phase 4, not a code coupling. — **Reversibility:** reversible — adding a third consumer later is additive.

### Where the bootstrap executes

- **D-05:** `catalog/bootstrap.py` runs in a dedicated **`tools` service on `python:3.11-slim`** with boto3 — NOT in the Glue container. Rationale: the bootstrap makes boto3 API calls and never touches Spark; running it on the Glue image would force every adopter to pull ~4.77 GB before their first API call, which attacks the project's core value directly. **This supersedes ROADMAP.md Phase 1 success criterion 2**, which assumed an ephemeral Glue container.
- **D-06:** Tooling dependencies (boto3, ruff, pytest) are managed by a **pinned `requirements.txt` installed with pip**, not uv. Rationale: research recommended uv, but the user chose pip — zero new tooling for an adopter to learn, and it works identically everywhere. The dependency install lives inside the container, so the adopter never runs pip themselves.
- **D-07:** The Glue image is pulled **only on the first `./run.sh job`** (Phase 2), and that subcommand prints a warning before the pull ("first run downloads ~4.8 GB"). Phase 1 never touches it. There is no `pull`/`warm` subcommand.
- **D-08:** "Idempotent bootstrap" (CAT-04) means **create-if-absent, update-if-present**: catch `AlreadyExistsException` and call `update_table`. Re-running after editing `schema.json` applies the change. Partitions are left in place. Explicitly NOT delete-and-recreate — that would be destructive if ever pointed at real AWS.

### `run.sh` ergonomics

- **D-09:** `./run.sh up` performs compose up **plus `bootstrap` plus `seed`**, leaving a fully usable environment. `bootstrap` and `seed` remain separately callable for re-applying a schema change or re-seeding data. Rationale: the user wanted a clean conceptual boundary between metadata and data as *commands*, but `up` leaving a catalog that points at empty paths is not a useful state.
- **D-10:** A **`demo`** subcommand is added: `up` → `job` → `test` → summary report. This is the single command the README leads with and the one that satisfies RUN-04 in Phase 2. — **Reversibility:** reversible.
- **D-11:** Subcommand surface is now **eight**: `up`, `down`, `bootstrap`, `seed`, `job`, `test`, `lint`, `demo`. **This supersedes RUN-02 (which listed six) and ROADMAP.md Phase 1 success criterion 3 (which says "all six subcommands").** Both must be corrected.
- **D-12:** Output style is **lean steps with full detail on failure** — one line per step with a status marker; raw docker/pytest output suppressed on the happy path and dumped in full when a step fails. No `--verbose` flag (avoids argument-parsing complexity in plain shell).
- **D-13:** Preflight checks run before anything else: Docker running, `docker compose` available, `.env` present. On failure, print the exact remedial command (e.g. `cp .env.example .env`). The script does **not** auto-create `.env` — the adopter should learn that the file exists, because that is where they will make their changes.

### Sample data and naming

- **D-14:** The example dataset is **daily temperatures for Santa Catarina cities** (user's choice). Input CSV columns: `cidade` (string), `data_medicao` (partition key), `temp_min` (double), `temp_max` (double). The Phase 2 job derives `temp_media` on write. Rationale for keeping min/max rather than a single temperature column: it gives `transforms/` a real, assertable computation so TEST-01 is a genuine test rather than a passthrough check. Cities: Florianópolis, Joinville, Blumenau, Chapecó, Lages, Criciúma.
- **D-15:** **The sample data is synthetic and must be labelled as such** — in `data/sample/` (a README or header comment) and in the project README. It is not INMET, Epagri, or any real meteorological record. This repository will be public; unlabelled invented measurements will eventually be cited as real by someone.
- **D-16:** Resource names **derive from a single `PROJECT_NAME` variable** in `.env`: `${PROJECT_NAME}-raw`, `${PROJECT_NAME}-curated`, `${PROJECT_NAME}_db`. An adopter changes one variable and the whole rename follows — this turns the DOC-05 rename checklist (Phase 4) into a single line. No per-resource overrides. — **Reversibility:** costly — adding per-resource overrides later means fallback logic in compose, `run.sh`, and Terraform simultaneously.
- **D-17:** The example registers **three partitions** (three dates). Enough for the `CreatePartition` loop to actually be a loop and for a test to assert per-partition counts, without inflating repo size or run time. The loop matters precisely because Floci lacks `BatchCreatePartition`.
- **D-18:** Sample CSVs are **committed to `data/sample/`** and uploaded to the emulated S3 by the `seed` subcommand — not generated at runtime. Rationale: keeps the input inspectable for someone learning the template.

### Claude's Discretion

- Exact `.env.example` variable names beyond `PROJECT_NAME`, and the internal structure of the neutral schema JSON (key names, nesting).
- Compose network naming, service naming beyond `floci` and `tools`, and whether `tools` uses a Dockerfile or an inline `image` + `command`.
- The specific synthetic temperature values, as long as they are plausible for each city (coastal cities milder, Lages and the serra colder) and clearly labelled synthetic.
- Log line formatting and status markers in `run.sh`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level scope and constraints
- `.planning/PROJECT.md` — locked decisions (Glue 5.0, Floci, `run.sh`, Terraform), constraints, and the Out of Scope list that bounds this phase
- `.planning/REQUIREMENTS.md` — ENV-01…07, RUN-01/02/03, CAT-01…04 are this phase's requirements; note RUN-02 is superseded by D-11 above
- `.planning/ROADMAP.md` §"Phase 1" — goal, success criteria, and the non-negotiable ordering constraints; criteria 2 and 3 are superseded by D-05 and D-11
- `.planning/ROADMAP.md` §"Scope Guardrail" — the rule that any growth of the sample beyond the minimum must cite a requirement ID

### Technical research (read before planning implementation details)
- `.planning/research/STACK.md` — exact image references, pinned versions, Floci init-script paths, readiness endpoint, and the explicit note that `DISABLE_SSL` and `AWS_REGION` are NOT real env vars for these containers
- `.planning/research/ARCHITECTURE.md` — container topology, compose service shape, config flow from `.env` through to the container, and the proposed directory tree
- `.planning/research/PITFALLS.md` — CRLF/`.gitattributes` ordering, `MSYS_NO_PATHCONV` path mangling, credential-provider traps, and the phase mapping for each
- `.planning/research/SUMMARY.md` — consolidated findings with confidence levels and the carried-forward UNKNOWNs

### External documentation
- Floci Glue service coverage: https://floci.io/floci/services/glue/ — the authoritative list of supported Catalog operations; confirms `BatchCreatePartition` is absent
- Floci service overview: https://floci.io/aws/

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
None — greenfield repository. The only tracked files are `.planning/` documents and `.claude/CLAUDE.md`.

### Established Patterns
None yet. This phase **establishes** the patterns every later phase follows: `.env`-only configuration, endpoint isolation so the emulator is swappable, and the `run.sh` subcommand shape.

### Integration Points
- The schema JSON written here is consumed by Terraform in Phase 3 (D-01). Its shape is binding on that phase.
- The `run.sh` subcommand surface established here is invoked by CI in Phase 3 (CI-02) and documented in Phase 4 (DOC-01). Renaming a subcommand later breaks both.
- The `job` and `test` subcommands are wired in this phase but only exercised in Phase 2.

### Repository hygiene note
`.planning/research/.cache/*.json` (8 files) was committed with the research artifacts. This repository will be public; the fetch cache is noise. Add `.planning/research/.cache/` to `.gitignore` in this phase and remove the tracked files.

</code_context>

<specifics>
## Specific Ideas

- The dataset was specifically requested by the user: **daily temperatures for Santa Catarina cities**. Keep it recognisably Brazilian and recognisably synthetic.
- `demo` was chosen over `all` as the subcommand name because "demo" communicates that what it runs is a disposable demonstration — which is exactly what a template's example pipeline is.
- The preference for lean output with detail-on-failure came with the reasoning that an adopter's first contact should not be a wall of log.

</specifics>

<deferred>
## Deferred Ideas

- **Per-resource name overrides** (explicit `RAW_BUCKET`, `CURATED_BUCKET` alongside `PROJECT_NAME`) — considered and rejected for v1 in favour of single-variable derivation (D-16). Revisit only if an adopter needs to point at pre-existing resources with non-conforming names.
- **`pull` / `warm` subcommand** to pre-fetch images — rejected in favour of a warning on first `job` (D-07). Reconsider if CI or adopter feedback shows the surprise pull is a real problem.
- **Schema JSON driving the Spark read schema** (third consumer) — rejected for v1 (D-04) to keep `transforms/` pure. Revisit if type drift between catalog and job turns out to bite in practice.
- **`uv` for dependency management** — research recommended it; user chose pinned `requirements.txt` + pip (D-06). Revisit only if install time becomes a CI bottleneck in Phase 3.
- **Richer dataset columns** (precipitation, region) — flagged during discussion as exactly the growth the Scope Guardrail prohibits. v2 if ever.

</deferred>

---

*Phase: 1-Local Environment, Entrypoint & Catalog Bootstrap*
*Context gathered: 2026-08-06*
