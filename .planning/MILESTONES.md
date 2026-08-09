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

**Shipped:** 2026-08-08
**Phases:** 2 (Phase 5-6)
**Git Tag:** `v1.1`

### Goals

1. **Event Trigger & Local Simulation** — Job accepts file parameter, Terraform provisions EventBridge, local trigger simulation validates in Floci
2. **Performance Testing** — Dynamic test data generator, throughput benchmarks, structured JSON logging

### Requirements

| Phase | Requirements |
|-------|-------------|
| Phase 5 | EVT-01, EVT-02, SIM-01, SIM-02, SIM-03, SIM-04, IAC-05, IAC-06, IAC-07 |
| Phase 6 | PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, EVT-03, EVT-04, EVT-05 |

### Archived Artifacts

- [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md)

---

## v1.2 — Hexagonal Architecture & Developer Experience

**Shipped:** 2026-08-09
**Phases:** 3 (Phases 1-3)
**Plans:** 3 total
**Git Tag:** `v1.2`
**Closeout:** verified_closeout (all 3 phases verified)

### Accomplishments

1. **Hexagonal Architecture** — Glue Job refatorado para ports & adapters: domain layer isolado (sem imports de Spark/Glue/boto3), ports como ABC com `@abstractmethod`, adapters primary/secondary, e `job.py` reduzido de 105 para 50 linhas
2. **DI Container** — Injeção de dependências via `infrastructure/di.py`, com `get_container().get_glue_adapter()` resolvendo o wiring; config S3A extraída para `infrastructure/config.py`
3. **Testes com Mocks** — Suítes de domínio e de contratos de ports (17 testes passando) usando mocks de Spark DataFrame, sem exigir container
4. **Testes de Integração** — Fixtures S3 contra o emulador Floci, testes end-to-end do GlueAdapter, 8 testes do DI container e 17 testes de PySpark real
5. **lint --fix** — `./run.sh lint --fix` com auto-fix do ruff configurado
6. **CI/CD** — Pipeline GitHub Actions com 4 jobs (Lint, Test Unit, Test Integration com Floci, Terraform), mais pre-commit hooks

### Key Stats

- Files changed: 95 (excluindo fixtures CSV geradas)
- Lines added: 5,698
- Commits: 50
- Timeline: 2026-08-08 to 2026-08-09 (2 days)

### Known Gaps

- **WR-03 (risco de OOM em `collect()`)** — adiado desde o code review da Phase 1; exige mudança arquitetural. Segue como dívida técnica.
- **Testes end-to-end do GlueAdapter** — verificados a nível de artefato, não de execução: são gated por `@requires_glue` e exigem o container `aws-glue-libs:5`. O job de integração no CI os ignora explicitamente.

### Archived Artifacts

- [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md)
