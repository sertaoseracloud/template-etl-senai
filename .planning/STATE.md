---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Hexagonal Architecture & Developer Experience
current_phase: 0
status: planning
created: "2026-08-08T23:20:00.000Z"
last_updated: "2026-08-08T23:20:00.000Z"
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
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
