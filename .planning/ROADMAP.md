# Roadmap: template_etl

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-08-08) ([archived](milestones/v1.0-ROADMAP.md))
- ✅ **v1.1 Event-Driven ETL & Performance** — Phases 5-6 (shipped 2026-08-08) ([archived](milestones/v1.1-ROADMAP.md))
- ✅ **v1.2 Hexagonal Architecture & DX** — Phases 1-3 (shipped 2026-08-09) ([archived](milestones/v1.2-ROADMAP.md))

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-08-08</summary>

Bootstrap do ambiente local, entrypoint `run.sh`, job ETL com transforms puras,
suíte de testes, módulo Terraform, pipeline CI e documentação pública.

Detalhes: [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Event-Driven ETL & Performance (Phases 5-6) — SHIPPED 2026-08-08</summary>

Trigger por evento com simulação local, provisionamento EventBridge via Terraform,
gerador dinâmico de dados de teste e benchmarks de throughput.

Detalhes: [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

<details>
<summary>✅ v1.2 Hexagonal Architecture & DX (Phases 1-3) — SHIPPED 2026-08-09</summary>

- [x] Phase 1: Hexagonal Architecture (1/1 plan) — completed 2026-08-08
- [x] Phase 2: Tests & Developer Experience (1/1 plan) — completed 2026-08-09
- [x] Phase 3: Integration & Performance Tests (1/1 plan) — completed 2026-08-09

Detalhes: [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

---

## Open Technical Debt

- **WR-03** — risco de OOM em `collect()`; exige mudança arquitetural (aberto desde v1.2 Phase 1)

---

*Next milestone: `/gsd-new-milestone`*
