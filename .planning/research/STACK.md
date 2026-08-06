# Stack Research

**Domain:** Containerized AWS Glue 5.0 ETL template, developed entirely in Docker, with local AWS emulation via Floci
**Researched:** 2026-08-06
**Confidence:** MEDIUM-HIGH overall — HIGH on the AWS Glue container and Terraform facts (first-party docs), MEDIUM on Floci specifics (young project, docs are the only source), **LOW/UNKNOWN and explicitly flagged** on GlueContext-catalog-endpoint override (this is a real, load-bearing architectural limitation, not a gap in research effort)

> **Note on confidence tagging.** The research-plan tool's `classify-confidence` seam only recognizes a small fixed set of provider IDs (`websearch`→MEDIUM, `context7`→MEDIUM, unrecognized IDs incl. `webfetch`/`curated`/`official-docs`→LOW by default in this environment). Where a claim below was fetched directly from a first-party primary source (`docs.aws.amazon.com`, `registry.terraform.io`, `github.com/awslabs/*`, `github.com/aws-samples/*`, `github.com/hashicorp/*`, `floci.io` official docs, `pypi.org`), I mark it **HIGH** based on the source hierarchy principle (first-party docs outrank the tool-level default) and say so explicitly. Everything sourced from blog posts, unresolved GitHub issues, or Medium articles is marked **MEDIUM** or **LOW** and called out as such.

---

## 1. AWS Glue 5.0 Docker image

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `public.ecr.aws/glue/aws-glue-libs:5` | Glue 5.0 | Base image for the job container | This is the **only** first-party image for Glue 5.0. AWS moved Glue 5.0 images to ECR Public; Docker Hub's `amazon/aws-glue-libs` tops out at Glue 4.0 (`glue_libs_4.0.0_image_01`). Confirmed on `docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html`. **Confidence: HIGH.** |
| Apache Spark | 3.5.4 (`3.5.4-amzn-0`) | Distributed compute | Bundled, not swappable. Confirmed via image contents list and REPL banner in AWS's own doc. **HIGH.** |
| Python | 3.11.6 | Job + tooling runtime | Bundled. Confirmed via REPL banner (`Python 3.11.6 (main, Jan 9 2025...)`) in AWS's local-dev doc. **HIGH.** Patch version may have moved since; treat 3.11.x as the contract, not 3.11.6 exactly. |
| Base OS | Amazon Linux 2023 | Container OS | Documented. **HIGH.** |

### What's preinstalled

