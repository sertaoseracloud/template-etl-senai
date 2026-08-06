# Project Research Summary

**Project:** template_etl — AWS Glue 5.0 ETL Docker template with Floci local emulation
**Domain:** Open-source containerized ETL scaffolding (GitHub template repository)
**Researched:** 2026-08-06
**Confidence:** MEDIUM-HIGH overall

## Executive Summary

This template delivers a containerized AWS Glue 5.0 development environment (`public.ecr.aws/glue/aws-glue-libs:5`) with complete local emulation of S3, Glue Data Catalog, and Athena via Floci — a young (2026) but MIT-licensed, zero-token LocalStack alternative. The core value ("clone and `./run.sh`, everything works offline") is achievable, but depends critically on a **load-bearing architectural limitation: `GlueContext.create_dynamic_frame.from_catalog()` cannot be redirected to Floci** and must use path-based S3A reads locally, with catalog access only through boto3 (bootstrap script) and Athena/DuckDB (integration tests). This is verified across official AWS docs, open-source code inspection, and converging community attempts.

The roadmap's highest leverage is rigorous phase ordering — establish `./run.sh`, .env config, and Floci connectivity first, before any job code, to validate "one command, green" early. Two critical cross-platform blockers must land before the first `.sh` script: CRLF enforcement via `.gitattributes` and `MSYS_NO_PATHCONV=1` for Git Bash path mangling.

**Highest-stakes risk:** Floci is immature (1 year old); API coverage is provisional (research found `BatchCreatePartition` already missing). **Mitigation:** strict endpoint-only isolation, so swapping emulators costs one env var.

## Key Findings

### Recommended Stack

