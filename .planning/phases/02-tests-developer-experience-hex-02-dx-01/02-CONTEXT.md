---
phase: "02"
phase_name: "Tests & Developer Experience (HEX-02, DX-01)"
created: "2026-08-09"
req_ids: "HEX-02.1 - HEX-02.5, DX-01.1 - DX-01.3"
---

# Phase 2 Context: Tests & Developer Experience

## Phase Goal
Rewrites tests with mocks and adds `lint --fix` command.

## Requirements

### HEX-02: Testes com Mocks
- **HEX-02.1**: Reescrever `tests/unit/test_transforms.py` com mocks de Spark DataFrame
- **HEX-02.2**: Criar `tests/unit/test_domain/` com testes de domínio
- **HEX-02.3**: Criar `tests/unit/test_ports/` com testes de contratos
- **HEX-02.4**: Criar `tests/integration/test_adapters/` com fixture de S3
- **HEX-02.5**: Adicionar tests de PySpark real (em Glue container)

### DX-01: Developer Experience
- **DX-01.1**: Adicionar `./run.sh lint --fix` ao run.sh
- **DX-01.2**: Configurar ruff para auto-fix (imports, unused vars, etc)
- **DX-01.3**: Adicionar pre-commit hook (opcional)

## Existing State

### Current Test Structure
```
tests/
├── conftest.py
├── unit/
│   └── test_transforms.py
└── integration/
    └── test_job.py
```

### Current run.sh Commands
```
./run.sh test    # pytest
./run.sh job     # run glue job
./run.sh demo    # demo mode
./run.sh validate # validation scripts
```

## Key Files to Modify
- `tests/unit/test_transforms.py` - Add mocks
- `run.sh` - Add `lint --fix` command
- `pyproject.toml` or `ruff.toml` - Configure ruff

## Decisions
1. Use `unittest.mock` for mocking (stdlib)
2. Use ruff for linting (fast, modern)
3. No pre-commit hook initially (optional DX-01.3)
