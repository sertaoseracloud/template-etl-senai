# Phase 1: Local Environment, Entrypoint & Catalog Bootstrap - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 1-Local Environment, Entrypoint & Catalog Bootstrap
**Areas discussed:** Schema single source of truth, Where the bootstrap executes, `run.sh` ergonomics, Naming and sample dataset

---

## Schema single source of truth (CAT-03)

### Mechanism linking the single source to Terraform

| Option | Description | Selected |
|--------|-------------|----------|
| JSON + `jsondecode` + `dynamic` | Read natively by both sides, no build step, no generated file; cost is verbosity in dynamic blocks | ✓ |
| Codegen to `.tf.json` | Terraform reads `.tf.json` as first-class config; cost is a generation step and the risk of editing the generated file | |
| Duplicate + drift test | Each side defines its own, a test fails on divergence; the test becomes the mechanism | |
| Python (pydantic) module as source | Typed schema emitting JSON; puts Python in authority over infrastructure | |

### Schema file format

| Option | Description | Selected |
|--------|-------------|----------|
| Neutral and minimal | Generic form both sides map from; readable and adaptable | ✓ |
| Glue API `TableInput` shape | Python becomes passthrough; verbose and full of fields meaningless to an adopter | |

### What the schema file defines

| Option | Description | Selected |
|--------|-------------|----------|
| Everything catalog-related | Columns, partition keys, SerDe, formats, relative location | ✓ |
| Columns and partitions only | Rest hardcoded on both sides since it is always Parquet | |

### Should the schema also feed Spark in Phase 2?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, three consumers | Job derives its `StructType` from the same file | |
| No, stop at two | Spark declares its own schema; keeps `transforms/` pure and testable without AWS | ✓ |
| Decide in Phase 2 | Leave open until the job exists | |

**Notes:** The two-consumer choice is what keeps TEST-01 achievable — `transforms/` doing file I/O to read a schema would undermine the pure-module split that makes it testable outside any container.

---

## Where the bootstrap executes

### Container running `catalog/bootstrap.py`

| Option | Description | Selected |
|--------|-------------|----------|
| `python:3.11-slim` + boto3 | Dedicated ~50 MB `tools` service; bootstrap never touches Spark | ✓ |
| Ephemeral Glue container | What the roadmap assumed; guarantees identical Python but costs a 4.77 GB pull | |
| `floci/floci:latest-compat` | Ships AWS CLI/boto3; no extra image but couples tooling to the emulator image | |
| Directly on the host | Fastest, but breaks "clone and one command" | |

**Notes:** Raised by Claude as a probable premise error in the roadmap — the bootstrap is pure boto3 and has no technical reason to load the Glue image. This supersedes ROADMAP.md Phase 1 criterion 2, which was corrected.

### Tooling dependency management

| Option | Description | Selected |
|--------|-------------|----------|
| Pinned `requirements.txt` + pip | Zero new tooling for an adopter; works everywhere | ✓ |
| `uv` with lockfile | Research's 2026 recommendation; faster with a real reproducible lock | |
| Split runtime vs dev | Conceptually more correct, more files to maintain | |

**Notes:** User chose pip over research's uv recommendation. Simplicity for adopters won over speed.

### When the 4.77 GB Glue image is pulled

| Option | Description | Selected |
|--------|-------------|----------|
| Only on first `job`, with a warning | Phase 1 stays light; adopter is told before it happens | ✓ |
| Explicit `pull` subcommand | Gives control, adds surface area | |
| On `up`, all at once | No later surprise, but the first command becomes a multi-minute wait | |

### Meaning of "idempotent bootstrap" (CAT-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Create if absent, update if present | Re-running applies schema edits; partitions preserved | ✓ |
| Skip if exists | Simpler and safer, but editing `schema.json` silently has no effect | |
| Delete and recreate | Deterministic clean state, but destroys partitions and would be catastrophic against real AWS | |

---

## `run.sh` ergonomics

### Does `up` populate the catalog?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, `up` includes bootstrap | One command yields a usable environment | ✓ |
| No, separate steps | Cleaner conceptual boundary, but nothing works until a second step | |

