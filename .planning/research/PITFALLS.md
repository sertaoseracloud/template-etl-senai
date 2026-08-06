# Pitfalls Research

**Domain:** Local AWS Glue ETL development environment (Docker + Floci emulator + Terraform + GitHub template repository)
**Researched:** 2026-08-06
**Confidence:** MEDIUM — most findings are cross-checked across 2+ independent web sources or directly grounded in the project's own PROJECT.md decisions; Floci-specific claims are LOW confidence because the project is new and thinly documented (see Pitfall 8 for what would settle this).

## Critical Pitfalls

### Pitfall 1: `GlueContext`/`job.init()` silently expects real AWS access, even for a "fully local" job

**What goes wrong:**
`job.init()` and `GlueContext` initialization call out to AWS services (security configuration lookup, credentials resolution) as part of their normal startup path. Even when the actual data plane (S3, Catalog) is redirected to a local emulator via `AWS_ENDPOINT_URL`, `job.init()` can still fail with errors like "error while getting security configuration for None" or, when the Hadoop S3A connector's classpath disagrees with the AWS SDK version bundled in the image, `Class class com.amazonaws.auth.DefaultAWSCredentialsProviderChain does not implement AWSCredentialsProvider` on the first `CREATE TABLE`/write call. Both are reported directly against `aws-glue-libs` Docker images.

**Why it happens:**
The Glue Docker image bundles a specific AWS SDK + Hadoop S3A version pairing tuned for the real AWS control plane. The credential provider chain still probes for real AWS credentials (environment, instance profile, `~/.aws`) unless every S3A/Glue property is explicitly and consistently overridden — a partial override (e.g. only `AWS_ENDPOINT_URL` set, but not `fs.s3a.aws.credentials.provider`) is enough to trigger the mismatch.

