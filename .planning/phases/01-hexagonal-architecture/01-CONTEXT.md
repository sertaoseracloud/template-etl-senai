# Context: Phase 1 — Hexagonal Architecture

## Milestone

v1.2 — Hexagonal Architecture & Developer Experience

## Phase Goal

Refatorar Glue Job para arquitetura hexagonal (ports & adapters).

## Requirements (from REQUIREMENTS.md)

### HEX-01.1 - HEX-01.3: Domain Layer
- [ ] HEX-01.1: `domain/` com entidades e value objects
- [ ] HEX-01.2: `domain/ports/` com primary/secondary ports
- [ ] HEX-01.3: `domain/services/` com lógica pura

### HEX-01.4 - HEX-01.5: Application Layer
- [ ] HEX-01.4: `application/` com use cases
- [ ] HEX-01.5: `application/dto/` com DTOs

### HEX-01.6 - HEX-01.8: Adapters Layer
- [ ] HEX-01.6: `adapters/primary/` (GlueJobAdapter)
- [ ] HEX-01.7: `adapters/secondary/` (S3, Spark, Catalog)
- [ ] HEX-01.8: Adapter stubs para testes

### HEX-01.9 - HEX-01.11: Infrastructure
- [ ] HEX-01.9: DI container
- [ ] HEX-01.10: Migrar job.py
- [ ] HEX-01.11: Manter transforms/ como pure functions

## Current Files

```
jobs/csv_to_parquet/
├── job.py              # 166 lines - ENTRY POINT
└── ../../../transforms/
    ├── __init__.py
    └── csv_to_parquet.py  # 153 lines - PURE TRANSFORMS
```

## Architecture Target

```
jobs/csv_to_parquet/
├── domain/
│   ├── entities.py          # CsvRecord, JobResult
│   ├── value_objects.py     # CityKey, Temperature
│   └── ports/
│       ├── primary/job_port.py
│       └── secondary/storage_port.py, transform_port.py
├── application/
│   ├── use_cases.py        # ProcessCsvJob
│   └── dto.py              # JobRequest, JobResponse
├── adapters/
│   ├── primary/glue_adapter.py
│   └── secondary/
│       ├── s3_adapter.py
│       ├── spark_adapter.py
│       └── glue_catalog_adapter.py
├── infrastructure/
│   └── di.py               # DI container
└── job.py                  # Thin entrypoint
```

## Key Invariants

1. **D-08 (v1.0)**: Domain não importa awsglue, boto3, pyspark
2. **Pure transforms**: transforms/ mantido como pure functions
3. **Backward compatible**: Interface CLI (`--JOB_NAME`, `--file-key`) inalterada

## Success Criteria

1. job.py < 50 linhas
2. Domain testável sem Spark
3. Ports com ABC/Protocol
4. DI container conecta adapters
5. `./run.sh test` passa
6. `./run.sh job` funciona idêntico

## Decisions to Make

1. **DI pattern**: Factory vs Injector vs manual
2. **DataFrame handling**: Converter para dict no port ou manter DataFrame?
3. **Error handling**: exceptions vs Result types