**Base image:** `public.ecr.aws/glue/aws-glue-libs:5` (not Docker Hub's `amazon/aws-glue-libs`, which stops at Glue 4.0)
- Spark 3.5.4, Python 3.11.6, Amazon Linux 2023, runs as `hadoop` user
- Jobs expected under `/home/hadoop/workspace/src/`
- Preinstalled: pytest, Iceberg, Hudi, Delta Lake
- **Confidence: HIGH** (official AWS docs)

**Local emulator:** `floci/floci:1.5.11` (pin version, never `latest`)
- S3, Glue Data Catalog (limited ops), Schema Registry, Athena-via-DuckDB
- **Not included:** job orchestration, crawlers, `BatchCreatePartition`
- Ships a baked-in `HEALTHCHECK`, so `depends_on: condition: service_healthy` needs no custom config
- **Confidence:** HIGH on scope; MEDIUM on completeness (young project, claims rest largely on Floci's own docs — little third-party validation exists yet)

**Catalog access (load-bearing limitation — ARCHITECTURAL RULE):**
- **Forbidden:** `GlueContext.create_dynamic_frame.from_catalog()` cannot redirect to Floci. The catalog read delegates to a closed-source JVM object (`self._ssql_ctx.getCatalogSource`) with no Python-layer endpoint override; the underlying client follows AWS SDK v1 conventions, which never gained endpoint-override support.
- **Solution:** Read/write via explicit `s3a://` paths with `create_dynamic_frame.from_options`; access the Catalog only through boto3 with `endpoint_url` and through Athena queries.
- **Evidence:** Reached independently by two researchers — one by reading `awsglue/context.py` source directly, one by triangulating six independent sources. AWS's own "zero AWS dependency" local-development post avoids the Catalog client entirely; the community project that got furthest (`glue-local-runner`) works around it by *removing* `hive-site.xml` rather than redirecting the client.
- **Confidence: MEDIUM-HIGH** (strong absence-of-evidence conclusion; no explicit AWS "this is impossible" statement exists, and the Java connector is closed-source)

**Spark/Hadoop S3A configuration (complete block required):**
```
spark.hadoop.fs.s3a.endpoint = "http://floci:4566"
spark.hadoop.fs.s3a.path.style.access = "true"       # REQUIRED for S3-compatible
spark.hadoop.fs.s3a.connection.ssl.enabled = "false"
spark.hadoop.fs.s3a.aws.credentials.provider = "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
```
**Critical:** `SimpleAWSCredentialsProvider` is non-negotiable — the default chain probes instance-metadata/env and causes 403/AccessDenied without it. The real failure mode is a *partial* override, not an absent one (evidenced in a still-open `aws-glue-libs` GitHub issue).

**Environment variable clarifications:**
- **Myth:** `DISABLE_SSL=true` and `AWS_REGION=us-east-1` are Glue container / Floci env vars
- **Reality:** Neither is read by Glue. Real mechanisms: Spark conf `spark.hadoop.fs.s3a.connection.ssl.enabled=false` and boto3's `AWS_DEFAULT_REGION`
- Flagged explicitly so it is not cargo-culted into the template
- **Confidence: HIGH** (AWS official docs + source code)

**`getResolvedOptions` behavior:**
- Plain `argparse` over `sys.argv`, not a JVM call — verified by reading `awsglue/utils.py` and `awsglue/job.py`
- Identical behavior locally and on AWS Glue; only the args-injection mechanism differs (`run.sh` vs `StartJobRun`)
- Removes an expected workaround layer
- **Confidence: HIGH** (source code inspected)

**Python tooling:** `uv` (0.12.2+), `ruff` (0.16.1+), `pytest` (8.3.4, bundled in the image), `chispa` (0.12.0) for DataFrame-equality assertions. AWS's own sample repo (`aws-samples/aws-glue-jobs-unit-testing`) uses a hand-rolled session-scoped `conftest.py` fixture — recommended over `pytest-spark`.

**Terraform provider:** `hashicorp/aws` `~> 6.0` (minimum **5.92.0** — earlier versions reject `python_version = "3.11"` on `glue_version = "5.0"`, a real historical bug, not theoretical)
**Confidence: HIGH**

### Expected Features

**Table Stakes:** README (Quick Start, structure, "how to adapt," local/AWS boundary), LICENSE (MIT), `.gitignore`, `.env.example`, dependency pinning, working CSV→Parquet example, GitHub Actions CI, CONTRIBUTING + issue templates

**Differentiators:** Local Glue Data Catalog emulation (surveyed competitors emulate only S3 and explicitly bypass the Catalog, or require real AWS credentials), Athena/DuckDB SQL validation (genuinely unmatched), single `./run.sh` entrypoint (no surveyed competitor offers clone→one command→green), Terraform included and CI-validated, zero-cost/offline (LocalStack Community now token-gated)

**Anti-Features (out of scope):** Cookiecutter, medallion example, devcontainer, Makefile, data-science folder structure, Jupyter, multiple package managers. Each traces to an explicit PROJECT.md Out-of-Scope or Constraint entry.

### Architecture

Docker Compose manages ephemeral Glue container invocations against a long-lived Floci service. `glue` sits behind a Compose `profiles:` entry and is invoked via `docker compose run --rm` per task — matching AWS's own documented `docker run --rm ... spark-submit` usage rather than an exec-into-long-lived-container pattern. Configuration flows strictly through environment variables (`.env` → compose → container), never hardcoded.

**Strict build order:**
1. Compose skeleton (Floci healthcheck)
2. `.env` + `run.sh` config flow
3. `catalog/bootstrap.py` (boto3, `CreatePartition` loop — **not** `BatchCreatePartition`)
4. `transforms/` + unit tests (pure PySpark, parallelizable)
5. `jobs/` entrypoint (thin, Glue-specific)
6. `tests/integration/` (end-to-end against Floci)
7. **Steps 1–6 deliver core value (MVP).** Terraform and CI follow — they reproduce the already-proven local loop rather than gate it.

**CI topology:** run the same `docker compose` / `run.sh` commands rather than modeling `glue` as a GitHub Actions `services:` sidecar — one source of truth for the topology. The Glue image is ~4.77 GB compressed and will dominate CI time.

### Critical Pitfalls

1. **`GlueContext` / `job.init()` silently expects real AWS** — fails if the S3A config is incomplete. The reported failure mode is a *partial* override. **Prevention:** ship the complete S3A block as one unit.
2. **Job bookmarks cannot be exercised locally** — no real JobRun exists. **Prevention:** document as AWS-only; do not attempt to test.
3. **`s3://` vs `s3a://` confusion** — boto3 and Spark have independent credential paths. **Prevention:** centralize in `.env`; verify both in the integration test.
4. **S3A commit semantics on an emulator** — `_temporary` directory semantics on non-AWS S3 may not replicate AWS behavior. **Prevention:** assert content in tests, not just exit code 0.
5. **IAM not enforced locally** — a permanent boundary, not a fixable bug. Jobs pass locally and fail with AccessDenied on real AWS. **Prevention:** least-privilege Terraform authored on faith; README must state "passing locally proves logic, not IAM."
6. **CRLF breaks shell scripts** — Git `core.autocrlf=true` checks out `.sh` with CRLF, breaking the shebang. **Prevention:** commit `.gitattributes` with `*.sh text eol=lf` **before the first `.sh` script**.
7. **Git Bash / MSYS2 path mangling** — MSYS2 rewrites POSIX paths before invoking `docker.exe`, breaking `-v` mounts. **Prevention:** `export MSYS_NO_PATHCONV=1` in `run.sh`, guarded for Linux/macOS. Not catchable on Linux CI — needs manual Windows verification.

## Implications for Roadmap

### Phase Structure (7 phases, 1–4 is MVP)

**Phase 1: Environment & Bootstrap**
- `docker-compose.yml`, `.env.example`, `run.sh`, **`.gitattributes` (CRLF before any `.sh`)**, `catalog/bootstrap.py`
- Validation: `run.sh up && run.sh bootstrap && run.sh down` → Catalog tables exist

**Phase 2: Transform Logic & Unit Tests**
- `transforms/csv_to_parquet.py` (pure PySpark), `tests/unit/`
- Parallelizable with Phase 1

**Phase 3: Glue Job Entrypoint & Execution**
- `jobs/csv_to_parquet/job.py`, `data/sample/input.csv`
- Validation: `run.sh up && run.sh bootstrap && run.sh job && run.sh down` → Parquet exists
- Research flag: empirically validate the complete S3A config against pinned Floci

**Phase 4: Integration Test & SQL Validation**
- `tests/integration/` (boto3 assertions, Athena/DuckDB query)
- Validation: full offline loop all green
- Research flag: validate DuckDB's Athena-SQL compatibility

**Phase 5: Terraform & Real-AWS Provisioning**
- `terraform/` module, `catalog/schema/*.json` as shared source of truth
- Validation: `terraform plan` clean

**Phase 6: GitHub Actions CI & Drift Detection**
- `.github/workflows/ci.yml`, scheduled weekly cron, explicit image caching decision
- Research flag: measure CI job duration empirically

**Phase 7: Documentation & Launch**
- README, CONTRIBUTING.md, issue templates, `docs/KNOWN_DIFFERENCES.md`

**Rationale:** Phase 1 blocks others. Phase 2 is parallelizable. Phase 3 before 4 (job must work before testing it). Phase 4 before 5 (local proven before Terraform). **Phases 1–4 deliver core value.**

### Research Flags

**Needing deeper research:** Phase 3 (S3A validation), Phase 4 (DuckDB/Athena dialect), Phase 6 (CI timing/disk space)

**Standard patterns (skip research):** Phases 1, 2, 5, 7

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | AWS Glue facts HIGH (official docs); Floci basics HIGH (official docs only); S3A config MEDIUM (community + GitHub issues); tooling/provider HIGH (verified) |
| Features | MEDIUM | Cross-referenced across 8+ competitor repos, only 2 fetched directly; anti-features locked in PROJECT.md (HIGH) |
| Architecture | HIGH | AWS patterns HIGH; Catalog question MEDIUM-HIGH (triangulated, but no explicit AWS "forbidden" statement and the connector is closed-source); build order HIGH |
| Pitfalls | MEDIUM | Grounded in AWS docs + community issues; Floci gaps emerge only from real usage; Windows path handling needs manual validation on real Windows |

**Overall: MEDIUM-HIGH.** Strengths: AWS stack stable, Floci core documented, patterns proven. Weaknesses: Floci is one year old, DuckDB/Athena dialect untested, Windows path handling needs real-Windows validation (GitHub CI insufficient).

### Gaps to Address During Planning

| Gap | How to Handle |
|-----|----------------|
| Floci operation fidelity beyond `BatchCreatePartition` | Phase 3/4: integration tests exercising key Catalog ops; document divergence; endpoint isolation keeps an emulator swap cheap |
| DuckDB SQL dialect compatibility vs Athena/Trino | Phase 4: write test SQL in a portable subset (SELECT/WHERE/COUNT); document Trino-specific syntax to avoid |
| `MSYS_NO_PATHCONV` effectiveness across Git Bash versions | Phase 1: include in `run.sh`; manual Windows validation required — GitHub CI is insufficient |
| GitHub Actions image pull timing | Phase 6: measure empirically; if pull dominates, investigate layer caching |
| **Shared schema drift (`bootstrap.py` vs Terraform)** | Unresolved open design question. Proposal: `catalog/schema/*.json` as single source of truth consumed by both. Must be settled during Phase 1/5 planning |

## Sources

Synthesized from the four project research documents in this directory, each of which carries its own inline source URLs and confidence annotations:

- `.planning/research/STACK.md` — toolchain, versions, exact config keys
- `.planning/research/FEATURES.md` — table stakes, differentiators, anti-features, competitor survey
- `.planning/research/ARCHITECTURE.md` — container topology, config flow, `from_catalog` finding, parity table, build order
- `.planning/research/PITFALLS.md` — 13 pitfalls with warning signs, prevention, and phase mapping

---

**Research completed: 2026-08-06 | Ready for roadmap: yes**