**How to avoid:**
Pin a complete, tested set of Spark/Hadoop properties for local mode: `fs.s3a.endpoint`, `fs.s3a.path.style.access=true`, `fs.s3a.connection.ssl.enabled=false`, `fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider`, plus dummy static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` values injected via env (Floci, like LocalStack, accepts any non-empty static credentials). Bake this as one non-negotiable config block the template ships, not something each adopter reconstructs from a blog post.

**Warning signs:**
`job.init()` hangs or throws before your script's first line runs; errors mentioning `SecurityConfiguration`, `AWSCredentialsProvider`, or `DefaultAWSCredentialsProviderChain`.

**Phase to address:**
Environment/bootstrap phase — the phase that wires `run.sh run` to execute the sample job inside the `aws-glue-libs` container against Floci. This is the first thing that must work end-to-end, so it should be verified before any other feature is layered on.

---

### Pitfall 2: Job bookmarks cannot be exercised locally at all — don't let the template imply otherwise

**What goes wrong:**
Job bookmarks depend on a persisted bookmark/continuation state tied to a real Glue **JobRun**. Floci does not implement `StartJobRun`/`GetJobRun` (confirmed unsupported per PROJECT.md), and the job itself runs inside the plain `aws-glue-libs` container, not through the Glue control plane — so there is no job-run identity for a bookmark to attach to. Even AWS's own docs warn that using the DataFrame API instead of the DynamicFrame/table API silently disables bookmarking, which is an easy mistake to make when writing "simple" example jobs.

**Why it happens:**
Developers assume "local Glue container" ⇒ "full Glue feature set." Bookmarks are a Glue-managed control-plane feature, not a Spark or DynamicFrame feature — no local S3/Catalog emulator can provide it.

**How to avoid:**
Document explicitly in the README/architecture notes that job bookmarks are **not exercisable locally** and must be validated post-deploy against real AWS. If the sample job uses `transformation_ctx` for illustration, add a comment stating it's inert locally. Don't build a test that pretends to verify bookmarking against the emulator.

**Warning signs:**
A "bookmark works!" test that actually just re-runs the whole dataset every time (silently passing because nothing filters).

**Phase to address:**
Sample-job phase (documentation/comments) and README/onboarding phase (explicit scope note under "what doesn't work locally").

---

### Pitfall 3: DynamicFrame vs DataFrame behavior differences bite in both directions

**What goes wrong:**
DynamicFrames infer schema per-record and encode inconsistencies as `choice`/union types instead of failing; DataFrames require a consistent schema and throw on missing/mismatched columns. Teams that prototype with DataFrames (faster, more familiar) and only convert to DynamicFrame at the catalog-write boundary get surprised when messy CSV input (the template's own stated example) produces `choice` columns Athena/DuckDB can't query cleanly, or when `.toDF()` conversions silently coerce types.

**Why it happens:**
The two APIs are similar enough (`.select`, `.filter`, similar transform names) that developers treat them as interchangeable, but their schema-handling philosophies are opposite.

**How to avoid:**
Since the template's Out of Scope explicitly limits itself to a minimal CSV→Parquet example, keep the sample job's use of DynamicFrame vs DataFrame intentional and commented: e.g., read as DynamicFrame only if you need catalog registration via `resolveChoice`, otherwise stay in DataFrame for the transform and convert once at the write boundary. Don't silently round-trip.

**Warning signs:**
Parquet output has `struct`-wrapped "choice" columns instead of the expected primitive type; Athena/DuckDB queries against the output return unexpected nested types.

**Phase to address:**
Sample-job phase (the CSV→Parquet job itself).

---

### Pitfall 4: S3A commit semantics differ from real S3 on an emulator, and can produce silently wrong output

**What goes wrong:**
The classic S3A `FileOutputCommitter`/staging-committer algorithms rely on directory rename-via-list-and-copy semantics that assume S3's (now strong, but historically eventual) consistency model. If Floci's S3 implementation deviates even slightly from AWS S3's real read-after-write/list consistency guarantees during the commit phase (`_temporary` directory listing, rename-emulation), partial or duplicate output can occur without an explicit error — the job reports success but the Parquet output is incomplete or has stale files left in `_temporary`.

**Why it happens:**
S3-compatible emulators reimplement the S3 API surface but not necessarily its exact internal consistency and locking behavior under concurrent multipart writes; this is a documented historical source of correctness bugs even against real early-era S3.

**How to avoid:**
Use `fs.s3a.committer.name=directory` or the simplest committer explicitly (not multipart "magic" committer, which depends on S3 semantics Floci is least likely to fully replicate) for local runs, and always assert row counts / checksums in the pytest integration test rather than just checking exit code 0. Treat "job exits 0" as necessary but not sufficient.

**Warning signs:**
Row counts in output Parquet don't match input CSV row count under repeated local runs; leftover `_temporary` directories after a "successful" run.

**Phase to address:**
Integration test phase (pytest end-to-end test against the emulator) — the test must assert data content, not just process exit code.

---

### Pitfall 5: LocalStack-family emulators (and by inheritance Floci) do not enforce IAM — the biggest parity trap

**What goes wrong:**
LocalStack is IAM-permissive by default and does not enforce IAM policies unless a paid/Pro feature is explicitly turned on; a job, bootstrap script, or Terraform-provisioned role that is missing a required `iam:*`/`glue:*`/`s3:*` permission will work perfectly against the local emulator and then fail with `AccessDenied` the first time it runs against real AWS. This is the single most consequential and most-cited class of local/prod divergence in this whole domain, and it is architecturally unavoidable — no free local emulator enforces IAM, because IAM enforcement is exactly the kind of feature vendors gate behind a paid tier (this was true of LocalStack Pro before its Community sunset, and there's no evidence Floci implements it either).

**Why it happens:**
Emulators exist to make local dev frictionless; enforcing IAM would reintroduce exactly the friction (credential/policy setup) developers use emulators to avoid. It's a deliberate product tradeoff, not a bug.

**How to avoid:**
The template cannot solve this technically — it must solve it procedurally. The IAM role and policy the Terraform module provisions must be written and reviewed as if AccessDenied errors are expected on first real deploy, and the README must say explicitly: "passing locally proves the Spark logic is correct; it proves nothing about IAM. Test the Terraform-provisioned role against a real (even sandbox) AWS account before considering the pipeline done." Consider a checklist item in the "Out of Scope" boundary: this template does not and cannot validate IAM correctness.

**Warning signs:**
N/A locally by definition — this is exactly why it's dangerous. First real symptom appears only on real AWS deploy as `AccessDeniedException`.

**Phase to address:**
Terraform phase (IAM role/policy authored with least-privilege intent, not "*" wildcards to make it "just work") and README/onboarding phase (explicit warning under a "Local vs Real AWS" parity section).

---

### Pitfall 6: Athena-via-DuckDB SQL is not Athena SQL — queries that pass locally can fail or (worse) silently return different results on real Athena

**What goes wrong:**
Real AWS Athena executes on the Trino/Presto engine (with some Hive-DDL-flavored syntax for DDL); Floci's Athena emulation runs through a DuckDB sidecar. DuckDB, Presto, and Trino are three genuinely different SQL dialects (verified via sqlglot's dialect list treating `athena`, `presto`, `trino`, and `duckdb` as distinct dialects) — differences include identifier quoting (backtick/Hive DDL vs double-quote/Trino), date/time function names, `CAST` behavior on malformed input, and window-function edge cases. A test suite that validates job output "via SQL" against DuckDB is validating DuckDB semantics, not Athena semantics.

**Why it happens:**
"Query with real SQL" (a capability Floci offers that LocalStack Community never did, per PROJECT.md) is genuinely valuable, but it's easy to conflate "SQL that runs" with "SQL that means the same thing on Athena."

**How to avoid:**
Keep integration-test SQL deliberately simple (`SELECT`, `WHERE`, `COUNT`, basic aggregates) that behaves identically across dialects, and avoid relying on Athena/Trino-specific functions or Hive DDL quirks in anything the template ships as "verified." Document the DuckDB-vs-Athena gap explicitly in the parity section so adopters don't assume more coverage than exists.

**Warning signs:**
A test query using engine-specific functions (e.g., Trino's `date_trunc` variants, `approx_percentile`) either fails locally (DuckDB lacks it) or "succeeds" with different results.

**Phase to address:**
Integration test phase — keep assertion SQL minimal and portable by design; document the boundary in README.

---

### Pitfall 7: `s3://` vs `s3a://` scheme confusion inside Glue jobs

