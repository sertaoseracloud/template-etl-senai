# Architecture Research: AWS Glue 5.0 ETL Template (Docker + Floci)

**Domain:** Open-source ETL scaffolding — AWS Glue 5.0 (Spark 3.5 / Python 3.11) containerized job development with local AWS emulation
**Researched:** 2026-08-06
**Confidence:** HIGH for container topology, config flow, and the Catalog-endpoint question (verified against official AWS docs and library source code). MEDIUM for CI timing estimates (no official benchmark found for this exact combination).

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              Host / CI runner                             │
│                                                                            │
│   ./run.sh  (single entrypoint — up | bootstrap | job | test | lint |    │
│              down)                                                        │
│                                                                            │
│   Reads .env → exports AWS_ENDPOINT_URL, AWS_REGION, AWS_ACCESS_KEY_ID,  │
│   AWS_SECRET_ACCESS_KEY, GLUE_DATABASE, S3_BUCKET_* → passes them into   │
│   `docker compose` as environment for every service                      │
└───────────────┬───────────────────────────────────┬──────────────────────┘
                │                                    │
                │ docker compose up -d floci         │ docker compose run --rm glue ...
                ▼                                    ▼
┌────────────────────────────┐     ┌──────────────────────────────────────┐
│  floci (long-lived service) │     │  glue (one-shot, ephemeral service)   │
│  image: floci/floci:1.5.11  │◄────┤  image: public.ecr.aws/glue/          │
│  port 4566, in-process:     │ AWS │         aws-glue-libs:5                │
│  S3, Glue Data Catalog,     │ SDK │  runs, per invocation:                │
│  Schema Registry, Athena    │ calls│   - bootstrap.py (boto3 → Catalog)   │
│  (DuckDB sidecar)           │ over │   - spark-submit job.py (PySpark)    │
│  HEALTHCHECK baked into     │ HTTP │   - pytest (unit + integration)      │
│  the image itself           │     │  user: hadoop, HOME=/home/hadoop      │
└──────────────┬──────────────┘     └──────────────────┬────────────────────┘
               │                                        │
               │ S3 API (in-process)                    │ spark.hadoop.fs.s3a.*
               ▼                                        │ → same floci:4566 endpoint
       in-memory / persistent                           ▼
       object store (bucket = S3_BUCKET_*)  ◄── Parquet/CSV read+write (S3A)

Terraform (separate, not part of the docker-compose graph):
  provisions the SAME shape — Glue Job, IAM role, S3 buckets, Data Catalog —
  against real AWS. Consumes the same variable names the bootstrap script
  uses, so schema is defined once and read by both paths.
```

### Component Responsibilities

| Component | Responsibility | Talks to |
|-----------|-----------------|----------|
| `floci` service | Emulates S3, Glue Data Catalog, Schema Registry, Athena (via DuckDB sidecar) on port 4566. In-process only for these services — no Docker socket needed. | Receives AWS SDK calls (SigV4-shaped HTTP) from `glue` container and from host tooling (Terraform validation, host-side `aws`/`boto3` scripts) |
| `glue` service (aws-glue-libs:5) | Runs the actual workload: catalog bootstrap (boto3), the PySpark job (`spark-submit`), and pytest. Never runs long-lived — invoked per task via `docker compose run --rm`. | S3A → `floci:4566` for data; boto3 Glue client → `floci:4566` for catalog bootstrap; **not** used for `from_catalog` reads locally (see Catalog-endpoint finding below) |
| `bootstrap.py` (boto3) | Idempotently creates database/table/partition metadata in the Catalog — the crawler replacement. Single source of schema truth. | `floci` (local) or real Glue Catalog (prod), both via the same boto3 client code, differing only by `endpoint_url` |
| `run.sh` | Orchestrates the above: brings `floci` up and waits for it to be healthy, runs bootstrap, runs the job, runs tests, tears down. Single entrypoint, no Makefile. | `docker compose` CLI only |
| Terraform | Provisions the real-AWS equivalent of what `floci` + `bootstrap.py` emulate locally: Glue Job resource, IAM role, S3 buckets, Glue Catalog database/tables. | Real AWS API only; never talks to `floci` |
| GitHub Actions | Builds nothing bespoke — pulls `aws-glue-libs:5` and `floci`, runs the same `run.sh` subcommands the local developer runs. | Same `docker compose` graph as local dev |

## Recommended Project Structure

```
.
├── run.sh                          # single entrypoint: up|bootstrap|job|test|lint|down
├── docker-compose.yml              # floci + glue service definitions
├── .env.example                    # documents every variable consumed by compose/job/terraform
├── .env                            # gitignored, developer's local copy
│
├── jobs/
│   └── csv_to_parquet/
│       ├── job.py                  # THIN entrypoint: getResolvedOptions + GlueContext wiring only
│       └── __init__.py
│
├── transforms/                     # pure Python/PySpark logic — importable, Glue-free
│   ├── __init__.py
│   └── csv_to_parquet.py           # def transform(df: DataFrame) -> DataFrame: ...
│
├── catalog/
│   ├── bootstrap.py                # boto3 script: creates database/table/partitions
│   └── schema/
│       └── csv_to_parquet.json     # single schema definition consumed by bootstrap.py AND terraform (via a data source / template file)
│
├── tests/
│   ├── unit/
│   │   └── test_csv_to_parquet.py  # imports transforms/, runs with local SparkSession, NO Glue/AWS
│   └── integration/
│       └── test_job_e2e.py         # runs against floci: writes fixture to S3, invokes job via docker compose run, asserts output + Catalog state via boto3/Athena
│
├── data/
│   └── sample/
│       └── input.csv               # tiny sample dataset, mounted into the glue container
│
├── terraform/
│   ├── main.tf                     # Glue Job, IAM role
│   ├── s3.tf                       # buckets
│   ├── glue_catalog.tf             # database/table resources — should read the SAME schema/*.json bootstrap.py uses
│   ├── variables.tf
│   └── outputs.tf
│
├── docker/
│   └── glue/
│       └── (no custom Dockerfile expected — official image used as-is; only add a Dockerfile here if JDBC/jars must be layered in per the "Appendix: Adding JDBC drivers" pattern)
│
├── .github/
│   └── workflows/
│       └── ci.yml                  # pulls both images, runs run.sh test / run.sh lint
│
└── docs/
    ├── ARCHITECTURE.md             # (this project's own, post-build)
    └── KNOWN_DIFFERENCES.md        # local-vs-AWS parity table (see below)
