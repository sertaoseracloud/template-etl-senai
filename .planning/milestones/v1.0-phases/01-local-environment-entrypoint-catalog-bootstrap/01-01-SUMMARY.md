---
phase: 01-local-environment-entrypoint-catalog-bootstrap
plan: 01
subsystem: local-environment
tags: [docker-compose, gitattributes, gitignore, floci, aws-glue, ruff, boto3]
status: complete

dependency-graph:
  requires: []
  provides:
    - .gitattributes (LF enforcement for .sh, ahead of any .sh file)
    - .gitignore (.env exclusion, research cache exclusion, Terraform state exclusion)
    - docker-compose.yml (floci default service; tools/glue profiled services)
    - .env.example (six documented config variables)
    - requirements.txt (boto3, ruff pinned by compatible-release range)
    - docker/tools/Dockerfile (python:3.11-slim tools image)
    - pyproject.toml (ruff config, target py311)
  affects:
    - 01-02 (run.sh consumes docker-compose.yml services and .env.example contract)
    - 01-03 (catalog/bootstrap.py and catalog/seed.py run inside the tools service built here)

tech-stack:
  added:
    - floci/floci:1.5.11 (S3/Glue/Athena emulator)
    - public.ecr.aws/glue/aws-glue-libs:5 (declared, not pulled by this plan)
    - python:3.11-slim (tools service base image)
    - boto3~=1.43.0, ruff~=0.16.0 (pip, installed at image build time)
  patterns:
    - env_file: - .env (not ${VAR} interpolation) isolates containers from host-shell AWS credentials
    - profiles: ["tools"] / ["glue"] keep `docker compose up` to a single default service (floci)
    - .gitattributes committed before any .sh file exists in the repository

key-files:
  created:
    - .gitattributes
    - .gitignore
    - requirements.txt
    - docker/tools/Dockerfile
    - pyproject.toml
    - docker-compose.yml
    - .env.example
  modified: []

decisions:
  - "boto3 and ruff pinned with ~= compatible-release ranges (boto3~=1.43.0, ruff~=0.16.0), not exact ==, per checkpoint-approved operator deviation. See Deviations section."
  - "floci's built-in HEALTHCHECK confirmed via docker image inspect; no healthcheck: key authored in compose (resolves the STACK.md-vs-ARCHITECTURE.md disagreement empirically in ARCHITECTURE.md's favor)."

actuals:
  tokens: 3600
  tasks: 3
  commits: 3

metrics:
  duration: "36m"
  completed: 2026-08-06
---

# Phase 01 Plan 01: Local Environment Entrypoint & Catalog Bootstrap — Environment Scaffolding Summary

Container topology (floci default, tools/glue profiled) plus the .gitattributes/.gitignore/.env.example scaffolding a Windows-safe, credential-free public template needs before the first `.sh` file or `.env` can exist.

## What Was Built

