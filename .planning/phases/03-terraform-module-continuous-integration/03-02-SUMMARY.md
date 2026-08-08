---
phase: "03"
plan: "02"
subsystem: github-actions
tags:
  - ci
  - github-actions
  - terraform
  - drift-detection
  - glue
dependency_graph:
  requires: []
  provides:
    - .github/workflows/ci.yml
    - .github/workflows/drift.yml
  affects: []
tech_stack:
  added:
    - GitHub Actions (docker/build-push-action v6, actions/checkout v4, actions/cache v4, hashicorp/setup-terraform v3)
  patterns:
    - Sequential job dependency chain (lint -> terraform -> test)
    - Docker Buildx cache (GHA) for large Glue image
    - AWS credentials via repository secrets (OIDC deferred to v2)
    - Scheduled cron trigger for proactive upstream breakage detection
key_files:
  created:
    - .github/workflows/ci.yml
    - .github/workflows/drift.yml
decisions:
  - id: D-01
    decision: Used docker/build-push-action with cache-from/cache-to type=gha,mode=max for Glue image caching
    rationale: Avoids re-pulling ~4.77 GB Glue image on every CI run; mode=max caches all layers
  - id: D-05
    decision: Three sequential jobs (lint -> terraform -> test) with explicit needs: dependencies
    rationale: Fast feedback first; terraform validation runs only after lint passes; test only runs after terraform validation
  - id: OIDC-deferral
    decision: Used AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY from secrets; added comment noting OIDC deferred to v2
    rationale: Aligns with deferred ideas in 03-CONTEXT.md; keeps v1 simple while documenting the planned improvement
  - id: quote-on-yaml
    decision: Quoted "on:" as "on:" in YAML files to prevent PyYAML 1.1 boolean parsing (on: -> True)
    rationale: PyYAML 6.x parses bare "on:" as a boolean in YAML 1.1 mode; quoting preserves string semantics
metrics:
  tokens: 45000
  raw_tokens: 22000
  tasks: 2
  commits: 2
  confidence: high
status: complete
actuals:
  tokens: 45000
  tasks: 2
  commits: 2
---

# Phase 03 Plan 02: GitHub Actions Workflows Summary

## One-liner

Created two GitHub Actions workflows: a CI pipeline that runs lint, terraform validation, and the full test suite sequentially on push and pull requests, and a scheduled drift-detection workflow that runs the complete demo loop twice weekly.

## Completed Tasks

### Task A: CI workflow (ci.yml)
- Sequential jobs: lint -> terraform -> test with explicit `needs:` dependencies
- **lint job**: runs `./run.sh lint` (ruff check + format check via tools container)
- **terraform job**: runs `terraform init -backend=false && terraform fmt -check -recursive && terraform validate` with no AWS credentials (offline validation per IAC-04)
- **test job**: runs `./run.sh bootstrap && ./run.sh seed && ./run.sh job && ./run.sh test` sequentially, invoking `./run.sh` subcommands (not duplicating compose steps)
- Triggers on `push` to `main` and on `pull_request`
- Glue image caching via `docker/build-push-action` with `cache-from: type=gha` and `cache-to: type=gha,mode=max`
- Small deps (ruff, pytest) cached via `actions/cache` standard
- AWS credentials via `secrets.AWS_ACCESS_KEY_ID` / `secrets.AWS_SECRET_ACCESS_KEY`; OIDC deferred to v2 (comment documented)
- **Commit**: f8d940a

### Task B: Drift Detection workflow (drift.yml)
- Single job: `demo` that runs `./run.sh demo` (full pipeline: up -> bootstrap -> seed -> job -> test)
- Scheduled cron: `0 8 * * 1,4` (Monday and Thursday 08:00 UTC)
- Same Glue image caching as ci.yml
- Workflow `name: "Drift Detection"` appears in the Actions tab
- Comment explains purpose: detects upstream image/dependency breakage without any code change
- **Commit**: d467a35

## Deviations from Plan

None - plan executed exactly as written.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| none | - | No new trust-boundary surface introduced; credentials use existing secrets pattern |

## Overall Verification

All success criteria met:
- ci.yml exists with three sequential jobs (lint, terraform, test)
- drift.yml exists with schedule trigger
- Both invoke ./run.sh subcommands (not duplicate compose/pytest steps)
- ci.yml triggers on push and pull_request
- drift.yml triggers twice weekly (Monday and Thursday 08:00 UTC)
- Glue image caching configured in both workflows
