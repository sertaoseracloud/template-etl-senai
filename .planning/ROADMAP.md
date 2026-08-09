# Roadmap: template_etl

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-08-08)
- ✅ **v1.1** — Event-Driven ETL & Performance Testing ([archived](milestones/v1.1-ROADMAP.md))
- 🚧 **v1.2** — Hexagonal Architecture & Developer Experience (in progress)

## v1.2 Phases

### Phase 1: Hexagonal Architecture (HEX-01)

**Goal:** Refatorar Glue Job para arquitetura hexagonal com ports & adapters.

**Requirements:** HEX-01.1 - HEX-01.11

**Success Criteria:**

1. Domain layer isolado (sem Spark/Glue imports)
2. Ports definidos como ABC/Protocol
3. Adapters implementam ports
4. DI container conecta componentes
5. job.py é thin entrypoint
6. transform/ mantido como pure functions

### Phase 2: Tests & Developer Experience (HEX-02, DX-01)

**Goal:** Reescrever testes com mocks e adicionar lint --fix.

**Requirements:** HEX-02.1 - HEX-02.5, DX-01.1 - DX-01.3

**Success Criteria:**

1. Testes com mocks de Spark DataFrame
2. Domain e ports testados isoladamente
3. `./run.sh lint --fix` funciona
4. ruff auto-fix configurado

---

## Progress

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Hexagonal Architecture | 1 | Complete | 2026-08-08 |
| 2. Tests & DX | 1 | Complete | 2026-08-09 |
| 3. Integration & Performance Tests | 1 | Planned | — |

---

### Phase 3: Integration & Performance Tests

**Goal:** Complete deferred integration tests and add performance testing.

**Plans:**
- [ ] 03-01-PLAN.md — Integration tests with S3 fixture and PySpark real tests

**Requirements:** HEX-02.4, HEX-02.5, DX-01.3

**Success Criteria:**

1. Integration tests with S3 fixture (Floci)
2. PySpark real tests in Glue container
3. Pre-commit hook configured (optional)
4. CI/CD pipeline stub

---

*Roadmap created: 2026-08-08*
