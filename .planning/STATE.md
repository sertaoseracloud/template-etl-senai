---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Phases
status: planning
last_updated: "2026-08-09T00:19:50.276Z"
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 1
  completed_plans: 1
  percent: 50
current_phase: 0
created: "2026-08-08T23:20:00.000Z"
current_phase_name: Tests & Developer Experience (HEX-02, DX-01)
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Clonar e rodar um comando resulta em ambiente de pea, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

## v1.2 Goals

1. **Arquitetura Hexagonal Full** — Refatorar Glue Job para ports & adapters
2. **Testes com Mocks** — Reescrever usando mocks de Spark
3. **lint --fix** — Adicionar ao run.sh

## Architecture Preview

```
jobs/
├── domain/
│   ├── entities.py          # CsvRecord, ParquetRecord, JobContext
│   └── ports/
│       ├── primary/         # JobPort (driving)
│       └── secondary/       # S3Port, SparkPort (driven)
├── application/
│   └── use_cases.py        # ProcessCsvJob, ValidateData
├── adapters/
│   ├── primary/             # GlueJobAdapter
│   └── secondary/          # S3Adapter, SparkAdapter, GlueCatalogAdapter
└── infrastructure/
    └── di.py               # DI container
```

## Next Steps

- `/gsd-plan-phase 1` — Start Phase 1: Hexagonal Architecture
