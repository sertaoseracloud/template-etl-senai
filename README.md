# template_etl

[![CI](https://github.com/<org>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/<repo>/actions/workflows/ci.yml)

A template for building ETL pipelines with AWS Glue 5.0. Runs entirely offline
using a local emulator — clone, run one command, see the full pipeline work, then
replace the sample job with your own.

---

## Quick Start

```bash
git clone <your-fork-url>
cd <your-repo>
cp .env.example .env      # fill in your PROJECT_NAME
./run.sh demo             # up → bootstrap → seed → job → test
```

One command takes a clean clone to a green pipeline: Floci emulator healthy,
catalog populated, sample job executed, tests passing — no AWS account, no
credentials, no manual steps.

> **Windows (Git Bash):** `run.sh` works as-is. Docker Compose path arguments are
> guarded internally against MSYS2 path rewriting. Always use `./run.sh` instead
> of running `docker compose` commands directly.

---

## Architecture

The local environment emulates three AWS services:

- **Floci** — S3, Glue Data Catalog, and Athena, served without a token.
  Floci uses a DuckDB sidecar for Athena queries. The entire stack runs in
  Docker, no cloud account required.
- **AWS Glue 5.0** (Spark 3.5, Python 3.11) — the job runtime. The container is
  pulled on the first `./run.sh job` invocation (~4.8 GB). The job uses explicit
  `s3a://` paths via `from_options`, not `from_catalog`, because the Glue Catalog
  client does not redirect to the local emulator.
- **Data Catalog** — schemas are registered by the `bootstrap` step using boto3.
  Crawlers are not available locally; schema registration uses `CreateTable` and
  `CreatePartition`.

**Pipeline shape:** S3 (raw) → Glue job → S3 (curated).

The job writes in append mode. Re-running `./run.sh demo` without stopping the
emulator first doubles the row count in each partition — this is the intended
behaviour, not a bug.

**The Terraform module (in `terraform/`) is validated offline and is never
applied during development or in CI.** It provisions Glue Job, IAM role, S3
buckets, and the Data Catalog for a real AWS account. See
[docs/KNOWN_DIFFERENCES.md](docs/KNOWN_DIFFERENCES.md) for what passing locally
does and does not prove.

---

## Project Structure

```
run.sh                 # Entrypoint: up, down, bootstrap, seed, job, test, lint, demo
catalog/               # Schema definitions and boto3 bootstrap scripts
  config.py            # All resource names derive from one PROJECT_NAME variable
  schema/              # Table schema (single source of truth for bootstrap and Terraform)
  bootstrap.py         # Register database, table, and partitions in the Glue Catalog
  seed.py              # Upload sample CSVs to the emulated S3 raw bucket
transforms/            # Pure PySpark transformations (testable without Glue or AWS)
jobs/                  # Glue job entrypoints (awsglue wiring only)
tests/                 # Pytest suite: unit tests + integration tests
terraform/             # Terraform module: Glue Job, IAM role, S3 buckets, Catalog
  modules/             # Reusable sub-modules (glue-job, iam-role, s3-buckets, catalog-table)
docs/                  # Local development guide
data/sample/           # Sample CSVs with synthetic temperature data for SC cities
.env.example           # All required environment variables (copy to .env)
docker-compose.yml     # Floci emulator and tools container definitions
```

---

## How to Adapt

Replace the sample pipeline with your own in five steps:

- **PROJECT_NAME** in `.env` and `.env.example` — all resource names derive
  from this one variable: `${PROJECT_NAME}-raw`, `${PROJECT_NAME}-curated`,
  `${PROJECT_NAME}_db`. Change it and the whole naming follows.
- **City data** in `data/sample/` — the bundled sample CSVs cover six Santa
  Catarina cities and are labelled as synthetic. Relabel or replace them with
  your own data.
- **Temperature column logic** in `transforms/csv_to_parquet.py` — if your
  input columns have different names, update the column references here.
- **Glue version** in `terraform/variables.tf` — bump the version if you need
  a newer Glue runtime in production.
- **Database, bucket, and job names** are derived automatically from
  `PROJECT_NAME`. No additional renaming required.

---

## Known Differences

Running locally is not the same as running on real AWS. Key differences:

- **IAM is not enforced locally** — passing locally proves Spark logic, not IAM policy. See `terraform/iam.tf` for the intended policy.
- **Job bookmarks are not implemented locally** — the job re-processes all files on each run.
- **No crawlers or StartJobRun locally** — schema registration uses the bootstrap script instead.
- **`from_catalog` is unavailable locally** — the Glue Catalog client does not redirect to the emulator. The job uses explicit `s3a://` paths.
- **Terraform is validated offline, never applied** — `init -backend=false`, `fmt -check`, and `validate` run in CI. Applying to a real account requires credentials.

---

## Event-Driven Triggers (EventBridge)

**Floci does NOT support EventBridge.** The local development environment uses a polling workaround instead.

### Local Development: Polling Simulation

The `./run.sh watch` command polls the emulated S3 bucket for new files and triggers the Glue job with the `--file-key` parameter:

```bash
# Upload a file (simulates S3 PUT event)
./run.sh upload data/sample/temperaturas_2026-01-15.csv

# Start watching for new files
./run.sh watch
```

### Production: EventBridge Trigger

In production on real AWS, EventBridge handles the event-driven flow automatically:

1. S3 receives a new object (ObjectCreated event)
2. EventBridge rule detects the event
3. EventBridge triggers the Glue job with `--file-key` parameter
4. Job processes only the specified file

The `--file-key` parameter and `FILE_KEY` environment variable enable this pattern:

```bash
# Job accepts --file-key from EventBridge
spark-submit job.py --JOB_NAME csv_to_parquet --file-key temperaturas/file.csv
```

Full table at [docs/KNOWN_DIFFERENCES.md](docs/KNOWN_DIFFERENCES.md).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