**What goes wrong:**
Glue's DynamicFrame APIs conventionally accept `s3://` paths and resolve them via the Glue-managed S3 client, while raw Spark/Hadoop DataFrame reads/writes go through the `s3a://` (Hadoop S3A connector) filesystem implementation with its own separate configuration namespace (`fs.s3a.*`). Pointing both API families at the local emulator requires configuring credentials/endpoint in two different places; missing one (commonly the `s3a://` Hadoop-level config when only the boto3/Glue-level config was set) produces confusing "works in bootstrap script, fails in Spark job" symptoms, or vice versa.

**Why it happens:**
boto3 (used in the bootstrap script) and Spark/Hadoop (used in the job) each maintain independent credential/endpoint resolution paths even though they're hitting the same emulator.

**How to avoid:**
Centralize all endpoint/credential configuration in one place (env vars consumed identically by boto3 via `AWS_ENDPOINT_URL` and by Spark via `spark-defaults.conf`/`SparkConf` reading the same env vars at container start), and verify both the bootstrap script and the Spark job independently exercise a write+read round trip in the integration test.

**Warning signs:**
Bootstrap script (boto3) succeeds registering the catalog, but the Spark job can't see the bucket/Data Catalog table, or fails with `UnknownHostException`/connection-refused on the S3A path.

**Phase to address:**
Environment/bootstrap phase — define the single source of truth for endpoint config before writing the bootstrap script or the job.

---

### Pitfall 8: Floci is a young (2026), thinly-verified project — treat its API coverage claims as provisional

**What goes wrong:**
Floci's README/marketing claims broad coverage (69 services, Glue Data Catalog + Schema Registry + Athena-via-DuckDB) but PROJECT.md already found that `BatchCreatePartition` is absent from the documented Glue operation list, and Glue jobs/crawlers are explicitly unsupported. Because the project is new, "supported" in the docs may not mean "behaves identically to AWS" for every operation, error code, and edge case (e.g., partition key type coercion, pagination tokens, error response shapes) — these gaps are typically discovered by users hitting them, not documented upfront. If the project stalls (maintainer abandonment, funding issues — the exact fate that removed LocalStack Community as an option per PROJECT.md), the template inherits an unmaintained dependency at its core.

**Why it happens:**
New infra tooling projects (especially ones positioning as a free alternative to a company whose community edition was recently paywalled) get adopted quickly on marketing signal (stars, MIT license, "drop-in" claims) before the operation-level coverage has been exercised by a large user base. GitHub star count is a popularity signal, not a correctness or maintenance-longevity signal, and is weak evidence for a claim about API fidelity.

