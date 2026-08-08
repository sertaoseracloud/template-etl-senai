# Requirements: template_etl — v1.1

**Milestone:** v1.1 Event-Driven ETL & Performance Testing
**Defined:** 2026-08-08
**Core Value:** Clonar e rodar um comando resulta em ambiente de pea, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

## v1.1 Requirements

### S3 Event Trigger (EventBridge + Glue)

- [ ] **EVT-01**: Glue job aceita parametro de arquivo (path/key S3) via argumento de linha de comando ou variavel de ambiente
- [ ] **EVT-02**: Job registra no CloudWatch o arquivo processado (key, tamanho, timestamp)
- [ ] **EVT-03**: Terraform provisiona regra EventBridge que detecta PutObject no bucket de entrada
- [ ] **EVT-04**: EventBridge target e o Glue Job com parametro do arquivo via EventBridge Input Transformer
- [ ] **EVT-05**: IAM policy permite EventBridge invocar Glue Job (estrito ao job especifico)

### Local Trigger Simulation (Docker Validation)

- [ ] **SIM-01**: `./run.sh upload <file>` faz upload para S3 local (Floci) e registra o key
- [ ] **SIM-02**: `./run.sh watch` ou mecanismo polling detecta novos arquivos no bucket e dispara job com parametro
- [ ] **SIM-03**: Fluxo completo validavel localmente: upload -> trigger -> job -> parquet output
- [ ] **SIM-04**: Documentacao explica que trigger real (EventBridge) funciona apenas em AWS real

### Dynamic Test Data Generator

- [ ] **PERF-01**: Script `scripts/generate_test_data.py` gera CSV com numero configuravel de linhas
- [ ] **PERF-02**: Suporta parametros: `--rows`, `--output`, `--schema` (match com schema existente)
- [ ] **PERF-03**: `./run.sh perf-test <n_rows>` executa pipeline completo com dado gerado
- [ ] **PERF-04**: Testes de performance registram tempo de execucao e throughput (rows/segundo)
- [ ] **PERF-05**: Resultados de performance sao logados em formato estruturado (JSON)

### Terraform Updates

- [ ] **IAC-05**: Adiciona EventBridge rule para S3 ObjectCreated trigger
- [ ] **IAC-06**: Adiciona IAM role para EventBridge invocar Glue Job
- [ ] **IAC-07**: Input Transformer no EventBridge passa o S3 key como job parameter

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVT-01 | Phase 5 | Pending |
| EVT-02 | Phase 5 | Pending |
| SIM-01 | Phase 5 | Pending |
| SIM-02 | Phase 5 | Pending |
| SIM-03 | Phase 5 | Pending |
| SIM-04 | Phase 5 | Pending |
| IAC-05 | Phase 5 | Pending |
| IAC-06 | Phase 5 | Pending |
| IAC-07 | Phase 5 | Pending |
| PERF-01 | Phase 6 | Pending |
| PERF-02 | Phase 6 | Pending |
| PERF-03 | Phase 6 | Pending |
| PERF-04 | Phase 6 | Pending |
| PERF-05 | Phase 6 | Pending |
| EVT-03 | Phase 6 | Pending |
| EVT-04 | Phase 6 | Pending |
| EVT-05 | Phase 6 | Pending |

---
*Requirements defined: 2026-08-08*
*Roadmap created: 2026-08-08*
