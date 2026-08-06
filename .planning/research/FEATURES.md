# Feature Research

**Domain:** Open-source data-engineering starter template (GitHub template repository — AWS Glue 5.0 + Docker + Floci local emulation)
**Researched:** 2026-08-06
**Confidence:** MEDIUM (web search/fetch only, no primary-doc/Context7 access for this dimension; cross-checked across 3+ independent sources where noted, otherwise single-source and flagged LOW)

**Framing reminder:** The product IS the template. "Features" below describe what the template repository itself must contain/do so a developer who clicks "Use this template" adopts it, trusts it, and keeps most of it. This is not a features list for the example ETL job.

## Feature Landscape

### Table Stakes (Users Expect These)

Features a competent template-repo adopter assumes exist. Missing these reads as "abandoned side project," not "template."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| README with Quick Start (clone → one command → working result) | Every well-regarded template repo leads with this; "inverted pyramid" — most critical info first. Confirmed pattern across othneildrew/Best-README-Template and general README guidance surveyed. | LOW | Must literally work first try — this is the Core Value in PROJECT.md, not just a doc nicety. |
| README "Repository Structure" section explaining folders | Explicit best practice found across README guidance sources: "explain your folder structure... include short descriptions of what each folder does." | LOW | Especially important here since dirs mix Docker/Glue/Terraform/tests — unfamiliar combo for many readers. |
| LICENSE file | Baseline for any OSS repo; GitHub surfaces it prominently; template repos in this space (Floci itself is MIT) all carry one. | LOW | MIT is the natural choice — matches Floci's license and typical data-eng tooling; avoids adoption friction from copyleft. |
| `.gitignore` tuned to the stack | Must exclude Python artifacts, Docker volumes/`s3-data`-style local state (glue-local-runner generates `s3-data/` at runtime — confirmed via WebFetch), Terraform state/`.terraform/`. | LOW | Cheap, but easy to get subtly wrong (e.g. forgetting `.terraform/`, `*.tfstate`, local Floci volume dirs) — costs adopters a "why is my state committed" moment. |
| `.env.example` with every configurable name present | Confirmed as a standard convention in python-project-template surveys (Filco306/python-project-template, others) — "`.env.example` for specifying required secrets/config." | LOW | Directly required by PROJECT.md's "endpoint/credentials only via env var" constraint — this file IS the contract for that decision. |
| Dependency pinning (requirements.txt / lockfile) | Universal expectation; unpinned deps in a Glue 5.0 template are actively dangerous since the base image already fixes Python 3.11/Spark 3.5 — unpinned test/dev deps would silently drift and break reproducibility, the template's core promise. | LOW-MEDIUM | Pin at minimum: pytest, boto3, black/ruff, moto/other test deps. Must stay compatible with what's already inside `public.ecr.aws/glue/aws-glue-libs:5`. |
| A working example that runs end-to-end on first try, offline | This IS the stated Core Value in PROJECT.md. Every glue-local-docker-style repo surveyed (glue-local-runner, glue-devcontainer-template, aws-glue-local-interpreter, arukoh/glue-local) exists specifically to solve "can I run Glue without AWS," but several require manual `docker exec` + `spark-submit` steps rather than one command — see Differentiators. | MEDIUM | Depends on: Floci Glue Catalog support (confirmed), bootstrap script, `run.sh`. |
| CI that runs on every PR (build image, lint, test) with a status badge | Confirmed standard: GitHub Docs' Python workflow template plus survey results ("badges for build status... beneficial to have coverage badge"). Already locked in PROJECT.md scope. | MEDIUM | Complexity comes from running the *emulator* in CI, not just unit tests — needs Floci as a service container or docker-compose in the Actions job. |
| CONTRIBUTING.md | Confirmed near-universal across surveyed python project templates (Filco306, scottclowe/python-template-repo, ozdem1r/boilerplate_python_3, minimal-python-project-skeleton). | LOW | Even a short one (how to run tests, how to open a PR) signals the repo is maintained and lowers first-PR friction. |
| Issue templates (`.github/ISSUE_TEMPLATE/`) | Confirmed as a documented GitHub community-health-file convention (GitHub Docs, joelparkerhenderson/github-special-files-and-paths survey). | LOW | Bug report + feature request at minimum. For a template repo specifically, a "template itself is broken" vs "I have a question about adapting it" split is worth the extra template. |
| A "how to adapt this to your project" section in the README | Explicitly named as required in the research question, and matches the "rename/adopt problem" every template-repo survey flags as the #1 friction point after clicking "Use this template" (see GitHub Docs, sparkbox guide, br3ndonland/template-python approach). | LOW-MEDIUM | This is the single highest-leverage doc section for THIS project because there is no cookiecutter to automate it — see Q4/Q5 below. |
| Explicit "local vs real AWS" boundary documentation | Not generically true of README best-practice guides, but non-negotiable *for this specific template* because Floci is a lookalike, not AWS — Glue jobs/crawlers/triggers/workflows are NOT emulated (confirmed in PROJECT.md's own Floci coverage notes) and `BatchCreatePartition` is unsupported. An adopter who doesn't know this will file confused bugs or silently ship code that breaks in real AWS. | LOW to write, MEDIUM to keep accurate | Depends on Floci's supported-operations list, which can change release to release — needs periodic re-verification. |

### Differentiators (Competitive Advantage)

Where this template can credibly beat the ~8 existing "aws-glue-local-docker"-style repos found (mixi-m/aws-glue-local-image, jnshubham/aws-glue-local-etl-docker, arukoh/glue-local, anthonypernia/aws-glue-local-interpreter, wj-su/glue-local-runner, zagovorichev/aws-glue-docker, wtfzambo/glue-devcontainer-template, purecloudlabs/aws_glue_etl_docker, DNXLabs/docker-glue-libs).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Full Glue Data Catalog + Athena emulation (not just S3) | **This is the real gap.** Every surveyed repo that emulates AWS at all only emulates S3 via LocalStack, and glue-local-runner explicitly *removes* `hive-site.xml` to bypass the Glue Catalog entirely, falling back to a local Hive Metastore — i.e., existing repos give up on Catalog-backed development. Floci supports Data Catalog operations (CreateDatabase/Table/Partition, GetTable(s), etc.) directly, per PROJECT.md's own research and cross-confirmed by WebFetch of floci-io/floci. | MEDIUM | This is the hypothesis in the question and it holds up: no competitor repo found offers Catalog-aware local dev. Complexity is in getting the bootstrap script's Catalog registration right (per-partition loop workaround needed since `BatchCreatePartition` is unsupported). |
| SQL validation of job output via local Athena (DuckDB-backed) | No competitor repo, and not even LocalStack Community historically, offered this — Athena was always a paid/Pro feature or absent. Confirmed via WebFetch: Floci's Athena "executes via sidecar DuckDB and resolves table names by the Glue Data Catalog." | MEDIUM | Genuinely novel differentiator: integration tests can run `SELECT` against the job's output through the same Catalog the job registered against, closing the loop that other templates can't close. Should be showcased in the example's integration test, not buried. |
| Zero-cost, zero-token, fully offline loop (confirmed, not aspirational) | Confirmed cross-source: LocalStack Community requires an auth token as of March 2026 and Glue was always Pro-gated even before that; Floci is MIT with no account/token/feature-gate (WebFetch + WebSearch cross-confirmed). Every competitor repo either uses LocalStack (now token-gated for anything beyond S3) or requires real AWS credentials (glue-devcontainer-template explicitly mounts `~/.aws` and assumes real credentials — WebFetch-confirmed). | LOW (already true by construction — this is a claim to make loudly, not a feature to build) | This is genuinely differentiated versus glue-devcontainer-template (real-AWS-only) and versus any LocalStack-based repo (now token-gated). Worth a comparison table in the README. |
| Fast local loop (startup time, footprint) | Floci reports ~24ms startup / ~13MiB idle memory / ~90MB image vs LocalStack's ~3.3s / ~143MiB / ~1GB (WebSearch, single-source vendor-adjacent blog claims — LOW confidence, likely marketing-flavored, but directionally consistent with Floci being Java-native rather than a Python/Docker-heavy stack). | N/A (inherited from Floci, not built by this template) | Don't over-claim exact numbers in the template's own docs; cite Floci's own README/benchmarks rather than restating specific figures as if independently verified. |
| Single `./run.sh` entrypoint (vs. competitors' multi-step `docker-compose up` + manual `docker exec`/`spark-submit`) | Confirmed gap: glue-local-runner requires `docker exec` into the container and manually running `spark-submit`; glue-devcontainer-template requires opening VSCode and "Reopen in Container." Neither offers a single terminal command that takes a fresh clone to "job ran, tests green." | MEDIUM | Directly matches PROJECT.md's Core Value and the "no Makefile/no devcontainer" constraint — this is the template's signature UX moment and should be treated as the main character of the README, not a footnote. |
| Terraform module included and CI-validated (plan-only) alongside the local emulator | Most competitor repos are purely local-dev tools with no path to real AWS at all (they stop at "runs in Docker"). Providing a reviewed (if not applied) Terraform module that provisions the *same* resources the bootstrap script registers locally closes the "how do I actually ship this" gap none of the surveyed repos address. | MEDIUM-HIGH | Already in PROJECT.md scope. Differentiator only if the Terraform and the bootstrap script's schema are visibly the same source of truth (see Anti-Features: don't let them drift). |
| Explicit Glue-version currency (5.0, not 4.0) | Search confirms most current public examples/tutorials (e.g., zagovorichev/aws-glue-docker, several Medium walkthroughs) still target Glue 3.0/4.0-era images; `awslabs/aws-glue-libs` and the AWS official Docker doc have moved to `public.ecr.aws/glue/aws-glue-libs:5` but adoption in community repos lags. | LOW (already decided) | Cheap differentiator: just don't let this rot — this is the exact kind of dependency-currency claim that erodes fastest. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Cookiecutter/copier-based scaffolding | Seems like the "proper" way to solve the rename/adopt problem; most Python project templates in the ecosystem survey (cookiecutter-data-science, several python-project-template forks) do use it. | Already explicitly ruled out in PROJECT.md ("no introduce extra scaffolding tool to maintain"). Adds a Jinja-templating layer that must be maintained, tested, and kept in sync with every file in the repo — for a template whose whole pitch is minimal maintenance burden, this is a second product bolted onto the first. | GitHub's native "Use this template" + a documented, mechanical find-and-replace convention (single settings module + `.env`, see Q4 below), optionally automated with a one-time GitHub Actions rename workflow like rochacbruno/python-project-template's sed-based approach (WebFetch-confirmed) — automation without a templating *engine*. |
| Medallion/bronze-silver-gold example pipeline, Iceberg tables | Feels more "production-realistic," and is what most real Glue tutorials showcase. | Explicitly out of scope in PROJECT.md: "the product of the template is the scaffolding, not the business example... an elaborate example increases maintenance cost and the effort of whoever needs to rip it out." Every extra layer/table format is another thing that can break against Floci's partial Glue coverage and another thing an adopter has to understand before deleting. | Keep the CSV→Parquet example and instead invest the saved effort into making the scaffolding itself (bootstrap, `run.sh`, CI, Terraform) exemplary. |
| Devcontainer / VSCode-specific tooling | glue-devcontainer-template shows this is a real, semi-popular pattern (WebFetch-confirmed: `.devcontainer`, `.vscode`, poetry, pre-installed extensions) and it does lower friction *for VSCode users specifically*. | Explicitly excluded in PROJECT.md: couples the template to one editor/toolchain and duplicates what `./run.sh` + Docker already provides; also breaks the "works the same in Git Bash on Windows and Linux" constraint since devcontainers pull in Docker Desktop + VSCode Remote Containers as a second axis of environment variance. | `./run.sh` + a plain Docker Compose file that any editor can point at; nothing stops an adopter from layering their own `.devcontainer` on top later, but the template shouldn't ship or maintain one. |
| Makefile (even "just as an option alongside run.sh") | Extremely common in the ecosystem — cookiecutter-data-science, rochacbruno/python-project-template, and most Python templates surveyed default to a Makefile with `make data`/`make train`/`make init` style targets. | Explicitly excluded in PROJECT.md: `make` is not installed by default on Windows, and maintaining two parallel entrypoints (Makefile + run.sh) that must stay behaviorally identical is pure duplication for zero benefit given the stated dev environment (Windows + Git Bash). | `./run.sh` alone, with subcommands documented via its own `--help`. |
| Data science project structure (`data/raw`, `data/processed`, `notebooks/`, `models/`, `reports/`) | This is literally what cookiecutter-data-science (confirmed via WebSearch: raw/interim/processed/external, notebooks, models, reports dirs) trains people to expect from a "data" template. | Wrong shape for this project: this is an ETL/pipeline template producing code artifacts (a Glue job, a Catalog schema, infra), not a notebook-driven data science project with model artifacts. Copying that structure would import folders (`notebooks/`, `models/`) with no job to justify them, actively confusing adopters about what the template does. | Keep a small, ETL-shaped tree: source job code, `tests/`, `terraform/`, `scripts/` for bootstrap, `docs/`. Don't borrow DS-template conventions wholesale. |
| Jupyter notebook access baked into the container | Two competitor repos (glue-local-runner, purecloudlabs/aws_glue_etl_docker) expose Jupyter as their primary interactive dev mode. | Adds an HTTP service, port, and dependency surface to maintain and secure (even locally) for a template whose stated interaction model is "one command, tests go green" — notebooks encourage exploratory, non-reproducible interaction that fights the template's reproducibility-first Core Value. | If an adopter wants notebooks, that's a fork-time decision; the template's example stays script/pytest-driven. |
| Multiple package-manager options (pip + poetry + conda templates, "pick your framework" init scripts) | rochacbruno/python-project-template's `make init` (download Flask/FastAPI/Click/Typer variants) shows this pattern exists and has real adopters. | For a Glue 5.0 template, the Python environment is *already fixed* by the base image (Python 3.11, Spark 3.5) — offering package-manager choice fights the one dependency constraint that can't move, and multiplies CI matrix and doc surface for a decision the base image already made. | Standardize on `pip` + a pinned `requirements.txt` (matches what's already inside the Glue image and what boto3/pytest tooling assumes) and document it as non-negotiable, not configurable. |
| ADR tooling (Log4brains, adr-tools CLI) | Confirmed as a common ecosystem convention for documenting decisions (adr.github.io/madr, adr-tools). | A generator/static-site tool is another dependency and another thing to keep working; for a template repo the *decisions being recorded* (Glue 5.0 vs 4.0, Floci vs LocalStack) are few and mostly already captured in PROJECT.md/Key Decisions. | Plain Markdown files in `docs/adr/NNNN-title.md` using a minimal MADR-style template (bare-minimal variant), no tooling — see Documentation Surface below. |
| Auto-provisioning real AWS resources from `run.sh` (e.g. `run.sh deploy`) | Convenient-sounding "one command to go from local to prod." | Conflicts directly with PROJECT.md's Out of Scope ("Deploy real validado em conta AWS" not required) and the "no coupling to accounts/naming" public-repo constraint — baking a deploy path into `run.sh` invites adopters to point it at real accounts using template-default names/state, a security and cost footgun for a zero-credential-by-design template. | Terraform lives in its own directory, run via plain `terraform plan`/`apply` by the adopter with their own backend config — never wired into `run.sh`. |

## Feature Dependencies

```
[.env.example with all config names]
    └──requires──> [single settings/config module reads from env]
                       └──enables──> [swap Floci endpoint via env var only, no refactor]  (locked constraint)

[./run.sh single entrypoint]
    └──requires──> [Docker Compose file defining glue + floci services]
    └──requires──> [bootstrap script (boto3) registering Catalog]
    └──enables──> [Quick Start "one command" README promise]
    └──enables──> [CI reusing the same subcommands the adopter runs locally]

[bootstrap script (Catalog registration)]
    └──requires──> [Floci Glue Data Catalog support, incl. per-partition CreatePartition loop
                     since BatchCreatePartition is unsupported]
    └──enables──> [Athena/DuckDB SQL validation in integration tests]  (key differentiator)
    └──shared-source-of-truth-with──> [Terraform Data Catalog resources]
                     (if these two drift, the "local vs AWS differences" doc rots — see Pitfalls)

["local vs AWS differences" doc]
    └──requires──> [accurate, versioned list of Floci-supported vs unsupported Glue/Athena operations]
    └──enables──> [adopters trust the template instead of filing "why doesn't X work" issues]

["how to adapt this" README section]
    └──requires──> [single settings/config module]
    └──requires──> [project name NOT hardcoded into file/dir paths]
    └──conflicts-with──> [cookiecutter/copier scaffolding]  (deliberately excluded — see Anti-Features)

[GitHub Actions CI]
    └──requires──> [./run.sh subcommands (ci should call run.sh, not duplicate its steps)]
    └──requires──> [Floci runnable headless/non-interactively in CI]
```

### Dependency Notes

- **`./run.sh` requires the Docker Compose file and bootstrap script:** the entrypoint is only as good as what it wraps; sequencing in the roadmap should stand up Compose + bootstrap before polishing `run.sh` ergonomics.
- **Bootstrap script and Terraform share a source of truth:** both register the same databases/tables/partitions. If the roadmap builds these as two independent, hand-written definitions, they will drift and directly undermine the "local vs AWS differences" documentation — consider generating one from the other, or at minimum a single shared schema file (e.g. JSON/YAML) both read from, flagged as a design question for the architecture/requirements phase.
- **Athena/DuckDB validation depends on Catalog bootstrap correctness:** this is the top differentiator, but it's only crediblie once bootstrap registration (including the partition-loop workaround) is solid — sequence it after basic Catalog + job flow, not in parallel.
- **"How to adapt" doc conflicts with cookiecutter:** by design. The dependency graph shows the manual-adaptation path (settings module + doc) is the entire replacement for what a scaffolding tool would otherwise automate — under-investing in that doc section is equivalent to skipping the rename tooling other templates ship.
- **CI should call `run.sh`, not reimplement it:** every competitor repo surveyed treats "local dev flow" and "CI flow" as separate, hand-maintained scripts (docker-compose commands duplicated between README and workflow YAML). Routing CI through the same `run.sh` subcommands used locally is cheap to do now and expensive to retrofit later — flag for the requirements/architecture phase.

## MVP Definition

### Launch With (v1)

Everything already locked as Active in PROJECT.md, reframed as the true launch minimum for a *credible* template:

- [ ] `./run.sh` with a small, self-documenting subcommand surface (`up`, `run`, `test`, `lint`, `down`/`clean`, `--help`) — the signature UX moment, must work identically in Git Bash and Linux
- [ ] Docker Compose wiring Floci + the `aws-glue-libs:5` container
- [ ] boto3 bootstrap script registering databases/tables/partitions in the Data Catalog (with the `CreatePartition`-loop workaround, not `BatchCreatePartition`)
- [ ] Minimal CSV→Parquet example job
- [ ] pytest suite: unit tests on the transform + one integration test that validates output via Athena/DuckDB SQL against the real Catalog (this is the differentiator — don't defer it to v1.x)
- [ ] `.env.example` covering every AWS-endpoint/credential name, with a single settings module as the only reader of those env vars
- [ ] README: Quick Start, Repository Structure, "How to adapt this template," and a "Floci vs real AWS — what's different" section (short in v1, expandable later)
- [ ] LICENSE (MIT), `.gitignore` tuned to Docker/Terraform/Python state
- [ ] GitHub Actions CI: build image, lint, run pytest (incl. integration test) against Floci, on every PR, with a status badge in the README
- [ ] Terraform module (Glue Job, IAM role, S3 buckets, Data Catalog) — plan-validated in CI, not necessarily applied
- [ ] CONTRIBUTING.md (short) + basic issue templates (bug / adapting-the-template question)

### Add After Validation (v1.x)

Trigger: first external adopters actually use the template and hit friction points research can't fully predict.

- [ ] Deeper "local vs AWS differences" page as a standalone doc (split out of README once it outgrows a section) — trigger: repeated confused issues about unsupported operations
- [ ] `docs/adr/` with the decisions already listed in PROJECT.md's Key Decisions table, backfilled — trigger: someone asks "why Floci and not LocalStack" for the third time
- [ ] Architecture diagram (even ASCII) showing container/Compose/Catalog/Terraform relationships — trigger: onboarding friction reports, not speculative
- [ ] Troubleshooting doc — trigger: recurring issue patterns once there's real usage to mine
- [ ] SECURITY.md — trigger: first external contributor or first CVE-adjacent question; cheap to add, not needed day one for a template with no runtime service exposed

### Future Consideration (v2+)

- [ ] Automated one-time GitHub Actions rename workflow (sed-based, à la rochacbruno/python-project-template) — defer until the manual "how to adapt" doc has been validated by real adopters; automating the wrong convention is worse than documenting the right one
- [ ] Additional example job variants (e.g., partitioned write, schema evolution) — explicitly resist per PROJECT.md's Out of Scope; only reconsider if the minimal example is proven insufficient, not preemptively

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `./run.sh` single entrypoint (up/run/test/lint/clean/--help) | HIGH | MEDIUM | P1 |
| Docker Compose (Floci + Glue container) | HIGH | LOW-MEDIUM | P1 |
| boto3 Catalog bootstrap script | HIGH | MEDIUM | P1 |
| Athena/DuckDB SQL validation in integration test | HIGH (top differentiator) | MEDIUM | P1 |
| `.env.example` + single settings module | HIGH | LOW | P1 |
| README Quick Start + Structure + "how to adapt" | HIGH | LOW-MEDIUM | P1 |
| CI (build, lint, test against Floci) + badge | HIGH | MEDIUM | P1 |
| LICENSE, `.gitignore`, dependency pinning | HIGH (penalized if missing) | LOW | P1 |
| Terraform module (plan-validated in CI) | MEDIUM-HIGH | MEDIUM-HIGH | P1 (already locked scope) |
| CONTRIBUTING.md + issue templates | MEDIUM | LOW | P1 |
| "Local vs AWS differences" section (in-README) | HIGH (prevents confused issues) | LOW | P1 |
| Standalone "local vs AWS differences" page | MEDIUM | LOW | P2 |
| ADR directory (backfilled decisions) | LOW-MEDIUM | LOW | P2 |
| Architecture diagram | MEDIUM | LOW | P2 |
| Troubleshooting doc | MEDIUM | LOW (once real issues exist) | P2 |
| SECURITY.md | LOW | LOW | P2 |
| Automated rename GitHub Action | LOW-MEDIUM | MEDIUM | P3 |
| Additional example job variants | LOW (conflicts with scoping) | MEDIUM-HIGH | P3 (resist) |

**Priority key:**
- P1: Must have for launch (credibility floor + the differentiator)
- P2: Should have, add once real adopters generate signal
- P3: Nice to have, likely never — mostly listed to explicitly defer, not to plan toward

## Competitor Feature Analysis

| Feature | glue-local-runner (wj-su) | glue-devcontainer-template (wtfzambo) | This template |
|---------|---------------------------|----------------------------------------|----------------|
| AWS emulation scope | S3 only, via LocalStack; explicitly bypasses Glue Catalog (removes `hive-site.xml`) | None — mounts real `~/.aws` credentials | S3 + Glue Data Catalog + Schema Registry + Athena, via Floci |
| Single-command run | No — `docker-compose up --build` then manual `docker exec` + `spark-submit` | No — open in VSCode, "Reopen in Container," then run manually | Yes — `./run.sh run` (target) |
| Credential requirement | None for S3, but Catalog unavailable | Real AWS credentials required | None — fully offline, no token, no account |
| Editor coupling | None specified | VSCode Dev Containers required | None — plain Docker Compose + `run.sh` |
| SQL validation of output | Not available (no Catalog) | Not available (no local AWS at all) | Available via Athena/DuckDB against real Catalog |
| CI against the emulator | UNKNOWN (not evidenced in available material) | UNKNOWN (devcontainer-focused, no CI evidenced) | Yes — locked in PROJECT.md scope |
| Path to real AWS deploy | UNKNOWN (not evidenced) | Implicit (uses real AWS profiles already) | Explicit Terraform module, plan-validated in CI |
| Windows support without extra tooling | UNKNOWN (docker-compose should work, not confirmed) | Requires Docker Desktop + VSCode; Makefile/devcontainer patterns often assume Unix-like `make` | Explicit design target — Git Bash + Linux, no `make` |

## Sources

- [awslabs/aws-glue-libs](https://github.com/awslabs/aws-glue-libs) — official Glue Python interface repo (MEDIUM, official AWS org)
- [AWS Docs: Develop and test Glue jobs locally using a Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html) (HIGH, official AWS docs)
- [wj-su/glue-local-runner](https://github.com/wj-su/glue-local-runner) (LOW-MEDIUM, community repo, structure confirmed via WebFetch)
- [wtfzambo/glue-devcontainer-template](https://github.com/wtfzambo/glue-devcontainer-template) (LOW-MEDIUM, community repo, confirmed via WebFetch)
- [mixi-m/aws-glue-local-image](https://github.com/mixi-m/aws-glue-local-image), [jnshubham/aws-glue-local-etl-docker](https://github.com/jnshubham/aws-glue-local-etl-docker), [arukoh/glue-local](https://github.com/arukoh/glue-local), [anthonypernia/aws-glue-local-interpreter](https://github.com/anthonypernia/aws-glue-local-interpreter), [zagovorichev/aws-glue-docker](https://github.com/zagovorichev/aws-glue-docker), [purecloudlabs/aws_glue_etl_docker](https://github.com/purecloudlabs/aws_glue_etl_docker), [DNXLabs/docker-glue-libs](https://github.com/DNXLabs/docker-glue-libs) — surveyed via search result titles/descriptions only, not individually fetched (LOW, listed for completeness of competitive landscape, not deeply verified)
- [floci-io/floci](https://github.com/floci-io/floci) (MEDIUM, confirmed via WebFetch + cross-checked WebSearch across multiple independent write-ups: Mervin Praison blog, medevel.com, Medium x2, anavem.com, floci.io/aws)
- [rochacbruno/python-project-template — ABOUT_THIS_TEMPLATE.md](https://github.com/rochacbruno/python-project-template/blob/main/ABOUT_THIS_TEMPLATE.md) (LOW-MEDIUM, single-source WebFetch of a community template's own design notes)
- [Filco306/python-project-template](https://github.com/Filco306/python-project-template), [scottclowe/python-template-repo](https://github.com/scottclowe/python-template-repo), [saezlab/python-project](https://github.com/saezlab/python-project), [ozdem1r/boilerplate_python_3](https://github.com/ozdem1r/boilerplate_python_3) — surveyed via search results only (LOW, listed titles/descriptions, not fetched)
- [Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/) / [drivendataorg/cookiecutter-data-science](https://github.com/drivendataorg/cookiecutter-data-science) (MEDIUM, well-known project, structure confirmed via multiple independent search-result summaries)
- [MADR — Markdown Architectural Decision Records](https://adr.github.io/madr/) / [adr/madr](https://github.com/adr/madr) (MEDIUM, canonical ADR-template project)
- [GitHub Docs: Creating a repository from a template](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template) (HIGH, official GitHub docs)
- [GitHub Docs: About issue and pull request templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates) (HIGH, official GitHub docs)
- [GitHub Docs: Creating a default community health file](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file) (HIGH, official GitHub docs)
- [GitHub Docs: Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) (HIGH, official GitHub docs)
- General shell-scripting `set -euo pipefail` and self-documenting-help patterns — surveyed across multiple community write-ups (Baeldung, HowToGeek, DEV Community, assorted gists) (LOW-MEDIUM, well-established pattern but no single canonical source; treat as community consensus not an authoritative spec)
- PROJECT.md (`C:/repo/template_etl/.planning/PROJECT.md`) — primary source for all locked decisions, constraints, and the Floci Glue-coverage detail (`BatchCreatePartition` unsupported, jobs/crawlers not emulated) referenced throughout this document (HIGH, project's own ground truth)

---
*Feature research for: open-source AWS Glue 5.0 ETL project template*
*Researched: 2026-08-06*
