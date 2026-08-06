<!-- GSD:project-start source:PROJECT.md -->

## Project

**template_etl — Template de ETL com AWS Glue**

Um template open-source para iniciar projetos de ETL com AWS Glue 5.0, containerizado e com emulação local completa dos serviços AWS. Quem clona o repositório roda um único comando e vê o ambiente subir, um job PySpark executar de ponta a ponta e os testes passarem — sem precisar de conta AWS, credencial ou qualquer passo manual. É publicado como GitHub template repository, para ser o ponto de partida de novos pipelines de ETL na comunidade.

**Core Value:** Clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

### Constraints

- **Tech stack**: AWS Glue 5.0 (Spark 3.5, Python 3.11), imagem `public.ecr.aws/glue/aws-glue-libs:5` — fixa a versão de Python e das bibliotecas Spark disponíveis.
- **Custo**: zero dependências pagas ou com auth token — foi o critério que eliminou LocalStack e definiu Floci.
- **Offline**: o fluxo local completo não pode exigir conta AWS, credencial real ou acesso à internet além do pull inicial das imagens.
- **Portabilidade**: precisa funcionar em Windows (Git Bash) e Linux — sem `make`, sem dependência de toolchain fora do container.
- **Público**: repositório aberto — sem acoplamento a infraestrutura, contas, naming ou convenções proprietárias.
- **Risco de dependência**: Floci é projeto novo (2026). O acoplamento a ele deve ficar restrito a configuração de endpoint, para que a substituição custe uma variável de ambiente.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## 1. AWS Glue 5.0 Docker image

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `public.ecr.aws/glue/aws-glue-libs:5` | Glue 5.0 | Base image for the job container | This is the **only** first-party image for Glue 5.0. AWS moved Glue 5.0 images to ECR Public; Docker Hub's `amazon/aws-glue-libs` tops out at Glue 4.0 (`glue_libs_4.0.0_image_01`). Confirmed on `docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html`. **Confidence: HIGH.** |
| Apache Spark | 3.5.4 (`3.5.4-amzn-0`) | Distributed compute | Bundled, not swappable. Confirmed via image contents list and REPL banner in AWS's own doc. **HIGH.** |
| Python | 3.11.6 | Job + tooling runtime | Bundled. Confirmed via REPL banner (`Python 3.11.6 (main, Jan 9 2025...)`) in AWS's local-dev doc. **HIGH.** Patch version may have moved since; treat 3.11.x as the contract, not 3.11.6 exactly. |
| Base OS | Amazon Linux 2023 | Container OS | Documented. **HIGH.** |

### What's preinstalled

