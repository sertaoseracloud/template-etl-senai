# Roadmap: template_etl

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-08-08)
- 🚧 **v1.1** — Phase 5-6 (in progress)
- 🔲 **vNext** — Planned

## Phases

### 🚧 v1.1 Event-Driven ETL & Performance Testing

**Goal:** Enable event-driven ETL with S3-triggered Glue jobs and add dynamic performance test data generation, validated locally in Docker.

#### Summary

- [ ] **Phase 5: Event Trigger & Local Simulation** — Terraform EventBridge infrastructure + local trigger simulation for Floci validation (10 requirements)
- [ ] **Phase 6: Performance Testing** — Dynamic test data generator + performance benchmarks (8 requirements)

---

### Phase 5: Event Trigger & Local Simulation

**Goal:** Job accepts file parameter, local trigger simulation works in Floci, Terraform provisions EventBridge infrastructure.

**Depends on:** Phase 4 (v1.0)

**Requirements:** EVT-01, EVT-02, SIM-01, SIM-02, SIM-03, SIM-04, IAC-05, IAC-06, IAC-07

**Success Criteria** (what must be TRUE):

1. Job accepts `--file-key` parameter and processes only that file
2. Job logs CloudWatch-compatible event (file key, size, timestamp)
3. `./run.sh upload <file>` uploads to S3 and returns the key
4. `./run.sh watch` polls S3 and triggers job with file parameter
5. Full local flow validates: upload → trigger → job → parquet output
6. Documentation explains EventBridge trigger requires real AWS
7. Terraform provisions EventBridge rule for S3 ObjectCreated
8. Terraform provisions IAM role allowing EventBridge to invoke Glue job
9. Terraform Input Transformer passes S3 key as job parameter
10. `terraform fmt -check` and `validate` pass offline

**Plans**: 2 plans ✅
- [x] 05-01-PLAN.md — S3 Trigger Simulation: job --file-key, run.sh upload/watch, local flow validation
- [x] 05-02-PLAN.md — Terraform EventBridge: eventbridge module, IAM role, Input Transformer

**UI hint**: no

---

### Phase 6: Performance Testing

**Goal:** Dynamic test data generator creates configurable datasets, performance tests measure throughput and log structured results.

**Depends on:** Phase 5

**Requirements:** PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, EVT-03, EVT-04, EVT-05

**Success Criteria** (what must be TRUE):

1. `scripts/generate_test_data.py --rows N --output <path>` creates CSV with N rows matching existing schema
2. `./run.sh perf-test <n_rows>` runs full pipeline with generated data
3. Performance test logs execution time and throughput (rows/second)
4. Results logged in structured JSON format
5. Terraform EventBridge rule targets Glue job with file parameter
6. Input Transformer extracts S3 key from EventBridge event
7. IAM policy restricts EventBridge invoke to specific job (least privilege)
8. Local performance test validates the trigger mechanism end-to-end

**Plans**: TBD

**UI hint**: no

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Event Trigger & Local Simulation | 0/2 | Not started | - |
| 6. Performance Testing | 0/N | Not started | - |

---

*Roadmap created: 2026-08-08 for v1.1*
*Last updated: 2026-08-08*
