# Milestones

## v1.0 MVP — Initial Template Release

**Shipped:** 2026-08-08
**Phases:** 4 (Phases 1-4)
**Plans:** 9 total
**Git Tag:** `v1.0`

### Accomplishments

1. **Local Environment Bootstrap** — Docker-based development environment with Floci emulator, zero AWS credentials required
2. **Run.sh Entrypoint** — Eight subcommands (`up`, `down`, `bootstrap`, `seed`, `job`, `test`, `lint`, `demo`) with preflight checks and Git Bash compatibility
3. **ETL Job with Pure Transforms** — CSV to Parquet transformation with S3A configuration, Glue 5.0 support
4. **Test Suite** — Unit tests (no AWS), integration tests (content assertions via Athena), full offline operation
5. **Terraform Module** — IAC for Glue Job, IAM least-privilege policy, S3 buckets, Data Catalog with compound partitioning
6. **CI Pipeline** — GitHub Actions: lint -> terraform validate -> test suite, plus scheduled drift detection
7. **Public Documentation** — README with onion structure, KNOWN_DIFFERENCES.md (10 local/AWS divergences), CONTRIBUTING.md, LICENSE, issue templates

### Key Stats

- Files changed: 57
- Lines added: 4,593
- Requirements: 38 v1 (all complete)
- Timeline: 2026-08-07 to 2026-08-08 (2 days)

### Archived Artifacts

- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)

---

## v1.1 — Event-Driven ETL & Performance Testing

**Status:** In progress
**Started:** 2026-08-08
**Phases:** 2 (Phase 5-6)

### Goals

1. **Event Trigger & Local Simulation** — Job accepts file parameter, Terraform provisions EventBridge, local trigger simulation validates in Floci
2. **Performance Testing** — Dynamic test data generator, throughput benchmarks, structured JSON logging

### Requirements

| Phase | Requirements |
|-------|-------------|
| Phase 5 | EVT-01, EVT-02, SIM-01, SIM-02, SIM-03, SIM-04, IAC-05, IAC-06, IAC-07 |
| Phase 6 | PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, EVT-03, EVT-04, EVT-05 |

### Archived Artifacts

_(None yet — milestone in progress)_