- **`.gitattributes`** — `* text=auto eol=lf` baseline, `*.sh text eol=lf` explicit rule, `*.csv text eol=lf`, and binary markers for `*.parquet`/`*.png`. Committed in the first commit of this plan, before any `.sh` file exists anywhere in the repository (Pitfall 10 / ROADMAP Ordering Constraint 1).
- **`.gitignore`** — excludes `.env`/`.env.*` with a `!.env.example` negation (T-01-01), the research fetch cache (T-01-02), Python/ruff/pytest cache dirs, Terraform state (T-01-04, pre-emptively), and `.DS_Store`.
- **Untracked the research fetch cache** — `git rm -r --cached .planning/research/.cache` removed 8 tracked JSON files from the index; they remain on disk.
- **`requirements.txt`** — `boto3~=1.43.0` and `ruff~=0.16.0`, pip-installed (D-06), no `pytest` (Phase 2 owns that decision).
- **`docker/tools/Dockerfile`** — `python:3.11-slim` base, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `RUFF_CACHE_DIR=/tmp/ruff-cache`, `WORKDIR /workspace`, installs `requirements.txt` at build time so no network access is needed per invocation.
- **`pyproject.toml`** — `[tool.ruff]` only (no `[project]` table — this is a template, not a distributable package), `target-version = "py311"`, `line-length = 100`, `select = ["E", "F", "W", "I", "UP", "C4", "SIM", "PTH"]`.
- **`docker-compose.yml`** — three services, no top-level `version:` key:
  - `floci` (`floci/floci:1.5.11`, default profile) — `FLOCI_HOSTNAME=floci`, `FLOCI_PORT=4566`, `FLOCI_STORAGE_MODE=memory` under `environment:` (compose-network facts, not adopter config); no `healthcheck:` authored — confirmed via `docker image inspect` that the image ships its own.
  - `tools` (build from `docker/tools/Dockerfile`, `profiles: ["tools"]`) — `depends_on: floci: condition: service_healthy`, `working_dir: /workspace`, `.:/workspace:ro`, `env_file: - .env`.
  - `glue` (`public.ecr.aws/glue/aws-glue-libs:5`, `profiles: ["glue"]`) — same `depends_on`, `working_dir: /home/hadoop/workspace`, `.:/home/hadoop/workspace` read-write, `env_file: - .env`.