### A single zero-to-green subcommand (needed by RUN-04 in Phase 2)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add `demo` | `up` + `job` + `test` + report; the command the README leads with | ✓ |
| Yes, but call it `all` | More conservative name, less evocative of a disposable demonstration | |
| No, chain with `&&` | Keeps six subcommands, but "one command" becomes three with glue | |

**Notes:** `demo` was preferred because it signals the pipeline is a disposable demonstration — accurate for a template. This raised the subcommand count and required correcting RUN-02 and ROADMAP.md criterion 3.

### Output style

| Option | Description | Selected |
|--------|-------------|----------|
| Lean steps + detail on failure | One line per step; raw output suppressed on success, dumped on failure | ✓ |
| Raw output, no decoration | Nothing hidden, but the first contact is a wall of log | |
| Lean with `--verbose` | More control, more argument parsing in plain shell | |

### Behaviour when a prerequisite is missing

| Option | Description | Selected |
|--------|-------------|----------|
| Preflight check with actionable message | Verifies Docker, compose, `.env`; prints the exact fix | ✓ |
| Auto-create `.env` | Removes friction but hides the file the adopter needs to edit | |
| Let it fail naturally | Less code, but native error messages are bad enough to generate issues | |

---

## Naming and sample dataset

### Sample dataset

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic events | Generic placeholder with a free partition column | |
| Orders / sales | Familiar, but carries enough domain to invite extension | |
| Public dataset sample | Realistic, but adds weight, licensing, and scope-creep temptation | |
| **Free text:** Santa Catarina daily city temperatures | User's own choice | ✓ |

**Notes:** User supplied this rather than picking a listed option. Claude observed that `temp_min`/`temp_max` in the input lets the job *compute* `temp_media`, giving `transforms/` real assertable logic instead of a passthrough — which makes TEST-01 a genuine test. Claude also flagged that the data will be synthetic and must be labelled as such in a public repository, since unlabelled invented measurements eventually get cited as real.

### Resource naming

| Option | Description | Selected |
|--------|-------------|----------|
| Derived from a single `PROJECT_NAME` | One variable changes everything; collapses the DOC-05 rename checklist to one line | ✓ |
| Each name explicit in `.env` | More readable, but several edit points and several chances to miss one | |
| Hybrid with per-resource override | Covers both cases at the cost of fallback logic in three places | |

### Number of partitions

| Option | Description | Selected |
|--------|-------------|----------|
| Three dates | Enough for the `CreatePartition` loop to be a real loop | ✓ |
| One | A one-iteration loop does not prove the loop works | |
| Twelve | Convincing but slower and heavier for little gain | |

### How sample data reaches the emulated S3

| Option | Description | Selected |
|--------|-------------|----------|
| Bootstrap uploads the CSVs | Guarantees every registered partition points at a real path | |
| Separate `seed` subcommand | Cleaner metadata/data boundary; opens a window where the catalog points at nothing | ✓ |
| Generate at runtime | Cleaner repo, but adds generation code and makes input less inspectable | |

**Follow-up:** Because `seed` is separate but `up` includes `bootstrap`, Claude asked whether `up` should also run `seed`. User chose **yes** — `up` = compose + bootstrap + seed — preserving the command-level boundary while ensuring `up` leaves a usable state rather than a catalog pointing at empty paths.

---

## Claude's Discretion

- `.env.example` variable names beyond `PROJECT_NAME`, and the internal key structure of the neutral schema JSON
- Compose network and service naming beyond `floci` and `tools`; whether `tools` uses a Dockerfile or inline `image` + `command`
- Specific synthetic temperature values (must be plausible per city and clearly labelled synthetic)
- Log line formatting and status markers in `run.sh`

## Deferred Ideas

- Per-resource name overrides alongside `PROJECT_NAME` — rejected for v1
- `pull` / `warm` subcommand — rejected in favour of a warning on first `job`
- Schema JSON driving the Spark read schema (third consumer) — rejected to keep `transforms/` pure
- `uv` for dependency management — research recommended it; user chose pip
- Richer dataset columns (precipitation, region) — flagged as exactly the growth the Scope Guardrail prohibits
