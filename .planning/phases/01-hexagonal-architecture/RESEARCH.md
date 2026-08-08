# Research: Hexagonal Architecture for Glue Job

## Context

Refatorar `jobs/csv_to_parquet/job.py` para arquitetura hexagonal (ports & adapters) com:
- Domain layer isolado (sem Spark/Glue imports)
- Ports definidos como ABC/Protocol
- Adapters implementam ports
- DI container conecta componentes
- Testes com mocks

## Current State

### job.py (166 lines)
- Importa awsglue, pyspark
- Faz parsing de argumentos
- Configura S3A
- Orquestra leitura → transformação → escrita
- Logging CloudWatch-compatible

### transforms/csv_to_parquet.py (153 lines)
- `normalize_city_key()` - pure function
- `read_csv()`, `derive_temp_media()`, `add_city_key()`, `write_parquet()`
- Não importa Spark (apenas pyspark.sql)
- Mantido como domain logic

## Target Architecture

```
jobs/
├── domain/
│   ├── __init__.py
│   ├── entities.py          # CsvRecord, ParquetRecord, JobResult
│   ├── value_objects.py     # CityKey, Temperature
│   └── ports/
│       ├── __init__.py
│       ├── primary/
│       │   └── job_port.py  # JobPort (ABC)
│       └── secondary/
│           ├── storage_port.py   # StoragePort (ABC)
│           ├── transform_port.py  # TransformPort (ABC)
│           └── catalog_port.py    # CatalogPort (ABC)
├── application/
│   ├── __init__.py
│   ├── use_cases.py        # ProcessCsvJob, ValidateData
│   └── dto.py              # JobRequest, JobResponse
├── adapters/
│   ├── __init__.py
│   ├── primary/
│   │   └── glue_adapter.py # GlueJobAdapter (implements JobPort)
│   └── secondary/
│       ├── s3_adapter.py    # S3Adapter (implements StoragePort)
│       ├── spark_adapter.py # SparkAdapter (implements TransformPort)
│       └── glue_catalog_adapter.py
├── infrastructure/
│   ├── __init__.py
│   └── di.py               # DI container
└── job.py                  # Thin entrypoint (GlueJobAdapter.run())
```

## Key Decisions

### 1. Domain Layer Isolation
- **Challenge**: PySpark imports são necessários para DataFrame operations
- **Solution**: Domain só usa tipos Python puros (dict, dataclasses). DataFrame é um detail do adapter.

### 2. Ports Definition
```python
# domain/ports/secondary/storage_port.py
from abc import ABC, abstractmethod

class StoragePort(ABC):
    @abstractmethod
    def read_csv(self, path: str) -> list[dict]: ...
    
    @abstractmethod
    def write_parquet(self, data: list[dict], path: str) -> None: ...
```

### 3. DI Container
- Factory pattern simples
- Adaptadores registrados por interface
- Resolução por tipo

### 4. Testing Strategy
- Domain: unittest com pure Python
- Ports: contract tests
- Adapters: integration tests com mocks
- End-to-end: existing Glue container tests

## References

- [Hexagonal Architecture (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://alistair.cockburn.us/reading-on-the-ports-and-adapters-architecture/)
- [Python ABC for Protocol](https://docs.python.org/3/library/abc.html#abc.ABC)