**How to avoid:**
This risk is already partially mitigated by the locked decision to isolate Floci behind an endpoint/credential env-var boundary (per PROJECT.md's "Configuração de endpoint/credenciais exclusivamente por variável de ambiente"). Reinforce it: (1) never call Floci-specific admin/debug endpoints from the bootstrap script or job code — stick to standard boto3 Glue/S3 API calls only, so a swap to another LocalStack-compatible emulator requires zero code changes; (2) pin the exact Floci image tag/version in `docker-compose` rather than tracking `latest`, and document the pin in README so a breaking Floci release doesn't silently break the template; (3) keep the bootstrap script's partition-registration path written as a `CreatePartition` loop (not `BatchCreatePartition`) as already noted in PROJECT.md, with a comment explaining why, so nobody "fixes" it into a call that breaks locally; (4) if Floci stalls, the mitigation path is switching the `AWS_ENDPOINT_URL` (and image reference) to another LocalStack-compatible emulator — validate in CI that nothing beyond that config changes by keeping an explicit "Floci coupling" test/lint (e.g., grep CI step for Floci-specific hostnames/APIs outside the compose file).

**UNKNOWN / what would settle it:** Floci's actual test coverage for each documented Glue operation, its release/maintenance cadence beyond what's visible in the "Releases" page, and how closely its Athena-via-DuckDB error responses match real Athena's. These would be settled by: running the template's own bootstrap script + job against Floci for a few months and logging any operation-level surprises, and periodically checking `floci-io/floci` commit/release activity before each template release.

**Warning signs:**
Floci throws an unexpected error/500 on an operation the docs list as "supported"; Floci releases stop appearing for 3+ months; a `docker pull` of the pinned Floci tag starts failing (image removed/registry changed).

**Phase to address:**
Environment/bootstrap phase (isolation boundary + version pinning) and CI phase (pin verification, periodic re-check reminder in README/CONTRIBUTING).

---

### Pitfall 9: Glue image size and Spark JVM defaults dominate CI/dev loop time and can OOM in constrained containers

**What goes wrong:**
The `aws-glue-libs` image needs 7GB+ of disk and includes Amazon Linux 2023 + Spark 3.5 + Iceberg/Hudi/Delta libraries + connectors — this is a large image whose cold pull time can dominate both first-run local setup and every CI run unless cached. Separately, JVMs inside containers historically read host memory rather than the container's cgroup limit unless container-awareness is explicitly enabled/configured, which can cause a Spark driver/executor inside a memory-constrained CI runner or laptop Docker Desktop VM to allocate a heap far larger than available, leading to `OOMKilled` rather than a clear Spark memory error.

**Why it happens:**
Large ML/data images ship every library a wide user base might need "just in case"; JVM heap ergonomics were designed before containers were common and default to host-visible memory unless the runtime/flags say otherwise. Glue 5.0's image is already leaner than earlier versions (JupyterLab/Livy removed), which helps but doesn't eliminate the issue.

**How to avoid:**
In GitHub Actions, pull/cache the Glue image as a distinct cache step (Docker layer caching via buildx `cache-from`/`cache-to`, or an explicit `docker pull` + registry cache) so CI doesn't re-pull ~7GB on every PR. Locally, document the disk-space requirement in the README prerequisites section up front. For memory, explicitly cap and document `--memory` / `SPARK_DRIVER_MEMORY`/`SPARK_EXECUTOR_MEMORY` in `docker-compose`/`run.sh` at a conservative value appropriate for the minimal example job, rather than relying on JVM auto-detection inside the container.

**Warning signs:**
CI job time dominated by "Pull image" step; local `docker run` exits with code 137 (OOMKilled) with no Spark-level error message; first-run setup takes 10+ minutes with no indication of what's happening.

**Phase to address:**
CI/GitHub Actions phase (image caching) and environment/bootstrap phase (memory flags, documented disk prerequisite).

---

### Pitfall 10: CRLF line endings break `./run.sh` and any mounted shell scripts when developed on Windows

**What goes wrong:**
Git on Windows with `core.autocrlf=true` (a common default/recommendation for cross-platform repos) checks out text files with CRLF line endings. A `.sh` script checked out with CRLF and then executed inside a Linux container (either baked into the image or bind-mounted) fails because the shebang line `#!/bin/sh\r` doesn't parse — this surfaces as `bad interpreter: No such file or directory` or a Docker "exec format error," which is a genuinely confusing error message unless you already know to suspect line endings. This is a near-certain trap given the project is "developed on Windows 10 / Git Bash" per PROJECT.md, and `./run.sh` is the primary entrypoint.

**Why it happens:**
Git's line-ending normalization is a per-developer/per-machine config (`core.autocrlf`), not a repo-enforced setting, unless the repo ships a `.gitattributes` file. Without one, a contributor's local Git config silently determines whether scripts work.

**How to avoid:**
Ship a `.gitattributes` in the repo root forcing `*.sh text eol=lf` (and ideally `* text=auto eol=lf` as a baseline with explicit `.bat`/`.ps1` exceptions if any exist), so line endings are enforced at the repo level regardless of a contributor's Git config. This is strictly more robust than relying on `core.autocrlf=input` being set correctly on every contributor's machine. Optionally add a CI lint step that fails the PR if any `.sh` file contains CRLF.

**Warning signs:**
`./run.sh: line 1: $'\r': command not found`, or Docker reporting `exec /run.sh: no such file or directory` despite the file visibly existing; works for the original author but fails for a fresh clone on another Windows machine with different Git config.

**Phase to address:**
Repo-scaffolding phase (before any `.sh` script is written) — `.gitattributes` should exist before `run.sh` is committed, not retrofitted after a bug report.

---

### Pitfall 11: Git Bash/MSYS2 path mangling breaks Docker volume mount arguments in `run.sh`

**What goes wrong:**
Git Bash (MSYS2) automatically rewrites POSIX-looking path arguments (e.g., `/c/repo/template_etl`) into Windows paths before invoking any native Windows binary, including `docker.exe`. This silently corrupts `-v $(pwd):/app`-style volume mount arguments in ways that are inconsistent between Git Bash versions and Docker Desktop versions — sometimes producing a working but wrong mount, sometimes producing an outright error. Because `./run.sh` is explicitly required to work identically on Windows/Git Bash and Linux (per PROJECT.md constraints), this is a first-class risk, not an edge case.

**Why it happens:**
MSYS2's path-conversion layer exists to make POSIX-style paths work with native Windows tools generally, but Docker Desktop's own path handling for bind mounts expects a specific format, and the two translation layers don't always compose correctly — the well-known mitigation is disabling MSYS's translation for the docker invocation specifically.

**How to avoid:**
In `run.sh`, explicitly `export MSYS_NO_PATHCONV=1` (guarded so it's a no-op on native Linux/macOS, e.g., only set when `$OSTYPE` indicates msys/cygwin) before any `docker`/`docker compose` invocation involving volume mounts, and always build mount paths via `$(pwd)` rather than hardcoded absolute paths. Add this as a documented, tested requirement — verify it in CI is not sufficient since GitHub Actions Windows runners don't reproduce Git Bash's exact MSYS path behavior the same way a real Windows 10 + Git Bash dev machine does; this needs a real manual check on Windows before shipping.

**Warning signs:**
Volume mount silently points at the wrong path (container sees an empty directory or the wrong drive), or Docker reports it cannot find/create the mount source; behavior differs between two Windows machines with different Git Bash versions.

**Phase to address:**
Entrypoint (`run.sh`) phase — must be manually verified on a real Windows 10 + Git Bash environment (matching PROJECT.md's stated dev environment), since CI on Linux runners cannot catch this class of bug.

---

### Pitfall 12: Public GitHub template repositories rot — unpinned deps, drifted README, CI that only ever passed once

**What goes wrong:**
Starter templates decay in predictable ways: (a) unpinned or loosely-pinned dependency versions (Terraform provider versions, Python package versions, the Floci image tag) drift and break months after the template's last commit, with no CI run to catch it because CI only runs on PRs/pushes, not on a schedule; (b) the README example commands stop matching the actual `run.sh` subcommands as the CLI evolves; (c) CI that was only ever validated on the maintainer's exact local Docker/OS setup passes in the author's environment and fails for adopters on a different OS or Docker version; (d) a public template repo generates an ongoing stream of issues/questions from adopters unfamiliar with the domain (Glue, Terraform, Docker) that the maintainer must triage indefinitely, which is a maintenance cost distinct from the code itself.

**Why it happens:**
Template repos are typically built once during an initial burst of effort and then get infrequent maintenance attention, while their dependencies (Docker base images, Terraform provider versions, the Glue image tag, Floci itself) keep releasing. Nothing forces revalidation unless CI runs on a schedule.

**How to avoid:**
Pin exact versions everywhere that matters (Glue image tag `:5` is already fairly stable per AWS's tagging scheme, but Floci's tag and Terraform provider versions should be pinned exactly, not `>=`); add a **scheduled** GitHub Actions workflow (e.g., weekly `cron`) that runs the full local flow (`run.sh up`, sample job, pytest suite) even with no code changes, so dependency drift is caught by CI rather than by an adopter's bug report. Keep the README's command examples generated from or tested against the actual `run.sh --help` output where feasible, or at minimum add a CI check that greps README code blocks for subcommands and verifies they exist in `run.sh`. Explicitly scope maintenance expectations in CONTRIBUTING.md (e.g., "this is a template, PRs for the sample job's business logic will be redirected — PRs for the scaffolding itself are welcome") to control issue-triage load, matching PROJECT.md's own stated principle that the sample job should stay minimal.

**Warning signs:**
Last CI run (visible in Actions tab) is many months old with no scheduled runs since; README references a `run.sh` subcommand that `run.sh --help` doesn't list; a fresh `git clone` + first-run fails on a machine that isn't the original author's.

**Phase to address:**
CI/GitHub Actions phase (add the scheduled drift-detection workflow) and README/onboarding phase (keep examples verifiably in sync); revisit at any future milestone before advertising the template further.

---

### Pitfall 13: Over-scaffolding — the template ships things adopters must delete before they can use it

**What goes wrong:**
Templates that try to be helpful by including a "realistic" example (multiple tables, a medallion-style pipeline, elaborate IAM, extra services) increase the amount of code an adopter must understand and rip out before writing their own pipeline, and every piece of "example" scaffolding becomes something that can rot per Pitfall 12. PROJECT.md has already explicitly scoped this out (minimal CSV→Parquet only, no medallion/Iceberg example), which is the correct call — this pitfall is flagged here as a guardrail against scope creep during roadmap/phase planning, not as a new finding.

**Why it happens:**
It's tempting during implementation to "just add one more realistic touch" (a second table, a join, a partition-projection example) because it demonstrates more capability — but each addition is scaffolding a real adopter has to first understand, then delete.

**How to avoid:**
Treat PROJECT.md's Out of Scope list as a hard boundary during phase planning and code review, not a suggestion — any PR/phase that adds business-logic complexity to the sample job beyond "read CSV, minimal transform, write Parquet, register in Catalog" should be challenged.

**Warning signs:**
The sample job's line count grows across phases without a corresponding requirement; a new phase adds a "nice example" of a feature (e.g., partitioned writes, joins) that wasn't in the original requirements list.

**Phase to address:**
Roadmap/phase planning itself — this is a planning discipline, not an implementation task.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|------------------|
| Using `latest` tag for Floci or Glue image instead of pinning | Always "current" without a version bump PR | Silent breakage when upstream ships a breaking change; un-reproducible CI failures | Never in a public template — pin always |
| Wildcard/broad IAM policy in Terraform to "make it work" | Deploy succeeds on first try, no AccessDenied debugging | Teaches adopters an anti-pattern; real risk if adopters ship the wildcard policy to production unmodified | Never — even for a template, least-privilege should be modeled since this is the one artifact deploying to a real account |
| Skipping row-count/content assertions in the integration test (just checking exit code 0) | Faster to write, test "passes" immediately | Silent data-loss bugs from S3A commit semantics (Pitfall 4) go undetected | Never for the end-to-end test; acceptable only for a throwaway smoke test that's clearly labeled as such |
| Hardcoding Floci-specific behavior/endpoints outside the single config boundary | Slightly less indirection, marginally simpler code | Defeats the whole point of the env-var isolation decision in PROJECT.md; makes future emulator swap expensive | Never |
| Not adding a scheduled CI drift-check workflow | Simpler initial CI setup | Dependency rot (Pitfall 12) discovered by adopters, not maintainers | Acceptable to defer to a later phase/milestone, but should be tracked, not silently dropped |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| Spark ↔ Floci S3 (S3A) | Setting `AWS_ENDPOINT_URL` but forgetting `fs.s3a.path.style.access=true` and `fs.s3a.aws.credentials.provider` | Configure the full S3A property set together as one block; never partially override |
| boto3 bootstrap script ↔ Spark job | Each independently re-deriving endpoint/credential config, drifting apart over time | Single source of truth (env vars) consumed identically by both, verified by an integration test that exercises both paths |
| Terraform ↔ Floci-provisioned local resources | Reusing the same Terraform module against both local (Floci) and real AWS without conditional guards | Keep Terraform targeting real AWS only; use the boto3 bootstrap script for local, as already decided in PROJECT.md — don't blur this boundary |
| GitHub Actions ↔ Glue/Floci images | Re-pulling large images from scratch every PR | Docker layer caching (`buildx cache-from/cache-to`) or registry cache configured explicitly in the CI phase |
| Athena queries (via Floci/DuckDB) ↔ real Athena (Trino) | Assuming query behavior validated locally will match production | Keep local-verified SQL restricted to dialect-portable subset; document the gap |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| JVM heap sized by host-visible memory inside container | `OOMKilled` (exit 137) with no clear Spark error | Explicitly set conservative `SPARK_DRIVER_MEMORY`/`--memory` container limits rather than relying on auto-detection | Any CI runner or laptop with less RAM than the JVM's default heap guess |
| Re-pulling ~7GB Glue image on every CI run | CI minutes dominated by image pull, slow PR feedback | Layer caching / registry cache in GitHub Actions | As soon as CI runs on more than a handful of PRs |
| S3A "magic"/multipart committer under emulator consistency gaps | Intermittent, non-reproducible data loss in output | Use simpler directory-rename committer for local runs; assert data content, not just exit code | Under concurrent writes or larger files/partitions than the minimal example |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Wildcard IAM policy in the shipped Terraform module | Adopters copy it into real production accounts unmodified | Author least-privilege IAM scoped to exactly the Glue job/Catalog/S3 actions needed, even though local testing can't validate it |
| Committing real AWS credentials to `.env`/docker-compose during local dev/debugging of the credential-mismatch errors (Pitfall 1) | Accidental credential leak in a public repo | `.gitattributes`/`.gitignore` covering `.env*`; README explicitly states local dev never needs real credentials, only dummy static values |
| Static dummy credentials (`test`/`test`) accidentally reused against real AWS endpoint due to a misconfigured `AWS_ENDPOINT_URL` | Job could attempt to run against real AWS with garbage credentials — confusing failure at best | Environment-variable config validated/asserted at `run.sh` startup (fail fast if `AWS_ENDPOINT_URL` is unset in local mode, rather than silently falling through to AWS's default endpoints) |

## "Looks Done But Isn't" Checklist

- [ ] **Sample job "works":** Often only exit-code-0 checked — verify row counts/content match expectations (Pitfall 4), not just process success.
- [ ] **`run.sh` works "on my machine":** Often only verified on the author's exact Windows/Git Bash + Docker Desktop version — verify a fresh clone on a different Windows machine (MSYS_NO_PATHCONV, CRLF) and on native Linux.
- [ ] **CI "passes":** Often only validated at time of writing — verify a scheduled/dependency-drift run exists so passing CI still means something months later.
- [ ] **IAM role in Terraform "works":** Passing locally proves nothing about IAM (Pitfall 5) — verify least-privilege intent was reviewed, not just "job runs against the emulator."
- [ ] **Athena/DuckDB queries in tests "validate the pipeline":** Verify the SQL used is dialect-portable, not exercising Trino/Hive-specific syntax that DuckDB happens to also support with different semantics.
- [ ] **Bootstrap script "registers partitions":** Verify it loops `CreatePartition` rather than calling `BatchCreatePartition`, which Floci doesn't support (per PROJECT.md).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| Floci stalls/is abandoned | MEDIUM | Swap `AWS_ENDPOINT_URL` + image reference to another LocalStack-compatible emulator; if the endpoint-isolation boundary (Pitfall 8 mitigation) was respected, no application code should need to change |
| CRLF breaks `run.sh` for a contributor | LOW | Add/fix `.gitattributes`, have the contributor `git rm --cached` + re-checkout affected files |
| Data-loss bug from S3A commit semantics discovered late | MEDIUM | Switch committer algorithm, add content-assertion tests retroactively, re-run full suite |
| Adopter ships wildcard IAM policy to production and hits a security review | HIGH (their side) | Template's responsibility ends at documenting the least-privilege intent clearly; recovery is on the adopter, but README warning reduces likelihood |
| Template README drifts from actual `run.sh` behavior | LOW | Add CI check cross-referencing README command blocks against `run.sh --help`; fix as a doc PR |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| 1. GlueContext/job.init needs real AWS access | Environment/bootstrap phase | Sample job runs end-to-end against Floci with zero real AWS credentials present in the environment |
| 2. Job bookmarks not exercisable locally | Sample-job + README phase | README/code comments explicitly state the limitation |
| 3. DynamicFrame vs DataFrame divergence | Sample-job phase | Code review checks conversions are intentional/commented |
| 4. S3A commit semantics on emulator | Integration test phase | pytest asserts row count/content, not just exit code |
| 5. IAM not enforced locally (parity trap) | Terraform phase + README | Terraform IAM reviewed for least-privilege; README has explicit parity warning |
| 6. Athena-via-DuckDB dialect drift | Integration test phase | Test SQL restricted to dialect-portable subset, documented |
| 7. `s3://` vs `s3a://` scheme confusion | Environment/bootstrap phase | Single env-var-driven config consumed by both boto3 and Spark, both paths tested |
| 8. Floci immaturity/coverage gaps | Environment/bootstrap phase + CI phase | Endpoint isolation boundary enforced (lint/grep check); image tag pinned |
| 9. Image size/JVM memory defaults | CI phase + environment phase | CI image caching configured; memory flags documented and set |
| 10. CRLF breaks shell scripts | Repo-scaffolding phase | `.gitattributes` exists before first `.sh` commit; CI lint for CRLF |
| 11. Git Bash/MSYS path mangling | `run.sh` phase | Manually verified on real Windows 10 + Git Bash (not just CI) |
| 12. Template rot (deps, README, CI) | CI phase + README phase | Scheduled CI workflow exists; README examples checked against `run.sh --help` |
| 13. Over-scaffolding | Roadmap/phase planning | Out of Scope list enforced in review |

## Sources

- [Develop and test AWS Glue jobs locally using a Docker image (AWS Glue docs)](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [Docker image for AWS Glue version 5.0 — AWS re:Post](https://repost.aws/questions/QUaALGdTZtTGmfTMfeWoI9Tg/docker-image-for-aws-glue-version-5-0)
- [Develop and test AWS Glue 5.0 jobs locally using a Docker container — AWS Big Data Blog](https://aws.amazon.com/blogs/big-data/develop-and-test-aws-glue-5-0-jobs-locally-using-a-docker-container)
- [AWS Glue docker image DefaultAWSCredentialsProviderChain error — GitHub Issue #130, awslabs/aws-glue-libs](https://github.com/awslabs/aws-glue-libs/issues/130)
- [awsglue.job.Job.init arguments — GitHub Discussion #117, awslabs/aws-glue-libs](https://github.com/awslabs/aws-glue-libs/discussions/117)
- [Using job bookmarks — AWS Glue docs](https://docs.aws.amazon.com/glue/latest/dg/programming-etl-connect-bookmarks.html)
- [Required to use transformation_ctx in all glue Transforms? — AWS re:Post](https://repost.aws/questions/QUDYroVypJQmWeSgfrZPXOGw/required-to-use-transformation-ctx-in-all-glue-transforms)
- [Difference between pyspark dataframe and aws glue dynamicframe — Medium](https://medium.com/@irshadalamtech/difference-between-pyspark-dataframe-and-dynamicframe-f5c863201afd)
- [DynamicFrame class — AWS Glue docs](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-crawler-pyspark-extensions-dynamic-frame.html)
- [Introducing the S3A Committers — Apache Hadoop docs](https://hadoop.apache.org/docs/stable/hadoop-aws/tools/hadoop-aws/committer_architecture.html)
- [Committing work to S3 with the S3A Committers — Apache Hadoop](https://github.com/apache/hadoop/blob/trunk/hadoop-tools/hadoop-aws/src/site/markdown/tools/hadoop-aws/committers.md)
- [S3 Committers and EMRFS in AWS EMR's Big Data Processing using Spark — Medium/Globant](https://medium.com/globant/s3-committers-and-emrfs-in-aws-emrs-big-data-processing-using-spark-4b311dac1ede)
- [Integrating Spark with Localstack S3 — Medium](https://medium.com/@davidsmithtech/integrating-spark-with-localstack-s3-4f4c85487362)
- [floci-io/floci — GitHub repository and README](https://github.com/floci-io/floci)
- [Floci: A Lightweight, Open-Source Local AWS Emulator for Developers — Medevel](https://medevel.com/floci/)
- [Introducing Floci: The Fast, Free, and Open-Source AWS Emulator](https://hectorvent.dev/posts/introducing-floci/)
- [Generate IAM policies locally using LocalStack](https://hashnode.localstack.cloud/generate-iam-policies-locally-using-localstack)
- [IAM Policy Enforcement — LocalStack docs](https://docs.localstack.cloud/aws/capabilities/security-testing/iam-policy-enforcement/)
- [sqlglot dialects (athena, presto, trino, duckdb as distinct dialects)](https://sqlglot.com/sqlglot/dialects/athena.html)
- [Trino vs. Presto vs. Spark SQL vs. DuckDB comparison](https://www.devtechie.com/blog/sql-engines-comparison-guide)
- [Mounting Docker volumes on Windows using Git Bash — Gist](https://gist.github.com/pedrodeoliveira/80ef038dcb8bd7ebfccdad5f2c95d3b2)
- [Docker and Git Bash / MSYS2 on Windows: path conversion workaround — Gist](https://gist.github.com/borekb/cb1536a3685ca6fc0ad9a028e6a959e3)
- [borekb/docker-path-workaround — GitHub](https://github.com/borekb/docker-path-workaround)
- [[BUG] Docker fails to execute docker-entrypoint.sh on Windows due to CRLF line endings — GitHub Issue #8434, activepieces/activepieces](https://github.com/activepieces/activepieces/issues/8434)
- [The case of Windows line-ending in bash-script — Sergei Dorogin's blog](https://techblog.dorogin.com/the-case-of-windows-line-ending-in-bash-script-7236f056abe)
- [Java inside docker: What you must know to not FAIL — Red Hat Developer](https://developers.redhat.com/blog/2017/03/14/java-inside-docker)
- [Spark Memory Management: The Complete 2026 Guide — luminousmen](https://luminousmen.com/post/dive-into-spark-memory/)
- [How I Reduced Docker Pull Time from 3 Minutes to 3 Seconds — DEV Community](https://dev.to/sandeepkomal/how-i-reduced-docker-pull-time-from-3-minutes-to-3-seconds-b54)
- [Creating a template repository — GitHub Docs](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository)
- Project's own PROJECT.md (C:/repo/template_etl/.planning/PROJECT.md) — locked decisions on Floci Glue operation coverage, LocalStack Community sunset, BatchCreatePartition gap

---
*Pitfalls research for: local AWS Glue ETL Docker template with Floci emulation*
*Researched: 2026-08-06*