Per `docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html` (**HIGH**, official AWS docs):
- Amazon Linux 2023, AWS Glue ETL Library, Apache Spark 3.5.4
- Apache Iceberg 1.7.1, Apache Hudi 0.15.0, Delta Lake 3.3.0 — **all three preloaded by default in Glue 5.0**; the `DATALAKE_FORMATS` env var used in Glue ≤4.0 is gone and unnecessary
- AWS Glue Data Catalog Client
- Amazon Redshift connector for Spark, Amazon DynamoDB connector for Hadoop
- `pytest` (observed as `pytest-8.3.4` / `pluggy-1.5.0` in AWS's own sample output — treat as a floor, not a pin)
- **Removed vs Glue 4.0:** JupyterLab and Livy are no longer bundled. If you want a notebook UI, you build a custom child image (AWS's own blog post builds one named `glue_v5_livy` on top of the base image — **not** something the base image gives you for free).

### The `docker run` invocations AWS documents

Container **user is `hadoop`** (non-root). This is new in Glue 5.0 — Glue 4.0's default user was `glue_user`. Job scripts are expected under `/home/hadoop/workspace/` (mounted from host), scripts specifically under `/home/hadoop/workspace/src/`.

**No `DISABLE_SSL` or `AWS_REGION` env var is used anywhere in AWS's official local-dev flow.** I searched the official doc and the companion AWS Big Data Blog post for Glue 5.0 specifically and neither uses these variables. Only `AWS_PROFILE` is set, to select a named profile from the mounted `~/.aws`. **Treat the premise of these two env vars being Glue-container-level knobs as false** — `DISABLE_SSL`/`AWS_REGION` are LocalStack-era client-side conventions; for this stack the equivalent controls are Hadoop S3A Spark-conf keys (see §3) and boto3's own env vars (`AWS_DEFAULT_REGION`), not anything the Glue image itself reads. **Confidence: HIGH** that AWS's documented flow doesn't use them; can't rule out they're silently read by some undocumented internal script, but nothing in official docs supports that.

```bash
# spark-submit
docker run -it --rm \
    -v ~/.aws:/home/hadoop/.aws \
    -v $WORKSPACE_LOCATION:/home/hadoop/workspace/ \
    -e AWS_PROFILE=$PROFILE_NAME \
    --name glue5_spark_submit \
    public.ecr.aws/glue/aws-glue-libs:5 \
    spark-submit /home/hadoop/workspace/src/$SCRIPT_FILE_NAME

# pyspark REPL
docker run -it --rm \
    -v ~/.aws:/home/hadoop/.aws \
    -e AWS_PROFILE=$PROFILE_NAME \
    --name glue5_pyspark \
    public.ecr.aws/glue/aws-glue-libs:5 \
    pyspark

# pytest (note: entrypoint takes "-c '<shell command>'", not a bare command)
docker run -i --rm \
    -v ~/.aws:/home/hadoop/.aws \
    -v $WORKSPACE_LOCATION:/home/hadoop/workspace/ \
    --workdir /home/hadoop/workspace \
    -e AWS_PROFILE=$PROFILE_NAME \
    --name glue5_pytest \
    public.ecr.aws/glue/aws-glue-libs:5 \
    -c "python3 -m pytest --disable-warnings"

# Spark History Server (port 18080) — from AWS's Glue 5.0 blog post appendix
docker run --rm -it -p 18080:18080 public.ecr.aws/glue/aws-glue-libs:5 \
    -c "/usr/lib/spark/sbin/start-history-server.sh && spark-submit sample.py"
```

Spark UI: standard Spark default port **4040** applies for any interactively-running Spark driver (not Glue-specific, not called out separately in AWS's doc — publish it with `-p 4040:4040` if you want to reach it from the host).

Jupyter/Livy (ports 8888/8998) require building a **custom image** on top of the base — the official blog's example uses a self-built tag (`glue_v5_livy`), it is not something `public.ecr.aws/glue/aws-glue-libs:5` provides directly. **For this template, skip Jupyter entirely** — it adds a second Dockerfile and contradicts "single entrypoint, minimal template."

Adding JDBC/extra JARs: mount a host directory to `/opt/spark/jars/` — anything there is auto-added to the Spark classpath.

**Not supported when running the container locally** (documented restrictions, relevant because a "table stakes" job feature request could otherwise silently misbehave): job bookmarks, the AWS Glue Parquet writer, `FillMissingValues`/`FindMatches` transforms, the vectorized SIMD CSV reader, `customJdbcDriverS3Path`, AWS Glue Data Quality, Sensitive Data Detection, Lake Formation credential vending.

**Sources:** `docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html` (HIGH), `aws.amazon.com/blogs/big-data/develop-and-test-aws-glue-5-0-jobs-locally-using-a-docker-container/` (HIGH — official AWS blog).

---

## 2. Floci

### Core facts

| Item | Value | Confidence |
|------|-------|------------|
| Docker Hub image | `floci/floci` | HIGH (official docs) |
| Standard tags | `latest`, `x.y.z` (e.g. `1.5.11`), `nightly`, `nightly-mmddyyyy` | HIGH |
| Compat tags | Same set with `-compat` suffix: `latest-compat`, `1.5.11-compat`, `nightly-compat`, `nightly-mmddyyyy-compat` | HIGH |
| Architectures | multi-arch manifest, `linux/amd64` + `linux/arm64`, auto-selected | HIGH |

**`latest` vs `latest-compat`:** the standard image ships the Floci native binary only. `-compat` layers **Python 3 + AWS CLI + boto3** on top, with identical startup time (~24ms) and memory footprint (~13MiB) — only image size differs. **Use `-compat` only if your init scripts (mounted into `/etc/floci/init/...`) themselves need `aws`/`boto3` to run.** For this template, the bootstrap script that populates the Data Catalog runs from the **application container** (or CI runner) via boto3 against Floci's exposed port, not as a Floci init script — so the plain `floci/floci:1.5.11` (non-compat, version-pinned) is the right choice, not `latest-compat`. Pin the version tag, not `latest`, since Floci is a young, fast-moving 2026 project and unpinned `latest` breaks reproducibility guarantees the template promises.

### Environment variables

Both image variants preset (baked in, not required to set yourself, but override-able):
```
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_CONFIG_FILE=/etc/floci/aws/config
```
`-compat` additionally sets `AWS_ENDPOINT_URL=http://localhost:4566`.

Configuration knobs (native Floci names — these are what you actually set in `docker-compose.yml`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLOCI_PORT` | `4566` | API port |
| `FLOCI_HOSTNAME` | unset | Hostname embedded in returned resource URLs when run inside Compose — set this to the service name (e.g. `floci`) so URLs returned to the Glue container resolve correctly on the Docker network |
| `FLOCI_STORAGE_MODE` | `memory` | `memory` \| `persistent` \| `hybrid` \| `wal` — use `memory` for CI (fast, disposable), consider `persistent` for local dev if you want state across restarts |
| `FLOCI_STORAGE_PERSISTENT_PATH` | `./data` | Where persisted state is written when `FLOCI_STORAGE_MODE=persistent` |

LocalStack env-var compatibility layer (Floci auto-translates these if you're porting an existing LocalStack compose file): `LOCALSTACK_HOST`/`LOCALSTACK_HOSTNAME`→`FLOCI_HOSTNAME`, `PERSISTENCE=1`/`PERSIST_STATE=1`→`FLOCI_STORAGE_MODE=persistent`, `EDGE_PORT`→`FLOCI_PORT`, `GATEWAY_LISTEN`→`QUARKUS_HTTP_HOST`, `LS_LOG`/`DEBUG=1`→`QUARKUS_LOG_LEVEL`, `DOCKER_HOST`→`FLOCI_DOCKER_DOCKER_HOST`, `USE_SSL=1`→`FLOCI_TLS_ENABLED=true`. `SERVICES=` is not needed at all — Floci starts all 69 services instantly, no selective enabling. Not directly relevant to a greenfield template (write native `FLOCI_*` vars, don't carry over LocalStack names), but useful if a contributor pastes in an old LocalStack compose snippet by habit.

**Source:** `floci.io/floci/configuration/docker-images/`, `github.com/floci-io/floci/blob/main/README.md`, `floci.io/floci/getting-started/migrate-from-localstack/` — all official Floci docs, **HIGH** confidence on content-as-documented; **MEDIUM** on completeness since this is the entirety of what the docs site currently states, and the project is young enough that undocumented behavior may exist.

### Init scripts

Two directory trees are recognized, Floci-native takes priority:
```
/etc/floci/init/{boot,start,ready,stop}.d          # native, priority
/etc/localstack/init/{boot,start,ready,shutdown}.d # LocalStack-compat, fallback
```
Only `.sh` (shell) and `.py` (python3, requires `-compat` image) are executed; other extensions are ignored. Within a stage, scripts run **sequentially, in lexicographical order**. Stages, in order: `boot` (before services start, no AWS APIs available yet) → `start` (after HTTP server is up, APIs available) → `ready` (after all `start` scripts finish) → `stop` (during shutdown).

```yaml
volumes:
  - ./init/boot.d:/etc/floci/init/boot.d:ro
  - ./init/start.d:/etc/floci/init/start.d:ro
  - ./init/ready.d:/etc/floci/init/ready.d:ro
  - ./init/stop.d:/etc/floci/init/stop.d:ro
```
For this template, the boto3 Data Catalog bootstrap script should probably run as a `run.sh` step from **outside** the container against the published port, rather than as a Floci init script — keeps it in one Python codebase with the tests instead of splitting logic between `/etc/floci/init/` shell/py files and the app repo. Use init scripts only if you need catalog state present before the very first API call reaches Floci.

### Health / readiness endpoint

Floci serves the LocalStack-compatible paths **`GET /_localstack/init`** and **`GET /_localstack/health`** unchanged — confirmed in the official migration doc, which explicitly states existing LocalStack CI/scripts polling these paths need no changes. A native `/_floci/init` alias is referenced in secondary sources (DeepWiki-generated summary) but I could not independently confirm it against the primary floci.io docs, so treat that path as **MEDIUM confidence / possible**, and `/_localstack/health` as the safe, **HIGH confidence** one to poll.

**Recommended `run.sh`/CI readiness check** (LocalStack-compatible healthcheck pattern, since Floci explicitly preserves it):
```bash
until curl -sf http://localhost:4566/_localstack/health > /dev/null; do
  sleep 1
done
```
The docs additionally note Floci's own startup log ends with a LocalStack-style `Ready.` line, usable as a log-grep fallback if you'd rather not depend on curl in a minimal image. No documented JSON schema for the health response body was found — poll for HTTP 200, don't parse the body.

**Gap:** Floci's docs do not publish a `HEALTHCHECK` block in their own docker-compose examples (checked `floci.io/floci/configuration/docker-compose/` directly — three example compose files shown, none include one). You'll need to author your own `healthcheck:` stanza in the template's `docker-compose.yml` using the curl loop above.

---

## 3. Pointing Spark/Hadoop S3A at Floci

### Required `spark.hadoop.fs.s3a.*` keys

```python
spark = (
    SparkSession.builder
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.endpoint", "http://floci:4566")       # or http://localhost:4566 outside compose network
    .config("spark.hadoop.fs.s3a.endpoint.region", "us-east-1")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.access.key", "test")
    .config("spark.hadoop.fs.s3a.secret.key", "test")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .getOrCreate()
)
```

**Why each key matters (this is the part that bites people):**
- `path.style.access=true` — required because Floci (like LocalStack) doesn't do virtual-hosted-style bucket DNS resolution; without this, requests 404/fail DNS resolution.
- `connection.ssl.enabled=false` — Floci serves plain HTTP on 4566, not HTTPS; this is the practical answer to the "`DISABLE_SSL`" part of the original question — there's no such Glue/Floci env var, this Spark-conf key is the actual mechanism.
- `aws.credentials.provider=SimpleAWSCredentialsProvider` — **this is the single most common failure mode** found in research: an unresolved AWS `aws-glue-libs` GitHub issue (#112) shows exactly this symptom — a user configured endpoint/path-style/SSL correctly but still got `403 Forbidden`/`AccessDeniedException` against a local S3-compatible store because Hadoop's **default** S3A credential provider chain tries the EC2/ECS instance-metadata and env-var chains first and can silently pick up the wrong (or no) credentials before falling through to static ones. Force it to `SimpleAWSCredentialsProvider` explicitly.
- `endpoint.region=us-east-1` — recent `hadoop-aws` versions do SigV4 region validation and can fail/warn without an explicit region even for a fake endpoint; match it to Floci's default (`AWS_DEFAULT_REGION=us-east-1`).

### `s3://` vs `s3a://`

**Use `s3a://` exclusively.** I could not find a single authoritative AWS statement that plain `s3://` is unsupported in the `aws-glue-libs:5` image, but the circumstantial evidence is consistent and one-directional: every working local-Glue-against-emulator example found (community blog posts, the unresolved MinIO GitHub issue, generic PySpark-against-LocalStack guides) configures and uses `s3a://` paths exclusively — none demonstrate `s3://` working against a non-AWS endpoint. In real AWS-hosted Glue, `s3://` is transparently bound to the S3A implementation by Glue's own runtime wiring; that wiring is tuned for the real S3 service endpoint and is not something you should rely on redirecting. **Confidence: MEDIUM** (community consensus, not an AWS doc statement) — but the cost of being wrong is zero: standardize all template code (job script, bootstrap script's `s3a://` references, test fixtures) on `s3a://` and the ambiguity is moot.

**Source confidence:** the exact key list is **MEDIUM** — assembled from a Nov-2025 practitioner blog (`awongcm.io`) plus a cross-check against a real (if unresolved) AWS GitHub issue showing the failure mode when `aws.credentials.provider` is omitted. No AWS or Floci first-party doc publishes a canonical S3A-against-Floci config block — this is a genuine gap; the config above is the community-standard Hadoop-S3A-against-S3-compatible-endpoint recipe, not something floci.io or AWS specifically validated for this exact pairing.

---

## 4. Glue Data Catalog against Floci — load-bearing limitation, stated plainly

**Short answer: `GlueContext.create_dynamic_frame.from_catalog()` (and any other GlueContext catalog-resolution method) cannot be pointed at Floci or any non-AWS endpoint. Catalog access for local development must go through boto3 with `endpoint_url`, not through GlueContext.**

Here is the evidence trail, because this is exactly the kind of claim that should not be taken on faith:

1. `GlueContext`'s Python layer (`awsglue/context.py`, open source at `github.com/awslabs/aws-glue-libs`) delegates catalog calls to `self._ssql_ctx.getCatalogSource(...)` — a **JVM** call. The JVM-side implementation (the actual `com.amazonaws.services.glue.*` client) is compiled into the Glue ETL library JAR bundled in the container image and is **not** open source — it can't be inspected directly. **HIGH confidence this delegation happens** (read directly from the open-source Python source); **cannot verify** what's inside the JVM client because it's closed.
2. The package naming (`com.amazonaws.services.glue.AWSGlueClient`, confirmed via the AWS Java SDK javadoc URL structure) indicates this is an **AWS SDK for Java v1**-style client, not v2.
3. AWS SDK for Java **v1 does not support environment-variable or config-file endpoint overrides at all** (confirmed via `github.com/aws/aws-sdk-java` maintainer discussion/issue threads — v1 never got this feature before AWS announced its end-of-support). The generic `AWS_ENDPOINT_URL_<SERVICE>` mechanism (which boto3 and AWS CLI v2 do honor) is a v2-only, and even in v2 was only added for Java in SDK version **2.28.1** — long after Glue's bundled client was built against v1 conventions.
4. I checked the one open-source library that *does* let you redirect Glue-Catalog-as-Hive-metastore traffic — `awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore` (config key `hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory`, invoked via `spark.hadoop.hive.metastore.client.factory.class` in Spark). **This is a genuinely different code path from `GlueContext.create_dynamic_frame.from_catalog`** — it's for Spark SQL treating Glue Catalog as a Hive metastore, not for DynamicFrames — and its own README documents **no endpoint-override property either** (only caching knobs: `aws.glue.cache.{table,db}.{enable,size,ttl-mins}`).
5. LocalStack's own Glue documentation (`docs.localstack.cloud/aws/services/glue/`) — the one vendor whose Glue Pro tier genuinely runs real `StartJobRun`-triggered containers against its own catalog — does **not** publish the internal env var/JVM-property wiring it uses to make that work. It's closed-source, undocumented plumbing specific to LocalStack Pro's job-runner, not something transferable to a self-run `aws-glue-libs` container.
6. A relevant open GitHub issue (`awslabs/aws-glue-libs#59`, "Interact with s3 / catalog offline?") asks this exact question — whether MinIO-style catalog emulation is possible — and **has no maintainer response**. This is corroborating, not conclusive, evidence: the community doesn't have an answer either.

**Conclusion (MEDIUM-HIGH confidence — this is an absence-of-evidence conclusion, not a directly documented "this is impossible" statement from AWS):** treat GlueContext-catalog-against-Floci as **not possible** for this template. This is, reassuringly, exactly what the project's locked decisions already assume — the bootstrap script populates the catalog via boto3 (which supports `endpoint_url` cleanly, since boto3 is a modern SDK with full endpoint-override support), and the example job is a direct CSV→Parquet transform that doesn't need catalog resolution at runtime at all.

**Architectural rule for the template:** the Glue job script should read/write via explicit `s3a://` paths (`spark.read.csv(...)`, `df.write.parquet(...)`, or `DynamicFrame.from_options`/`glueContext.write_dynamic_frame.from_options` with explicit `connection_options={"path": "s3a://..."}`) — **never** `from_catalog`/`write_dynamic_frame.from_catalog`. Any place the template needs to *read* catalog metadata (e.g. an integration test asserting the bootstrap script registered the right table), use `boto3.client("glue", endpoint_url="http://localhost:4566")` directly. This constraint should be called out explicitly in the roadmap/example-job phase so nobody "helpfully" adds `from_catalog()` usage later and silently breaks local dev.

---

## 5. Python tooling

### Supporting Libraries / Dev Tools

| Tool | Version | Purpose | Why / Notes |
|------|---------|---------|-------------|
| `uv` | 0.12.2 (PyPI, confirmed 2026-08-05) | Dependency resolution + install into the fixed container Python | The container already fixes the Python runtime (3.11.6) — you don't need `uv`'s Python-version-management feature (`uv python pin`/install), just its fast resolver + lockfile (`uv.lock`, commit it) for reproducible `uv sync --frozen` / `uv pip install` runs both in Docker builds and CI. Rejecting Poetry: Poetry's resolver is materially slower and its Docker story (export plugin, virtualenv-in-container friction) is worse for a "single container, no local venv" template. Rejecting pip-tools/plain requirements.txt: no built-in lockfile-with-hashes workflow as clean as `uv.lock`, more moving parts for a template meant to be easy to fork. **Confidence: MEDIUM** (uv's overall 2026 dominance is well-attested across multiple sources; the specific "don't use uv's Python-management feature since the container already pins Python" framing is my synthesis, not a quoted recommendation). |
| `ruff` | 0.16.1 (PyPI, confirmed 2026-07-30) | Lint + format (replaces flake8+isort+black) | Single Rust binary, no separate formatter needed (`ruff format` replaces black). Config lives in `[tool.ruff]` in `pyproject.toml`: set `target-version = "py311"` to match the container, pick a rule baseline (`E,F,W,I,UP,C4,SIM,PTH` is the commonly recommended modern starting set), configure `ruff format` quote-style/line-length to match. **Confidence: MEDIUM-HIGH** (version confirmed on PyPI directly = HIGH; specific rule-set recommendation is a common community baseline, not a single canonical source = MEDIUM). |
| `pytest` | ships in image (8.3.4 observed; pin your own in `pyproject.toml` regardless) | Test runner | Already present in `aws-glue-libs:5` (confirmed via AWS's own doc's sample pytest output). Pin it explicitly in your dependency file anyway so `uv sync` outside the container (e.g. for editor tooling) matches. |
| `pytest-cov` | latest | Coverage reporting | Standard addition; no Glue-specific concern. |

### What NOT to use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Poetry | Slower resolver; Docker/venv story adds friction against a "one container, no separate venv" template; PEP 621 support historically lagged uv | `uv` |
| pip-tools / plain `requirements.txt` | No integrated lockfile-with-hashes + install-into-fixed-env workflow as tight as `uv sync --frozen` | `uv` |
| Managing the container's Python version via `uv python install` | Pointless — the base image already fixes Python 3.11.6; re-managing it inside the container adds a second source of truth for the interpreter version | Rely on the container's bundled interpreter; use `uv` only for dependency resolution/install |

---

## 6. Test tooling for PySpark / GlueContext

### The pattern (from AWS's own sample repo — `github.com/aws-samples/aws-glue-jobs-unit-testing`, **HIGH confidence**, first-party AWS sample):

```python
# tests/conftest.py
from pyspark import SparkContext
from awsglue.context import GlueContext
import pytest

@pytest.fixture(scope="session")
def glueContext():
    spark_context = SparkContext()
    glueContext = GlueContext(spark_context)
    yield glueContext
    spark_context.stop()
```

- **Scope: `session`.** AWS's own sample uses session scope — one Spark/Glue context for the whole test run, not per-test. This is the right default for a template: Spark context startup is expensive (~seconds), and tests should be transformation-logic tests, not context-lifecycle tests. Use function/module scope only for the rare test that needs an isolated context (e.g. testing catalog-connection setup itself).
- For the Floci-integration test path specifically, extend this fixture to add the S3A config from §3 when constructing the `SparkContext`/`SparkConf`, and separately expose a `boto3` Glue/S3 client fixture pointed at `endpoint_url="http://localhost:4566"` for catalog/bucket assertions — do not try to route those through `GlueContext` per §4.

### chispa vs pytest-spark vs hand-rolled

| Library | Version | Verdict for this template |
|---------|---------|---------------------------|
| `chispa` | 0.12.0 (PyPI, confirmed 2026-03-24 release) | **Worth adding** as a dev dependency for DataFrame-equality assertions with readable diff output (`assert_df_equality`). Requires Python ≥3.10,<4.0 — compatible with the container's 3.11. Low-risk, small, single-purpose. |
| `pytest-spark` | last observed release 0.5.0 (older, low-activity project per search results) | **Skip.** It mainly auto-injects `spark_context`/`spark_session` fixtures via config, which conflicts with wanting an explicit, template-owned `conftest.py` fixture that also wires in Floci's S3A config and matches the exact `GlueContext` construction AWS's own sample uses. Adding a plugin to do less than a 10-line fixture already does is unnecessary surface area for a template meant to be forked and understood quickly. |
| Hand-rolled `conftest.py` (as above) | n/a | **Primary recommendation.** Matches AWS's own official sample pattern exactly, keeps the template's test setup fully readable/auditable in one file, and avoids a dependency whose main job is fixture injection you're writing yourself anyway. |

**Confidence:** HIGH on the AWS sample fixture pattern (first-party AWS sample repo, code read directly); MEDIUM on the chispa/pytest-spark recommendation (chispa version verified on PyPI directly = HIGH for that fact; the "skip pytest-spark" judgment is my synthesis from its comparatively low visible activity, not a documented deprecation).

---

## 7. Terraform for Glue 5.0

### Core Technologies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `hashicorp/aws` provider | `~> 6.0` (latest observed: **6.58.0**, released 2026-08-05) | Provisions Glue job, IAM, S3, Data Catalog | Confirmed current on GitHub releases (`github.com/hashicorp/terraform-provider-aws/releases`). **HIGH.** |

### `aws_glue_job` for Glue 5.0

```hcl
resource "aws_glue_job" "etl" {
  name         = "template-etl-job"
  role_arn     = aws_iam_role.glue.arn
  glue_version = "5.0"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/jobs/etl_job.py"
    python_version  = "3.11"
  }

  number_of_workers = 2
  worker_type       = "G.1X"

  default_arguments = {
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-metrics"                   = ""
  }
}
```

**Important version gotcha (why the provider version floor matters):** `python_version = "3.11"` for `glue_version = "5.0"` jobs was **not accepted by the provider until it was added as an enhancement**, tracked in `hashicorp/terraform-provider-aws#41213` (opened 2025-02-03, shipped in milestone **v5.92.0**). Before that fix, the provider only validated `python_version` values of `2`, `3` (meaning 3.6), and `3.9` — meaning older provider versions would reject a valid Glue 5.0 job definition. **Pin `~> 6.0` (or at minimum `>= 5.92.0`) explicitly** in `required_providers` — this is a real, previously-broken case, not theoretical. **Confidence: HIGH** (read directly from the GitHub issue and its linked PR/milestone).

Use `number_of_workers`/`worker_type` (not the legacy `max_capacity`) for standard `glueetl` Spark jobs — `max_capacity` is the older, deprecated-for-Spark-jobs capacity model.

### Required IAM role/policy

```hcl
resource "aws_iam_role" "glue" {
  name = "template-etl-glue-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}
```

`AWSGlueServiceRole` (AWS-managed policy, ARN above — confirmed via `docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSGlueServiceRole.html`, **HIGH**) covers baseline EC2/CloudWatch Logs access Glue needs to run. It does **not** cover your specific S3 buckets — attach a scoped inline/customer-managed policy for the job's actual data buckets: `s3:ListBucket`+`s3:GetObject` on source paths, `s3:ListBucket`+`s3:PutObject`(+`s3:DeleteObject` if overwriting) on target paths, plus the script/temp-dir bucket.

### What changed for Glue 5.0 vs 4.0 in the provider

- `glue_version = "5.0"` accepted as a value (was previously only up to `"4.0"`).
- `python_version = "3.11"` accepted for Spark jobs — **required a provider bump** to work (see gotcha above); this is the one concrete, sourced "what changed" fact found. I did not find a comprehensive first-party "Terraform provider Glue 4.0→5.0 changelog" — beyond the `python_version` validation fix, no other Glue-5.0-specific provider schema changes were surfaced by research. Treat "nothing else changed" as **UNKNOWN rather than confirmed** — it's an absence of findings, not a confirmed absence of changes.

---

## Installation

```bash
# Python deps (inside the aws-glue-libs container, or matching venv for editor tooling)
uv sync --frozen

# Dev-only extras
uv add --dev ruff chispa pytest pytest-cov

# Terraform provider pin (versions.tf)
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| `uv` | Poetry | If the team already standardized on Poetry across other (non-templated) services and consistency outweighs the Docker-build speed/lockfile-cleanliness gains |
| Hand-rolled pytest fixtures | `pytest-spark` | If the project grows beyond a template into a larger multi-job repo where centralizing Spark-session config via plugin config (`pytest.ini` markers) starts paying off over an explicit fixture file |
| `s3a://` scheme everywhere | `s3://` | Only once (if ever) AWS explicitly documents `s3://` working against a non-AWS endpoint in `aws-glue-libs`; no such documentation currently exists |
| boto3 for all catalog access | `GlueContext.create_dynamic_frame.from_catalog` | Only against real AWS (CI/CD deploy validation against a real account, or the Terraform-provisioned environment) — never against Floci |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `amazon/aws-glue-libs` (Docker Hub) for anything beyond Glue 4.0 | Docker Hub tags stop at `glue_libs_4.0.0_image_01`; Glue 5.0 only exists on ECR Public | `public.ecr.aws/glue/aws-glue-libs:5` |
| `GlueContext.create_dynamic_frame.from_catalog()` / any GlueContext catalog method, in local dev | No documented or discoverable way to redirect its closed-source JVM client to Floci (§4) — it will try to reach real AWS Glue and fail/hang without real credentials | `boto3.client("glue", endpoint_url=...)` for catalog ops; explicit `s3a://` paths for job data I/O |
| Default Hadoop S3A credential provider chain (i.e. omitting `fs.s3a.aws.credentials.provider`) | Silently tries instance-metadata/env chains before static credentials; documented failure mode (403/AccessDenied) in a real unresolved `aws-glue-libs` GitHub issue against a local S3-compatible store | Explicit `SimpleAWSCredentialsProvider` |
| `floci/floci:latest` pinned in CI/template defaults | Floci is a fast-moving, ~1-year-old 2026 project; `latest` breaks the "clone and it just works, forever" promise of a template | Pin an exact version tag (e.g. `floci/floci:1.5.11`), bump deliberately |
| Building/relying on JupyterLab or Livy inside `aws-glue-libs:5` | Removed from the base image in Glue 5.0; requires a second custom Dockerfile to get back | Skip notebooks entirely for this template; use `spark-submit`/`pytest` invocations |

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| `public.ecr.aws/glue/aws-glue-libs:5` | Python 3.11.x, Spark 3.5.4, `pytest` ≥8.3.4 (bundled) | Don't try to swap Spark/Python versions inside this image — they're the product being tested against |
| `terraform-provider-aws` | `>= 5.92.0` required for `python_version = "3.11"` on `glue_version = "5.0"` jobs; recommend `~> 6.0` | Below 5.92.0, valid Glue 5.0 HCL is rejected by provider-side validation |
| `chispa` 0.12.0 | Python `>=3.10,<4.0` | Compatible with container's 3.11.6 |
| `floci/floci` any tag | S3 (58 ops, REST XML), Glue (38 ops, JSON 1.1 — Data Catalog + Schema Registry only, no Jobs/Crawlers), Athena (4 ops, DuckDB-backed) | `BatchCreatePartition` is **not** in Floci's supported Glue op list — use `CreatePartition` in a loop if the bootstrap script needs to register many partitions |

## Sources

- `docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html` — Glue 5.0 image contents, docker run commands, user/workdir, restrictions. **HIGH** (first-party AWS docs).
- `aws.amazon.com/blogs/big-data/develop-and-test-aws-glue-5-0-jobs-locally-using-a-docker-container/` — Spark History Server, Jupyter/Livy custom-image caveat. **HIGH** (first-party AWS blog).
- `github.com/awslabs/aws-glue-libs` (`awsglue/context.py`, issues #59/#112) — GlueContext internals, unresolved catalog/S3A-credential issues. **HIGH** for code read directly; **informational/unresolved** for the linked issues.
- `github.com/aws-samples/aws-glue-jobs-unit-testing` (`tests/conftest.py`) — canonical AWS-authored pytest fixture pattern. **HIGH** (first-party AWS sample).
- `github.com/aws/aws-sdk-java` discussions/issues — SDK v1 endpoint-override limitation. **MEDIUM-HIGH** (maintainer-adjacent GitHub discussion, not a formal doc page).
- `github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore` — confirms no endpoint-override config property exists in this related-but-distinct library. **HIGH** (README read directly).
- `docs.localstack.cloud/aws/services/glue/` — confirms LocalStack's own Glue-catalog wiring is undocumented/closed. **MEDIUM** (official LocalStack docs, but the specific claim is an absence of documentation, not a positive statement).
- `floci.io/floci/configuration/docker-images/`, `.../getting-started/migrate-from-localstack/`, `.../configuration/initialization-hooks/`, `.../configuration/docker-compose/`, `.../floci/services/`, `.../floci/services/glue/` — all official Floci docs. **HIGH** for content as documented; **MEDIUM** on completeness (young project, docs may lag reality).
- `github.com/floci-io/floci/blob/main/README.md` — image variants, env vars. **HIGH** (first-party README).
- `registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/glue_job`, `github.com/hashicorp/terraform-provider-aws/releases`, `github.com/hashicorp/terraform-provider-aws/issues/41213` — provider version, `aws_glue_job` schema, Glue 5.0 `python_version` fix. **HIGH** (first-party HashiCorp sources).
- `docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSGlueServiceRole.html` — managed policy ARN/scope. **HIGH**.
- `pypi.org/project/ruff/`, `pypi.org/project/uv/`, `pypi.org/project/chispa/` — current version numbers, checked directly. **HIGH**.
- `www.awongcm.io/blog/2025/11/22/setting-up-local-aws-glue-development-environment-with-docker/` — S3A config-key recipe for Glue+LocalStack. **MEDIUM** (practitioner blog, Nov 2025, not first-party, but the most concrete worked example found and internally consistent with other sources).

---
*Stack research for: containerized AWS Glue 5.0 ETL template with Floci local emulation*
*Researched: 2026-08-06*
