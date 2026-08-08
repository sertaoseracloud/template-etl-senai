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
6. **CI Pipeline** — GitHub Actions: lint → terraform validate → test suite, plus scheduled drift detection
7. **Public Documentation** — README with onion structure, KNOWN_DIFFERENCES.md (10 local/AWS divergences), CONTRIBUTING.md, LICENSE, issue templates

### Key Stats

- Files changed: 57
- Lines added: 4,593
- Requirements: 38 v1 (all complete)
- Timeline: 2026-08-07 to 2026-08-08 (2 days)

### Archived Artifacts

- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
