---
name: v1.2
milestone: v1.2
milestone_name: Hexagonal Architecture & Developer Experience
status: in_progress
created: "2026-08-08T23:20:00.000Z"
---

# Requirements: v1.2 — Hexagonal Architecture & Developer Experience

**Milestone:** v1.2
**Started:** 2026-08-08
**Core Value:** Refatorar Glue Job para arquitetura hexagonal (ports & adapters), reescrever testes com mocks, adicionar lint --fix

---

## HEX-01: Arquitetura Hexagonal (Full)

### Domain Layer
- [ ] **HEX-01.1**: Criar `domain/` com entidades e value objects (CsvRecord, ParquetRecord, JobContext)
- [ ] **HEX-01.2**: Criar `domain/ports/` com primary/secondary ports como ABC/Protocol
- [ ] **HEX-01.3**: Criar `domain/services/` com lógica de negócio pura (sem Spark/Glue imports)

### Application Layer
- [ ] **HEX-01.4**: Criar `application/` com use cases (ProcessCsvJob, ValidateData)
- [ ] **HEX-01.5**: Criar `application/dto/` com Data Transfer Objects

### Adapters Layer
- [ ] **HEX-01.6**: Criar `adapters/primary/` (GlueJobAdapter - entrypoint)
- [ ] **HEX-01.7**: Criar `adapters/secondary/` (S3Adapter, SparkAdapter, GlueCatalogAdapter)
- [ ] **HEX-01.8**: Implementar adapter stubs para testes

### Infrastructure
- [ ] **HEX-01.9**: Configurar DI container (simple factory/factory pattern)
- [ ] **HEX-01.10**: Migrar job.py para GlueJobAdapter (薄 entrypoint)
- [ ] **HEX-01.11**: Manter transforms/ como pure domain functions

---

## HEX-02: Testes com Mocks

### Unit Tests
- [x] **HEX-02.1**: Reescrever `tests/unit/test_transforms.py` com mocks de Spark DataFrame
- [x] **HEX-02.2**: Criar `tests/unit/test_domain/` com testes de domínio
- [x] **HEX-02.3**: Criar `tests/unit/test_ports/` com testes de contratos

### Integration Tests
- [ ] **HEX-02.4**: Criar `tests/integration/test_adapters/` com fixture de S3
- [ ] **HEX-02.5**: Adicionar tests de PySpark real (em Glue container)

---

## Phase 3: Integration & Performance Tests

### Integration Tests
- [ ] **INT-03.1**: Criar `tests/integration/test_adapters/` com fixture de S3 (Floci)
- [ ] **INT-03.2**: Testar GlueAdapter end-to-end com mock S3
- [ ] **INT-03.3**: Testar DI container com mock adapters

### PySpark Real Tests
- [ ] **INT-03.4**: Adicionar tests de PySpark real no Glue container
- [ ] **INT-03.5**: Validar transform functions com dados reais

### Developer Experience
- [ ] **DX-03.1**: Configurar pre-commit hook (opcional)
- [ ] **DX-03.2**: Adicionar CI/CD pipeline stub

---

## DX-01: Developer Experience

### Lint & Format
- [ ] **DX-01.1**: Adicionar `./run.sh lint --fix` ao run.sh
- [ ] **DX-01.2**: Configurar ruff para auto-fix (imports, unused vars, etc)
- [ ] **DX-01.3**: Adicionar pre-commit hook (opcional)

---

## Traceability

| Requirement | Phase | Status |
|------------|-------|--------|
| HEX-01.1 - HEX-01.11 | Phase 1 | ✅ Complete |
| HEX-02.1 - HEX-02.3 | Phase 2 | ✅ Complete |
| HEX-02.4 - HEX-02.5 | Phase 3 | Pending |
| DX-01.1 - DX-01.2 | Phase 2 | ✅ Complete |
| DX-01.3, DX-03.1 | Phase 3 | Pending |
| INT-03.1 - INT-03.5 | Phase 3 | Pending |