```

### Structure Rationale

- **`transforms/` is separated from `jobs/`** to satisfy the hard constraint: transformation logic must be unit-testable without Glue/AWS. `transforms/csv_to_parquet.py` takes and returns a plain PySpark `DataFrame` (or pandas, if the transform is trivial enough) — it imports only `pyspark.sql`, never `awsglue`. `jobs/csv_to_parquet/job.py` is the only file that imports `awsglue.transforms`, `awsglue.utils.getResolvedOptions`, `awsglue.context.GlueContext`, and `awsglue.job.Job`; its body is glue code (pun intended) that resolves args, builds a `GlueContext`, reads a `DynamicFrame`, converts `.toDF()`, calls `transforms.csv_to_parquet.transform(df)`, converts back, and writes. This mirrors the split AWS's own `aws-glue-jobs-unit-testing` sample and community guides converge on: keep `awsglue` imports out of anything you want `pytest` to import directly on a local machine without the container.
- **`catalog/schema/*.json` is the single schema source** consumed by both `bootstrap.py` (local/emulated Catalog) and referenced by Terraform (real Catalog) — this operationalizes the "no crawler" decision: one versioned definition, two consumers, so schema drift between local and prod is structurally prevented rather than merely documented.
- **`tests/unit/` vs `tests/integration/`** split maps directly to the two runtime realities: unit tests run under plain `pytest` (or even outside any container, if `pyspark` is installed locally) against `transforms/`; integration tests require the `aws-glue-libs` container (for `awsglue`/Spark) and the `floci` container (for S3/Catalog) and are the ones that exercise `from_options` S3A reads plus boto3/Athena assertions.
- **No Makefile, no devcontainer** — `run.sh` is deliberately the only orchestration surface, per the locked decision, and it must degrade gracefully on Windows Git Bash (no reliance on GNU-only flags).

## Architectural Patterns

### Pattern 1: Thin entrypoint / pure transform split

**What:** `job.py` does only argument resolution + I/O wiring (`getResolvedOptions`, `GlueContext`, `create_dynamic_frame.from_options`/`from_catalog`, `.write`). All business logic lives in a plain function in `transforms/` that accepts/returns a Spark `DataFrame` and has zero AWS Glue imports.
**When to use:** Always, for every job in this template — it is the mechanism that makes the "unit-testable without Glue/AWS" requirement achievable at all, since `awsglue` is only importable inside the `aws-glue-libs` container (it's not on PyPI).
**Trade-offs:** Slightly more indirection than writing everything inline in the job script; in exchange, `pytest tests/unit` can run on a bare `pip install pyspark` environment (or inside the container too, but doesn't require it), which keeps the fast feedback loop fast.

**Example:**
```python
# transforms/csv_to_parquet.py — no awsglue import, testable anywhere with pyspark installed
from pyspark.sql import DataFrame

def transform(df: DataFrame) -> DataFrame:
    return df.dropDuplicates().withColumnRenamed("id", "record_id")
```
```python
# jobs/csv_to_parquet/job.py — the only file that touches awsglue
import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from transforms.csv_to_parquet import transform

args = getResolvedOptions(sys.argv, ["JOB_NAME", "S3_INPUT_PATH", "S3_OUTPUT_PATH"])
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

df = glueContext.spark_session.read.option("header", True).csv(args["S3_INPUT_PATH"])
transform(df).write.mode("overwrite").parquet(args["S3_OUTPUT_PATH"])

job.commit()
```

### Pattern 2: `docker compose run --rm` for the job, not a long-lived exec target

**What:** The `glue` service is declared in `docker-compose.yml` but is not part of the default `docker compose up` graph — either omit it from `up`'s target set or put it behind a Compose `profiles:` entry (`profiles: ["tools"]`), so `docker compose up` only starts `floci`. Every job/bootstrap/test invocation is `docker compose run --rm glue <command>`.
**When to use:** This template's success criterion ("one command, green") — a one-shot ephemeral container per invocation matches exactly how AWS's own documentation runs the image (`docker run -it --rm ... spark-submit ...` / `... -c "python3 -m pytest ..."`), so the template stays close to officially-supported usage instead of inventing a custom long-lived-container-plus-exec pattern.
**Trade-offs:** `docker compose exec` into a long-lived `glue` container would start faster on repeat runs (no container churn) but (a) diverges from AWS's documented usage pattern, (b) requires the container to have a persistent foreground process (`tail -f /dev/null` or similar) which is unidiomatic for compose, and (c) risks state leaking between "clean" runs, which cuts against a template whose whole point is a repeatable, disposable, green-from-scratch flow. `docker compose run --rm` is the better fit for a template; its cost (image already pulled, so container startup itself is only a few seconds) is negligible next to Spark's own JVM startup time.

**Example:**
```yaml
# docker-compose.yml (excerpt)
services:
  floci:
    image: floci/floci:1.5.11
    ports: ["4566:4566"]
    environment:
      - FLOCI_HOSTNAME=floci
    # HEALTHCHECK is baked into the floci image itself (verified in docker/Dockerfile.native
    # in floci-io/floci) — no custom healthcheck: block is required in this compose file.

  glue:
    image: public.ecr.aws/glue/aws-glue-libs:5
    profiles: ["tools"]          # never started by `docker compose up`
    depends_on:
      floci:
        condition: service_healthy
    volumes:
      - ./jobs:/home/hadoop/workspace/jobs
      - ./transforms:/home/hadoop/workspace/transforms
      - ./catalog:/home/hadoop/workspace/catalog
      - ./tests:/home/hadoop/workspace/tests
      - ./data:/home/hadoop/workspace/data
    working_dir: /home/hadoop/workspace
    environment:
      - AWS_ENDPOINT_URL=http://floci:4566
      - AWS_REGION=${AWS_REGION}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
```
```bash
# run.sh (excerpt)
docker compose up -d floci                       # depends_on/service_healthy not evaluated by `up` alone for a target not included; call out explicitly below
docker compose run --rm glue python3 catalog/bootstrap.py
docker compose run --rm glue spark-submit jobs/csv_to_parquet/job.py --JOB_NAME csv_to_parquet ...
docker compose run --rm glue -c "python3 -m pytest --disable-warnings"
```
Note: because `glue` is gated by `profiles`, `docker compose run --rm glue ...` still honors its own `depends_on: floci: condition: service_healthy` — Compose evaluates dependency conditions for any service being started, including via `run`, so `floci` will be started/waited-on automatically the first time `run.sh` calls `docker compose run --rm glue ...` even without a prior explicit `up -d floci`. Calling `up -d floci` first is still recommended for a clear, single wait point and clean log output before bootstrap/job/tests run in sequence.

### Pattern 3: Environment-variable-only AWS configuration, identical code path both places

**What:** Every place that constructs an AWS client (boto3, Spark's `fs.s3a.*`, Glue's own SDK usage) reads `AWS_ENDPOINT_URL` / `AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from the environment, never hardcoded. Locally, `AWS_ENDPOINT_URL=http://floci:4566` with dummy credentials; in AWS, `AWS_ENDPOINT_URL` is unset (SDKs fall back to the real regional endpoints) and credentials come from the Glue job's IAM role.
**When to use:** Always — this is the locked decision and it is what makes swapping the emulator (or later, adding a second one) cost one env var rather than a code change.
**Trade-offs:** None significant; the only care point is that `getResolvedOptions` (Glue's own CLI-argument mechanism) is a *separate* channel from environment variables — it resolves `--KEY value` pairs from `sys.argv`, not from the OS environment. Locally, `spark-submit` must be given the same `--KEY value` job arguments a real `StartJobRun` call would inject (`run.sh`/compose passes them as command args, not env vars), while endpoint/credentials flow through the OS environment into boto3 and Spark's Hadoop config. These are two independent, parallel configuration channels feeding the same job script and must not be conflated.

## Data Flow

### Configuration Flow

```
.env  (developer-edited; template ships .env.example)
   │  AWS_REGION=us-east-1
   │  AWS_ACCESS_KEY_ID=test
   │  AWS_SECRET_ACCESS_KEY=test
   │  AWS_ENDPOINT_URL=http://floci:4566      ← unset/absent for real-AWS runs
   │  S3_BUCKET_RAW=raw-bucket
   │  S3_BUCKET_PROCESSED=processed-bucket
   │  GLUE_DATABASE=etl_template
   ▼
docker-compose.yml
   reads .env via Compose's built-in env_file/--env-file mechanism,
   injects into `environment:` of both floci and glue services
   ▼
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│ floci container               │        │ glue container                     │
│ AWS_ENDPOINT_URL not needed   │        │ boto3.client("glue",               │
│ by floci itself (it IS the    │◄───────┤   endpoint_url=os.environ[         │
│ endpoint) — but FLOCI_HOSTNAME│  HTTP  │   "AWS_ENDPOINT_URL"])              │
│ must be set so returned URLs  │  4566  │ boto3.client("s3", endpoint_url=..)│
│ resolve to `floci`, not       │        │ Spark: spark.hadoop.fs.s3a.endpoint│
│ `localhost`, from inside the  │        │   = same AWS_ENDPOINT_URL value    │
│ glue container's network      │        │ spark.hadoop.fs.s3a.path.style     │
│ namespace                     │        │   .access = true                   │
└─────────────────────────────┘        │ spark.hadoop.fs.s3a.access.key    │
                                          │   = $AWS_ACCESS_KEY_ID             │
                                          │ spark.hadoop.fs.s3a.secret.key    │
                                          │   = $AWS_SECRET_ACCESS_KEY         │
                                          └──────────────────┬─────────────────┘
                                                              │
                                              separate channel: job args
                                                              │
                                          run.sh / docker compose run passes:
                                            spark-submit job.py \
                                              --JOB_NAME csv_to_parquet \
                                              --S3_INPUT_PATH s3://raw-bucket/... \
                                              --S3_OUTPUT_PATH s3://processed-bucket/...
                                                              │
                                                              ▼
                                          getResolvedOptions(sys.argv, [...])
                                          — pure argparse over sys.argv, verified
                                            in awsglue/utils.py source: no JVM,
                                            no SparkContext, no Glue runtime
                                            dependency. Identical behavior
                                            locally and on real Glue — the only
                                            difference is WHO populates sys.argv
                                            (run.sh locally; Glue's StartJobRun
                                            argument injection in AWS).
```

**Production (real AWS) path:** `AWS_ENDPOINT_URL` is simply absent from the Glue job's environment. boto3 and the AWS SDK for Java (used internally by GlueContext) fall back to their default regional endpoint resolution. Credentials come from the Glue job's IAM execution role via the instance/container credential provider chain — never from `.env`. Terraform provisions that IAM role, the S3 buckets, and the Glue Catalog database/tables using the *same* `S3_BUCKET_*` / `GLUE_DATABASE` names defined in `.env.example`, so the naming contract between local and prod is explicit and centralized rather than duplicated.

### Key Data Flows

1. **Bootstrap (Catalog population):** `run.sh bootstrap` → `docker compose run --rm glue python3 catalog/bootstrap.py` → boto3 Glue client (endpoint = `floci:4566` locally / real Glue in prod) → `CreateDatabase`/`CreateTable`/`CreatePartition` (looped — `BatchCreatePartition` is not in Floci's supported-operations list per the project's own research, so bootstrap must call `CreatePartition` once per partition, which is also forward-compatible with real AWS since `CreatePartition` is always supported there too).
2. **Job execution:** `run.sh job` → `docker compose run --rm glue spark-submit jobs/csv_to_parquet/job.py --JOB_NAME ... --S3_INPUT_PATH ... --S3_OUTPUT_PATH ...` → job reads CSV via `from_options`/Spark's native CSV reader against S3A pointed at `floci:4566`, transforms via `transforms.csv_to_parquet.transform`, writes Parquet back to S3A.
3. **Verification:** `run.sh test` (integration) → boto3 `Glue.get_table`/`get_partitions` against `floci:4566` confirms Catalog state, and/or an Athena query (via Floci's DuckDB sidecar) against the emulated Catalog confirms the Parquet output is queryable as SQL — this is explicitly a capability the project's research already flagged as new territory Floci opens up that LocalStack Community never offered.

## Scaling Considerations

Not the relevant axis for this project — this is a development/CI template, not a production service. The closest analogue to "scale" here is elapsed time and reliability under repeated `./run.sh` invocations (local) and CI runs (GitHub Actions), addressed in the CI Topology section below.

## Anti-Patterns

### Anti-Pattern 1: Calling `GlueContext.create_dynamic_frame.from_catalog()` against Floci and expecting it to work

**What people might do:** Assume that because Floci implements the Glue Data Catalog API (CreateTable/GetTable/etc.), pointing the *job's own* `GlueContext.create_dynamic_frame.from_catalog()` call at Floci's endpoint will transparently read via the Catalog, the same way `boto3.client("glue", endpoint_url=...)` does.
**Why it's wrong:** See the dedicated finding below — the Catalog-reading code path inside `GlueContext` is not the same code path as boto3's Glue client, and there is no documented, supported way to redirect it to a non-AWS endpoint.
**Instead:** In the local/emulated path, read and write data via `create_dynamic_frame.from_options`/native Spark readers against S3A (which *does* have a fully documented endpoint-override mechanism), and exercise the Catalog only through boto3 (bootstrap script, integration test assertions) and Athena-via-DuckDB queries. Document this split explicitly in the README so users don't assume Catalog-driven reads are being demonstrated locally when they are not.

### Anti-Pattern 2: Treating `docker compose exec` into a long-lived `glue` container as the job-running mechanism

**What people might do:** Start the `glue` service with `docker compose up -d` alongside `floci`, then `docker compose exec glue spark-submit ...` for every run, to save container startup overhead.
**Why it's wrong:** The official image has no long-running foreground process; it's designed to be invoked per-command (`docker run --rm ... spark-submit ...` / `... pyspark` / `... pytest`) per AWS's own documentation. Forcing it into a long-lived role means inventing a keep-alive command not sanctioned by AWS, and it risks accumulating state (temp files, half-written outputs) between "clean" template runs, undermining reproducibility.
**Instead:** Use `docker compose run --rm glue <command>` per invocation, exactly as covered under Pattern 2 above.

### Anti-Pattern 3: Wiring `.env` values directly into `docker-compose.yml` `command:` strings instead of the container's own env/args resolution

**What people might do:** Bake `S3_INPUT_PATH=s3://raw-bucket/data.csv` etc. as literal strings into the compose file's `command:`, defeating the purpose of a single `.env`-driven configuration surface.
**Why it's wrong:** Breaks the "swap emulator = one env var" guarantee, and makes the Terraform/local naming contract implicit instead of explicit.
**Instead:** Keep `.env` → Compose `environment:`/`env_file:` → shell variable substitution in `run.sh`'s invocation of `docker compose run` as the only place values are threaded through.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| `floci` (S3, Glue Catalog, Schema Registry, Athena) | boto3 clients + Spark `fs.s3a.*` Hadoop config, all pointed at `AWS_ENDPOINT_URL` | Glue jobs/crawlers/triggers/workflows are NOT emulated (confirmed against Floci's own service table: Glue = "Data Catalog, Schema Registry, tables consumed by Athena" only) |
| Real AWS (production) | Same boto3/Spark code, `AWS_ENDPOINT_URL` unset, IAM role credentials | Terraform-provisioned; Job bookmarks, Data Catalog client used by `from_catalog`, and Lake Formation only exist here |
| GitHub Actions | Pulls both images fresh per run (no bespoke build) | See CI Topology below |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `jobs/*/job.py` ↔ `transforms/*.py` | Direct Python import, plain `DataFrame` in/out | The only boundary that must survive without any `awsglue`/AWS dependency — this is what `tests/unit` exercises |
| `glue` container ↔ `floci` container | HTTP (AWS SigV4-shaped requests) over the Compose network, port 4566 | `depends_on: condition: service_healthy` gates every `glue` invocation on Floci's own baked-in `HEALTHCHECK` |
| `catalog/bootstrap.py` ↔ Terraform | Shared schema definition file (`catalog/schema/*.json`), not runtime coupling | Prevents schema drift between the two provisioning paths without introducing a runtime dependency between them |

---

## Q4 — The Catalog-Endpoint Question (highest-stakes finding)

**Plain answer: No — `GlueContext.create_dynamic_frame.from_catalog()` cannot be honestly pointed at Floci (or any non-AWS Glue endpoint) in this template. The local path must use `from_options`/path-based S3A reads for Spark, and exercise the Data Catalog only through boto3 (bootstrap, assertions) and Athena-via-DuckDB.** Confidence: MEDIUM-HIGH — this is an absence-of-evidence conclusion (no documented override mechanism exists anywhere, across official docs, the open-source Python wrapper, and multiple independent community attempts), not a single authoritative "this is impossible" statement, because the Java connector that actually performs the catalog call is closed-source and not published on GitHub.

**Evidence:**

1. **The Python `create_dynamic_frame_from_catalog` call delegates entirely to a closed-source JVM object.** Reading `awsglue/context.py` directly (`github.com/awslabs/aws-glue-libs`, `master` branch) shows `create_dynamic_frame_from_catalog` calling `self._ssql_ctx.getCatalogSource(db, table_name, redshift_tmp_dir, transformation_ctx, ...)`. `self._ssql_ctx` is a `sc._jvm` object — a Java/Scala class bundled as a proprietary JAR inside the `aws-glue-libs` image, not part of the open-source `awsglue` Python package and not published on GitHub. There is no Python-layer parameter for `endpoint_url`, and no visible hook for one. (Source: `awsglue/context.py`, read directly.)

2. **AWS's own official local-dev documentation never uses `from_catalog` against anything other than a real AWS account.** The "Develop and test AWS Glue jobs locally using a Docker image" doc mounts `~/.aws` credentials and uses `AWS_PROFILE`, implying that if you *do* call `from_catalog` from the container, it resolves against your real AWS account's Catalog in whatever region your profile/`AWS_REGION` points to — not a redirectable local endpoint. (Source: `docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html`.)

3. **AWS's own "Building an AWS Glue ETL pipeline locally without an AWS account" blog post — the closest thing to an official "no AWS dependency" local-dev guide — never demonstrates `from_catalog`.** It builds `DynamicFrame`s from in-memory Python data via `DynamicFrame.fromDF()` instead, explicitly avoiding any Catalog interaction. If AWS's own zero-AWS-dependency guidance sidesteps the Catalog client entirely, that is strong circumstantial evidence no supported redirect exists. (Source: `aws.amazon.com/blogs/big-data/building-an-aws-glue-etl-pipeline-locally-without-an-aws-account/`.)

4. **Independent community attempts to run Glue against LocalStack converge on the same workaround: avoid the Glue Catalog client, don't try to redirect it.** The `glue-local-runner` project (github.com/wj-su/glue-local-runner) explicitly *removes* `hive-site.xml` "to force Spark to use a local Hive Metastore instead of the AWS Glue Data Catalog" rather than attempting to point the Glue Catalog client at LocalStack. A separate community write-up on LocalStack-for-local-Glue-dev only ever demonstrates `create_dynamic_frame_from_options` with `spark.hadoop.fs.s3a.endpoint` and related S3A keys pointed at LocalStack — it never discusses or claims success with `from_catalog`. (Sources: `github.com/wj-su/glue-local-runner`; `codelovingyogi.medium.com/localstack-for-local-glue-dev-87ab567cff0a`.)

5. **The S3A path, by contrast, has a fully documented, standard override mechanism** — `spark.hadoop.fs.s3a.endpoint`, `spark.hadoop.fs.s3a.access.key`, `spark.hadoop.fs.s3a.secret.key`, `spark.hadoop.fs.s3a.path.style.access=true`, `spark.hadoop.fs.s3a.aws.credentials.provider` — because S3A is a generic open-source Hadoop connector (not an AWS-proprietary Glue component), and this is exactly the mechanism community local-Glue-dev setups rely on for the data-plane side.

**What this means for the template:** the honest, documentable local flow is: `bootstrap.py` (boto3, Catalog) creates the database/table/partition metadata in Floci → the job reads/writes via `from_options` against S3A pointed at Floci → integration tests assert both the S3A output *and* the Catalog/Athena state via boto3, all independently of whether `from_catalog` was ever called. The job script can still demonstrate the `from_catalog` *code path* being written the "real" way, but it should be gated (e.g. `if os.environ.get("AWS_ENDPOINT_URL"): use from_options else use from_catalog`, or simply document that this template's example job intentionally uses `from_options` for portability and shows `from_catalog` only as a commented-out "how you'd do this in real AWS" alternative). This should be called out explicitly and prominently in the README so users don't come away believing the Catalog-driven read path was verified locally when it was not.

**What would fully settle this (currently UNKNOWN):** the source of the proprietary Java/Scala Glue Catalog connector class invoked via `sc._jvm` inside the container image — it is not published, so it cannot be inspected directly. Short of AWS publishing it or documenting an override, this conclusion rests on the convergent absence of any working example anywhere, across AWS's own docs/blog and multiple independent community projects.

---

## Q5 — Local vs. Real AWS Parity Boundary ("Known Differences" table)

| Area | Local (Floci + aws-glue-libs container) | Real AWS Glue | Confidence |
|------|------------------------------------------|----------------|------------|
| Job bookmarks | **Not supported.** AWS's own container docs list "Job bookmarks" under "Considerations" as unsupported when developing locally with this Docker image. | Fully supported, tracks processed files/partitions across runs. | HIGH — official AWS doc, `develop-local-docker-image.html` |
| `StartJobRun` / job orchestration | Does not exist. The job is invoked directly via `spark-submit` inside the container; there is no "Glue job" resource locally, no run ID, no job state machine. | `StartJobRun` creates a managed, serverless Spark run with retries, timeout, worker autoscaling, and a `GetJobRun` status API. | HIGH — Floci's own service table lists Glue support as "Data Catalog, Schema Registry" only; CreateJob/StartJobRun/GetJobRun are absent |
| Crawlers | Do not exist locally. Replaced by the versioned `catalog/bootstrap.py` script (deterministic, explicit) instead of schema inference. | `CreateCrawler`/`StartCrawler` infer schema by scanning data. | HIGH — explicit project decision + confirmed absent from Floci |
| Triggers / workflows | Do not exist locally. | Native Glue orchestration primitives. | HIGH — same basis as above |
| `create_dynamic_frame.from_catalog()` | Not usable against Floci (see Q4 finding above) — must use `from_options` locally. | Fully supported, standard pattern. | MEDIUM-HIGH — absence-of-evidence conclusion, see Q4 |
| `BatchCreatePartition` | Not in Floci's supported-operations list (per this project's own prior research) — bootstrap must loop `CreatePartition` calls. | Both `CreatePartition` and `BatchCreatePartition` supported. | Per project's own PROJECT.md research notes (treated as given/HIGH by this project) |
| Athena queries | Executed via Floci's DuckDB sidecar against S3 + Glue-backed table definitions — real SQL execution, but DuckDB's SQL dialect/engine semantics are not identical to Athena's Trino/Presto engine (e.g., some Presto-specific functions, exact NULL/type-coercion edge cases, and performance characteristics will differ). | Athena runs on a managed Trino/Presto-based engine. | MEDIUM — dialect-level differences are a reasonable/expected inference from DuckDB vs. Trino being different engines, not independently benchmarked here; flag any dialect-specific SQL in template docs |
| IAM enforcement | Not enforced by default. Floci's own docs state credentials "can be any non-empty values unless you explicitly enable stricter service-specific auth checks" (e.g., `FLOCI_SERVICES_S3_ENFORCE_AUTH`, default `false`). | Full IAM policy evaluation; the Glue job's execution role must have explicit permissions on S3/Catalog resources. | HIGH — direct quote from Floci README |
| Credentials / account model | Dummy values (`test`/`test`) resolve to a default fake account ID (`000000000000`) unless a 12-digit `AWS_ACCESS_KEY_ID` is supplied for multi-account isolation testing. | Real IAM principals, real account IDs. | HIGH — Floci README, "Multi-Account Isolation" section |
| Spark/library restrictions inside the container (both local AND when deployed, since it's the same image family used to build the real job's runtime expectations) | AWS Glue Parquet writer, `FillMissingValues`, `FindMatches`, vectorized SIMD CSV reader, `customJdbcDriverS3Path`, Data Quality, Sensitive Data Detection, and Lake Formation credential vending are all listed as unsupported *in the local Docker image specifically* — some of these ARE available when the same job runs as an actual Glue job in AWS. | All of the above are available in the real Glue job runtime. | HIGH — official "Considerations" list, `develop-local-docker-image.html` |
| Region / endpoint resolution | `AWS_ENDPOINT_URL` present, points at `floci:4566`; any `AWS_REGION` value works since Floci doesn't validate regions meaningfully. | `AWS_ENDPOINT_URL` absent; real regional endpoints; region affects service availability/latency. | HIGH — by construction of the config-flow design above |

---

## Q6 — CI Topology (GitHub Actions)

**Recommendation: use `docker compose` inside the workflow (the same `docker-compose.yml` and `run.sh` local developers use), not GitHub Actions' native `services:` container mechanism.**

Reasoning:
- GitHub Actions' `services:` keyword is designed for *sidecar* services reachable by a job running directly on the runner (`localhost:<port>`); it works for a single Floci container fine, but the `glue` container in this template is not a passive sidecar — it's the thing actually executing `run.sh`'s commands, with its own volume mounts, working directory, and env. Modeling that as a second `services:` entry adds no value over just running `docker compose` directly in a step, and would fork the topology definition into two places (workflow YAML and compose YAML) that must be kept in sync — directly working against the project's "one command, one truth" design.
- Compose's `depends_on: condition: service_healthy` already gates the `glue` container on Floci's own baked-in `HEALTHCHECK` (see Pattern 2 above) — GitHub Actions' own `--health-cmd`/`--health-interval`/`--health-retries` `options:` mechanism (confirmed present and documented at `docs.github.com/en/actions/using-containerized-services/creating-postgresql-service-containers`) would be redundant, since it solves the same problem the image's own Dockerfile `HEALTHCHECK` instruction already solves.
- Practical consequence: `ci.yml` should simply `docker compose pull`, then invoke the same `./run.sh` subcommands (`up`, `bootstrap`, `job`, `test`, `lint`, `down`) a local developer would run — this is the strongest possible guarantee that CI failures reproduce locally and vice versa.

**Image size / caching:**
- `public.ecr.aws/glue/aws-glue-libs:5` is ~4.77 GB compressed (per Docker Hub layer metadata for the equivalent `amazon/aws-glue-libs:5.0.0-amd64` tag); AWS's own docs recommend at least 7 GB of free disk for it uncompressed. `floci/floci:1.5.11` is comparatively tiny (~90 MB per the Floci README's stated image size).
- GitHub-hosted `ubuntu-latest` runners report roughly 14–22 GB of usable/free disk depending on which GitHub documentation/benchmark is consulted (no single authoritative number was found; multiple third-party sources converge in this range as of 2026). Either figure comfortably fits both images plus checkout and build artifacts, so disk exhaustion is not expected to be a routine problem for this template, though it's worth keeping an eye on if the sample dataset or Spark's local shuffle/temp usage grows.
- **Do not attempt to cache the Glue base image itself** via `actions/cache`. At ~4.77 GB, a single cache entry would consume roughly half of a GitHub Actions repository's typical cache quota, and the round-trip cost of uploading/downloading a cache blob of that size is unlikely to beat a direct `docker pull` from ECR Public (a high-throughput, geographically distributed registry) — this is a reasoned recommendation, not a benchmarked one; treat it as MEDIUM confidence and validate empirically once the CI phase is built. If pull time turns out to be a real bottleneck in practice, the correct mitigation is pinning to a specific digest (so Docker's local layer cache on self-hosted runners, if ever used, is stable) rather than trying to warm GitHub's ephemeral runner cache.
- Pip/Poetry dependency caches (for lint tooling, boto3, pytest, etc., if any run outside the container) are worth caching via `actions/cache` — they're small and change infrequently, unlike the base image.
- **Expected job duration:** no official benchmark exists for this exact combination; expect the dominant costs to be (a) pulling the ~4.77 GB Glue image, (b) JVM/Spark cold-start inside the container for each `docker compose run` invocation (a few seconds each, non-trivial when multiplied across bootstrap + job + integration tests as separate invocations), and (c) the job itself, which is trivial (CSV → Parquet, tiny sample data). A reasonable target to validate empirically once built: low single-digit minutes total for `pull + up + bootstrap + job + test`. Confidence: MEDIUM (reasoned estimate, not measured).

---

## Q7 — Build Order

The earliest point at which "one command → green" is achievable end-to-end should be treated as the highest-priority milestone, since it is the project's stated core value. Dependencies, in order:

1. **`docker-compose.yml` skeleton** (floci service only, with its baked-in healthcheck wired to `depends_on`) — nothing downstream can be verified without Floci reachable.
2. **`.env.example` + config-flow wiring in `run.sh`** — establishes the single source of truth for endpoint/region/credentials/bucket/database names that every later component reads. Doing this early prevents later components from hardcoding values that then need to be retrofitted.
3. **`catalog/bootstrap.py`** — depends on (1) and (2) only (boto3 + Floci). This is independently verifiable ("does the database/table/partition metadata land in the Catalog?") before any Spark job exists, and is the natural first "green" milestone.
4. **`transforms/csv_to_parquet.py` + `tests/unit/`** — depends on nothing but a Python/PySpark install; can be built and fully green in parallel with (3), since it has no container/Floci dependency at all.
5. **`jobs/csv_to_parquet/job.py`** — depends on (3) (needs a bootstrapped Catalog/bucket to read from/write to) and (4) (imports the pure transform). This is the point where the `glue` service definition in `docker-compose.yml` (Pattern 2) must exist.
6. **Sample data (`data/sample/input.csv`)** — needed before (5) can be run end-to-end; trivial, can be created any time before this point.
7. **`tests/integration/`** — depends on (1)–(6) all existing and working; this is what actually proves "one command, green" for the full local loop (`run.sh up && run.sh bootstrap && run.sh job && run.sh test`).
8. **This is the earliest point at which "one command → green" is fully achievable** — steps 1–7 constitute the minimum closed loop. Terraform (real-AWS provisioning) and GitHub Actions CI are valuable but strictly downstream of this loop already being green locally, since both are designed to reproduce exactly what `run.sh` already does; building them before the local loop is proven would risk encoding an unverified topology into two more places.
9. **Terraform module** — can be developed in parallel with (7)/(8) once the schema (`catalog/schema/*.json`) and variable names from (2) are stable, since it's a separate, non-blocking consumer of the same naming contract.
10. **GitHub Actions workflow** — should be last, precisely because its entire design (Section Q6) is "run the same `run.sh` a local developer runs" — it has nothing to orchestrate until that sequence is proven locally.

**Roadmap implication:** phase 1 of the roadmap should scope exactly steps 1–7 above and no further — that is the smallest phase that delivers the project's stated core value ("clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes"). Terraform and CI are legitimately separate phases that depend on, but do not block, that first phase's success criterion.

## Sources

**HIGH confidence (official docs / primary source code, read directly):**
- AWS Glue Developer Guide — "Develop and test AWS Glue jobs locally using a Docker image": https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html (image tag, run patterns, user `hadoop`, workspace mount path, Job Bookmarks/Considerations list)
- `awsglue/context.py` (master branch, read via raw.githubusercontent.com): https://github.com/awslabs/aws-glue-libs/blob/master/awsglue/context.py (`create_dynamic_frame_from_catalog` delegates to `self._ssql_ctx`, a JVM object; no Python-layer endpoint parameter)
- `awsglue/utils.py` (master branch, read via raw.githubusercontent.com): https://github.com/awslabs/aws-glue-libs/blob/master/awsglue/utils.py (`getResolvedOptions` full implementation — pure `argparse`, no JVM dependency)
- `awsglue/job.py` (master branch): https://github.com/awslabs/aws-glue-libs/blob/master/awsglue/job.py (confirms `Job.job_bookmark_options()`/`id_params()`/etc. are pure classmethods returning static lists; only `Job.__init__` touches the JVM)
- floci-io/floci README (main branch, read via raw.githubusercontent.com): https://github.com/floci-io/floci (image name/tags, `/_localstack/health` + `/_localstack/init` compatibility, `FLOCI_HOSTNAME` multi-container guidance, Glue/Athena service-coverage table, credential model, multi-account isolation)
- floci-io/floci `docker/Dockerfile.native` (main branch): https://github.com/floci-io/floci/blob/main/docker/Dockerfile.native (confirms `HEALTHCHECK` is baked into the image itself via `/dev/tcp` against `/_floci/health`; base image `quay.io/quarkus/quarkus-micro-image:2.0`; no Docker-socket dependency for in-process services)
- floci-io/floci `docker/Dockerfile.compat`: https://github.com/floci-io/floci/blob/main/docker/Dockerfile.compat (confirms `latest-compat` tag adds Python3/boto3/awscli on top of the base image)
- Docker Compose docs — startup order / `depends_on: condition: service_healthy`: https://docs.docker.com/compose/how-tos/startup-order/
- Docker Compose docs — `profiles:`: https://docs.docker.com/compose/how-tos/profiles/
- GitHub Actions docs — service containers overview: https://docs.github.com/en/actions/using-containerized-services/about-service-containers
- GitHub Actions docs — PostgreSQL service container health-check example: https://docs.github.com/en/actions/using-containerized-services/creating-postgresql-service-containers

**MEDIUM confidence (secondary/community sources, used to corroborate the Q4 finding and CI sizing, no single authoritative statement found):**
- AWS Big Data Blog — "Building an AWS Glue ETL pipeline locally without an AWS account": https://aws.amazon.com/blogs/big-data/building-an-aws-glue-etl-pipeline-locally-without-an-aws-account/
- `wj-su/glue-local-runner` (GitHub): https://github.com/wj-su/glue-local-runner
- "LocalStack for local Glue dev" (Medium): https://codelovingyogi.medium.com/localstack-for-local-glue-dev-87ab567cff0a
- Docker Hub layer metadata for `amazon/aws-glue-libs:5.0.0-amd64` (image size ~4.77 GB compressed): https://hub.docker.com/layers/amazon/aws-glue-libs/5.0.0-amd64/images/sha256-fa89a11ddbfc54b9ca6ca808af8c5d2a3d792e2390d3374a7b0a91514ec72704
- GitHub-hosted runner disk-space figures — multiple third-party sources converge in the 14–22 GB range but no single canonical GitHub doc was located giving one authoritative figure as of this research; treat as directional only

**UNKNOWN (explicitly, per research discipline):**
- The exact behavior/configuration surface of the proprietary Java/Scala Glue Data Catalog connector invoked via `sc._jvm` inside `aws-glue-libs:5` — not published as source, so the Q4 conclusion rests on absence-of-evidence across all available primary and secondary sources rather than direct inspection. Would be settled by AWS publishing that connector's source or explicitly documenting (or explicitly denying) an endpoint-override mechanism.
- Exact GitHub Actions job duration for this specific pull+run+test sequence — no benchmark found; flagged as something to measure empirically once the CI phase is implemented.

---
*Architecture research for: AWS Glue 5.0 ETL template (Docker + Floci local emulation)*
*Researched: 2026-08-06*