- Amazon Linux 2023, AWS Glue ETL Library, Apache Spark 3.5.4
- Apache Iceberg 1.7.1, Apache Hudi 0.15.0, Delta Lake 3.3.0 — **all three preloaded by default in Glue 5.0**; the `DATALAKE_FORMATS` env var used in Glue ≤4.0 is gone and unnecessary
- AWS Glue Data Catalog Client
- Amazon Redshift connector for Spark, Amazon DynamoDB connector for Hadoop
- `pytest` (observed as `pytest-8.3.4` / `pluggy-1.5.0` in AWS's own sample output — treat as a floor, not a pin)
- **Removed vs Glue 4.0:** JupyterLab and Livy are no longer bundled. If you want a notebook UI, you build a custom child image (AWS's own blog post builds one named `glue_v5_livy` on top of the base image — **not** something the base image gives you for free).

### The `docker run` invocations AWS documents

# spark-submit

# pyspark REPL

# pytest (note: entrypoint takes "-c '<shell command>'", not a bare command)

# Spark History Server (port 18080) — from AWS's Glue 5.0 blog post appendix

## 2. Floci

### Core facts

| Item | Value | Confidence |
|------|-------|------------|
| Docker Hub image | `floci/floci` | HIGH (official docs) |
| Standard tags | `latest`, `x.y.z` (e.g. `1.5.11`), `nightly`, `nightly-mmddyyyy` | HIGH |
| Compat tags | Same set with `-compat` suffix: `latest-compat`, `1.5.11-compat`, `nightly-compat`, `nightly-mmddyyyy-compat` | HIGH |
| Architectures | multi-arch manifest, `linux/amd64` + `linux/arm64`, auto-selected | HIGH |

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLOCI_PORT` | `4566` | API port |
| `FLOCI_HOSTNAME` | unset | Hostname embedded in returned resource URLs when run inside Compose — set this to the service name (e.g. `floci`) so URLs returned to the Glue container resolve correctly on the Docker network |
| `FLOCI_STORAGE_MODE` | `memory` | `memory` \| `persistent` \| `hybrid` \| `wal` — use `memory` for CI (fast, disposable), consider `persistent` for local dev if you want state across restarts |
| `FLOCI_STORAGE_PERSISTENT_PATH` | `./data` | Where persisted state is written when `FLOCI_STORAGE_MODE=persistent` |

### Init scripts

### Health / readiness endpoint

## 3. Pointing Spark/Hadoop S3A at Floci

### Required `spark.hadoop.fs.s3a.*` keys

- `path.style.access=true` — required because Floci (like LocalStack) doesn't do virtual-hosted-style bucket DNS resolution; without this, requests 404/fail DNS resolution.
- `connection.ssl.enabled=false` — Floci serves plain HTTP on 4566, not HTTPS; this is the practical answer to the "`DISABLE_SSL`" part of the original question — there's no such Glue/Floci env var, this Spark-conf key is the actual mechanism.
- `aws.credentials.provider=SimpleAWSCredentialsProvider` — **this is the single most common failure mode** found in research: an unresolved AWS `aws-glue-libs` GitHub issue (#112) shows exactly this symptom — a user configured endpoint/path-style/SSL correctly but still got `403 Forbidden`/`AccessDeniedException` against a local S3-compatible store because Hadoop's **default** S3A credential provider chain tries the EC2/ECS instance-metadata and env-var chains first and can silently pick up the wrong (or no) credentials before falling through to static ones. Force it to `SimpleAWSCredentialsProvider` explicitly.
- `endpoint.region=us-east-1` — recent `hadoop-aws` versions do SigV4 region validation and can fail/warn without an explicit region even for a fake endpoint; match it to Floci's default (`AWS_DEFAULT_REGION=us-east-1`).

### `s3://` vs `s3a://`

## 4. Glue Data Catalog against Floci — load-bearing limitation, stated plainly

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

## 6. Test tooling for PySpark / GlueContext

### The pattern (from AWS's own sample repo — `github.com/aws-samples/aws-glue-jobs-unit-testing`, **HIGH confidence**, first-party AWS sample):

# tests/conftest.py

- **Scope: `session`.** AWS's own sample uses session scope — one Spark/Glue context for the whole test run, not per-test. This is the right default for a template: Spark context startup is expensive (~seconds), and tests should be transformation-logic tests, not context-lifecycle tests. Use function/module scope only for the rare test that needs an isolated context (e.g. testing catalog-connection setup itself).
- For the Floci-integration test path specifically, extend this fixture to add the S3A config from §3 when constructing the `SparkContext`/`SparkConf`, and separately expose a `boto3` Glue/S3 client fixture pointed at `endpoint_url="http://localhost:4566"` for catalog/bucket assertions — do not try to route those through `GlueContext` per §4.

### chispa vs pytest-spark vs hand-rolled

| Library | Version | Verdict for this template |
|---------|---------|---------------------------|
| `chispa` | 0.12.0 (PyPI, confirmed 2026-03-24 release) | **Worth adding** as a dev dependency for DataFrame-equality assertions with readable diff output (`assert_df_equality`). Requires Python ≥3.10,<4.0 — compatible with the container's 3.11. Low-risk, small, single-purpose. |
| `pytest-spark` | last observed release 0.5.0 (older, low-activity project per search results) | **Skip.** It mainly auto-injects `spark_context`/`spark_session` fixtures via config, which conflicts with wanting an explicit, template-owned `conftest.py` fixture that also wires in Floci's S3A config and matches the exact `GlueContext` construction AWS's own sample uses. Adding a plugin to do less than a 10-line fixture already does is unnecessary surface area for a template meant to be forked and understood quickly. |
| Hand-rolled `conftest.py` (as above) | n/a | **Primary recommendation.** Matches AWS's own official sample pattern exactly, keeps the template's test setup fully readable/auditable in one file, and avoids a dependency whose main job is fixture injection you're writing yourself anyway. |

## 7. Terraform for Glue 5.0

### Core Technologies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `hashicorp/aws` provider | `~> 6.0` (latest observed: **6.58.0**, released 2026-08-05) | Provisions Glue job, IAM, S3, Data Catalog | Confirmed current on GitHub releases (`github.com/hashicorp/terraform-provider-aws/releases`). **HIGH.** |

### `aws_glue_job` for Glue 5.0

### Required IAM role/policy

### What changed for Glue 5.0 vs 4.0 in the provider

- `glue_version = "5.0"` accepted as a value (was previously only up to `"4.0"`).
- `python_version = "3.11"` accepted for Spark jobs — **required a provider bump** to work (see gotcha above); this is the one concrete, sourced "what changed" fact found. I did not find a comprehensive first-party "Terraform provider Glue 4.0→5.0 changelog" — beyond the `python_version` validation fix, no other Glue-5.0-specific provider schema changes were surfaced by research. Treat "nothing else changed" as **UNKNOWN rather than confirmed** — it's an absence of findings, not a confirmed absence of changes.

## Installation

# Python deps (inside the aws-glue-libs container, or matching venv for editor tooling)

# Dev-only extras

# Terraform provider pin (versions.tf)

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

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
