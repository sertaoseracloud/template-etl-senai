# Local Development

## Requirements

- **Docker Desktop** v4.x+ on Windows (with WSL2 backend)
- **Bash** (Git Bash / MSYS2 or WSL)
- **Python** 3.11+ (only for `./run.sh bootstrap` and `./run.sh seed`, which run in the tools container)

## Quick Start

```bash
cp .env.example .env          # fill in your PROJECT_NAME
./run.sh demo                 # up → bootstrap → seed → job → test
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PROJECT_NAME` | Yes | — | Used to derive bucket names: `{PROJECT_NAME}-raw` / `{PROJECT_NAME}-curated` |
| `AWS_ENDPOINT_URL` | Yes | — | Local emulator endpoint (e.g. `http://localhost:4566`) |
| `AWS_DEFAULT_REGION` | Yes | — | AWS region (e.g. `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | Yes | — | Credentials for the emulator |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | Credentials for the emulator |
| `FLOCI_HOST_PORT` | No | `4566` | Port on the host where Floci listens |

## Architecture

```
Host (Windows)
  └── Docker Desktop (WSL2 backend)
        ├── floci           → S3 + Glue Catalog + Athena endpoints
        │                         (floci-duck sidecar for Athena)
        ├── glue            → AWS Glue 5.0 container (Spark 3.5)
        │                         runs ./run.sh job and ./run.sh test
        └── tools           → slim Python 3.11 image
                              runs catalog bootstrap/seed scripts
```

**Bucket naming**: underscores in `PROJECT_NAME` are replaced with hyphens.
Example: `PROJECT_NAME=template_etl` → `template-etl-raw`, `template-etl-curated`.

## Running Commands

| Command | What it does |
|---|---|
| `./run.sh up` | Start emulator, bootstrap catalog, seed sample data |
| `./run.sh bootstrap` | Create Glue database, table, and partitions |
| `./run.sh seed` | Upload sample CSVs to the raw bucket |
| `./run.sh job` | Run the csv_to_parquet Glue job |
| `./run.sh test` | Run pytest suite (unit + integration, athena tests skipped) |
| `./run.sh lint` | Run ruff check + format check |
| `./run.sh demo` | Run up, job, test, and print a summary |
| `./run.sh down` | Stop emulator and remove volumes |

## Tests

### Unit tests (always run)

```bash
./run.sh test                # runs inside the Glue container
```

Unit tests use a session-scoped SparkSession fixture (`conftest.py`) and
exercise only `transforms/` — no AWS SDK, no Glue API.

### Integration tests (always run)

Three integration tests run with every test invocation:

- `test_job_runs_successfully` — job completes with exit 0 and emits summary
- `test_job_output_content` — at least 18 parquet files written, all 3 dates × 6 cities present
- `test_job_produces_no_temp_commit_files` — no `_spark_metadata` or `_SUCCESS` at shallow path depth

These tests run the job via **subprocess `spark-submit`** (not in-process), exercise the full S3A path, and assert on the actual output stored in the emulated bucket.

### Athena tests (skipped by default)

Four tests require the Floci Athena endpoint (DuckDB-backed):

```bash
docker compose --profile glue run --rm glue \
  -c "python3 -m pytest tests/ --with-integration -v"
```

The Athena sidecar (`floci-duck`) is started automatically by Floci via the
Docker socket mounted from the host. It runs as a sibling container and
serves the Athena API endpoint on port 8442 inside the floci container.

> **Windows note:** On Windows + Docker Desktop, the Athena sidecar requires the
> Docker TCP socket to be exposed (`docker context ls` → tcp://localhost:2375).
> Without it, the sidecar fails with `java.net.BindException: Permission denied`.
> The 4 Athena tests are skipped automatically via `pytest -m "not athena"` in
> `./run.sh test`. On Linux or Mac with Docker Desktop, exposing the TCP socket
> via the Docker Desktop settings enables the full test suite.

### Running tests with Athena enabled (Linux/Mac)

```bash
# Expose the Docker TCP socket in Docker Desktop settings first, then:
docker compose --profile glue run --rm glue \
  -c "python3 -m pytest tests/ --with-integration -v"
```

## Project Layout

```
.
├── jobs/
│   └── csv_to_parquet/
│       └── job.py               # ETL entry point (awsglue + argparse)
├── transforms/
│   └── csv_to_parquet.py        # Pure PySpark transformations
├── catalog/
│   ├── bootstrap.py             # Create database, table, partitions
│   └── seed.py                  # Upload sample CSV data
├── tests/
│   ├── conftest.py              # Session-scoped SparkSession + D-08 invariant
│   ├── unit/
│   │   └── test_transforms.py   # Unit tests (11 tests)
│   └── integration/
│       └── test_job.py          # Integration + Athena tests (7 tests)
├── docker-compose.yml
├── run.sh
└── .env                         # (gitignored, create from .env.example)
```

## Known Limitations

- **Docker Desktop on Windows** — the Athena sidecar (`floci-duck`) requires a
  TCP-exposed Docker socket. On Windows this must be enabled manually in
  Docker Desktop settings. Without it, the 4 Athena tests are skipped.
- **Memory-mode Floci** — data in S3 is lost when `floci` restarts.
  Re-run `./run.sh up` (or `./run.sh bootstrap && ./run.sh seed`) after a restart.
- **`sys.path` in the Glue container** — the job working directory is
  `/home/hadoop/workspace` (bind-mounted project root). Python does not add the
  current working directory to `sys.path` automatically; `job.py` handles this
  with `sys.path.insert(0, str(Path.cwd()))` before importing transforms.