- **`.env.example`** — exactly six variables: `PROJECT_NAME`, `AWS_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `FLOCI_HOST_PORT`. No `DISABLE_SSL`, no SDK-v2 region spelling — neither is read by these containers.

## Deviations from Plan

### Auto-fixed Issues

None — the two Task 1 and Task 3 acceptance criteria that touched real infrastructure (`.gitattributes` ordering, floci healthcheck) both resolved cleanly with no code fix needed.

### Human-approved deviation (checkpoint resolution)

**1. [Checkpoint decision] boto3 and ruff pinned by compatible-release range (`~=`), not exact (`==`)**
- **Found during:** Task 2, blocking-human package-legitimacy checkpoint.
- **Original plan:** `requirements.txt` pins both dependencies with exact `==` versions; verified by acceptance criterion `grep -vE '^\s*(#|$)' requirements.txt | grep -cvE '^[A-Za-z0-9._-]+==[0-9]'` returning `0`.
- **What changed:** The human operator verified both packages on PyPI (boto3: Amazon Web Services, 500+ releases since 2015; ruff: Astral Software Inc., 300+ releases since 2023, version 0.16.1 matching STACK.md) and explicitly chose compatible-release ranges over exact pins: `boto3~=1.43.0` and `ruff~=0.16.0` (resolving to `>=1.43.0,<1.44.0` and `>=0.16.0,<0.17.0`).
- **Rationale (operator's):** ruff is pre-1.0, so a minor version bump can change lint rules and break an adopter's clone months later with no repository change. Patch-only pinning keeps that failure mode out of scope; Phase 3's scheduled drift-detection workflow (CI-03) is the intended catch if a pinned range ever does go bad.
- **Verification impact:** the plan's original exact-pin verify command (`grep -cvE '^[A-Za-z0-9._-]+==[0-9]'` returning `0`) now returns `2` (both lines use `~=`, not `==`) — reported here as the actual output rather than silently satisfied. The functional intent of the acceptance criterion — "every dependency is pinned, not floating" — is still met: `~=X.Y.Z` bounds both a floor and a ceiling, it is not an unbounded/`latest` dependency.
- **Files modified:** `requirements.txt`.
- **Commit:** `1826d3c`.
- **Resolved packages:** `boto3-1.43.66`, `ruff-0.16.1` (both fall inside their respective `~=` ranges, confirmed by the `docker compose --profile tools build tools` output and `ruff --version`).

### Verification-command discrepancy (not a compose-file defect)

**2. `docker compose config --services --profiles ''` / `docker compose config --services` (all profiles) behave differently than the plan's acceptance criteria assumed, on Compose v2.39.2.**
- In this Compose CLI version, `--profiles` (no argument) is a boolean flag that prints *profile names*, not a filter that activates all profiles. `docker compose config --services --profiles ''` and plain `docker compose config --services` both returned `floci` only — which happens to match the plan's default-profile assertion, but the "all profiles → floci, tools, glue" assertion required an alternate invocation (`COMPOSE_PROFILES='*' docker compose config --services`, confirmed to return `floci glue tools`, or `docker compose --profile tools --profile glue config --services`).
- This is a plan-verify-command wording issue against a newer Compose CLI, not a defect in `docker-compose.yml`. The functional requirement — default `docker compose up` starts only `floci`, and `tools`/`glue` are reachable only via explicit profile activation — is independently confirmed by the actual `docker compose up -d --wait floci` run (see Verification section below).

## Verification (actual output)

All commands run from the repository root, in order:

1. `docker compose config --quiet` → exit 0.
2. `docker compose up -d --wait floci` → `Container template_etl-floci-1 Healthy`; `docker compose ps --services --filter status=running` → `floci` only.
3. `docker images --format '{{.Repository}}' | grep -c aws-glue-libs` → `0` (Glue image never pulled).
4. `docker compose --profile tools build tools` → exit 0, `boto3-1.43.66`/`ruff-0.16.1` installed. `docker compose --profile tools run --rm tools ruff --version` → `ruff 0.16.1`.
5. `git check-ignore .env` → exit 0. `git check-ignore .env.example` → exit 1 (not ignored).
6. `git ls-files .planning/research/.cache` → empty.
7. `docker compose down -v --remove-orphans` → all containers/network removed, `docker compose ps -a` empty.

Additional acceptance checks run and passed:
- `docker image inspect floci/floci:1.5.11 --format '{{json .Config.Healthcheck}}'` → non-null (`CMD-SHELL curl -f http://localhost:4566/_floci/health || exit 1`, interval 5s, 5 retries) — confirms no `healthcheck:` key is needed in compose.
- `AWS_ACCESS_KEY_ID=AKIAHOSTLEAK docker compose --profile tools run --rm tools python -c "import os; print(os.environ['AWS_ACCESS_KEY_ID'])"` → printed `test`, not `AKIAHOSTLEAK` — confirms `env_file:` isolation from host-shell credentials (T-01-03).
- Second `docker compose --profile tools build tools` → `pip install` step reported `CACHED` — confirms the offline-rebuild backstop truth.
- `.env.example` contains exactly six `KEY=value` assignments (`PROJECT_NAME`, `AWS_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `FLOCI_HOST_PORT`); zero occurrences of `DISABLE_SSL` or `AWS_REGION=`.

## Known Stubs

None. Every artifact this plan claims to produce (`.gitattributes`, `.gitignore`, `docker-compose.yml`, `.env.example`, `requirements.txt`, `docker/tools/Dockerfile`, `pyproject.toml`) is complete and independently verified — no placeholder values, no unwired data paths.

## Threat Flags

None beyond the threat model already declared in `01-01-PLAN.md`. All six STRIDE entries (T-01-01 through T-01-06, T-01-SC) are mitigated as planned; the `AKIAHOSTLEAK` test independently confirms T-01-03.

## Self-Check: PASSED

- `.gitattributes` exists — FOUND.
- `.gitignore` exists — FOUND.
- `requirements.txt` exists — FOUND.
- `docker/tools/Dockerfile` exists — FOUND.
- `pyproject.toml` exists — FOUND.
- `docker-compose.yml` exists — FOUND.
- `.env.example` exists — FOUND.
- Commit `4e53b36` (Task 1) — FOUND in `git log --oneline --all`.
- Commit `1826d3c` (Task 2) — FOUND in `git log --oneline --all`.
- Commit `ae3c7b0` (Task 3) — FOUND in `git log --oneline --all`.
