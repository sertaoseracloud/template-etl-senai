# Requirements: template_etl — v1.1

**Milestone:** v1.1 Event-Driven ETL & Performance Testing
**Defined:** 2026-08-08
**Core Value:** Clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

## v1.1 Requirements

### S3 Event Trigger (EventBridge + Glue)

- [ ] **EVT-01**: Glue job aceita parâmetro de arquivo (path/key S3) via argumento de linha de comando ou variável de ambiente
- [ ] **EVT-02**: Job registra no CloudWatch o arquivo processado (key, tamanho, timestamp)
- [ ] **EVT-03**: Terraform provisiona regra EventBridge que detecta PutObject no bucket de entrada
- [ ] **EVT-04**: EventBridge target é o Glue Job com parâmetro do arquivo via EventBridge Input Transformer
- [ ] **EVT-05**: IAM policy permite EventBridge invocar Glue Job (estrito ao job específico)

### Local Trigger Simulation (Docker Validation)

- [ ] **SIM-01**: `./run.sh upload <file>` faz upload para S3 local (Floci) e registra o key
- [ ] **SIM-02**: `./run.sh watch` ou mecanismo polling detecta novos arquivos no bucket e dispara job com parâmetro
- [ ] **SIM-03**: Fluxo completo validável localmente: upload -> trigger -> job -> parquet output
- [ ] **SIM-04**: Documentação explica que trigger real (EventBridge) funciona apenas em AWS real

### Dynamic Test Data Generator

- [ ] **PERF-01**: Script `scripts/generate_test_data.py` gera CSV com número configurável de linhas
- [ ] **PERF-02**: Suporta parâmetros: `--rows`, `--output`, `--schema` (match com schema existente)
- [ ] **PERF-03**: `./run.sh perf-test <n_rows>` executa pipeline completo com dado gerado
- [ ] **PERF-04**: Testes de performance registram tempo de execução e throughput (rows/segundo)
- [ ] **PERF-05**: Resultados de performance são logados em formato estruturado (JSON)

### Terraform Updates

- [ ] **IAC-05**: Adiciona EventBridge rule para S3 ObjectCreated trigger
- [ ] **IAC-06**: Adiciona IAM role para EventBridge invocar Glue Job
- [ ] **IAC-07**: Input Transformer no EventBridge passa o S3 key como job parameter

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVT-01 | Phase 5 | — |
| EVT-02 | Phase 5 | — |
| EVT-03 | Phase 5 | — |
| EVT-04 | Phase 5 | — |
| EVT-05 | Phase 5 | — |
| SIM-01 | Phase 5 | — |
| SIM-02 | Phase 5 | — |
| SIM-03 | Phase 5 | — |
| SIM-04 | Phase 5 | — |
| PERF-01 | Phase 6 | — |
| PERF-02 | Phase 6 | — |
| PERF-03 | Phase 6 | — |
| PERF-04 | Phase 6 | — |
| PERF-05 | Phase 6 | — |
| IAC-05 | Phase 5 | — |
| IAC-06 | Phase 5 | — |
| IAC-07 | Phase 5 | — |

---
*Requirements defined: 2026-08-08*
*Last updated: 2026-08-08*
