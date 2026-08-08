# Phase 03: Terraform Module & Continuous Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-09
**Phase:** 03-Terraform Module & Continuous Integration
**Areas discussed:** CI cache, Terraform structure, Terraform variables, CI job parallelism, Terraform + Catalog

---

## CI Cache

| Option | Description | Selected |
|--------|-------------|----------|
| Cache completo | docker/build-push-action + type=gha; medir tempo real primeiro | ✓ |
| Sem cache da Glue image | Pull ECR Public em cada run (~5-10min) | |
| Cache só tooling small | boto3, ruff pip; Glue image sempre pull | |

**User's choice:** Cache completo
**Notes:** Medir tempo real antes de optimizar; caching de small deps (ruff, boto3) é direto.

---

## Terraform Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Sub-módulos por recurso | glue-job, iam-role, s3-buckets, catalog-table | ✓ |
| Root module único | Um main.tf com todos os resources | |
| Main.tf monolithic | Um ficheiro com comments a separar secções | |

**User's choice:** Sub-módulos por recurso
**Notes:** Adequado para adoption de template.

---

## Terraform Variables

| Option | Description | Selected |
|--------|-------------|----------|
| Todas as variáveis relevantes | project_name, region, glue_version, etc. com defaults | ✓ |
| Mínimo possível | Só project_name e região; resto hardcoded | |
| Nenhum default | Adotante forced to fill everything | |

**User's choice:** Todas as variáveis relevantes
**Notes:** Defaults cobrem o caso de uso do template sem modificação.

---

## CI Job Parallelism

| Option | Description | Selected |
|--------|-------------|----------|
| Sequencial | lint → terraform → test; falha rápida, diagnóstico claro | ✓ |
| Paralelo total | Todos jobs em paralelo; mais rápido mas menos diagnóstico | |
| Híbrido | Terraform em série com lint; tests em paralelo | |

**User's choice:** Sequencial
**Notes:** ~6-10 min total.

---

## Terraform + Catalog

| Option | Description | Selected |
|--------|-------------|----------|
| Terraform NÃO regista catálogo | Bootstrap script gere catálogo; Terraform só recursos AWS | |
| Terraform TAMBÉM regista catálogo | Terraform usa jsondecode do schema.json para catalog_table + CreatePartition loop | ✓ |

**User's choice:** Terraform TAMBÉM regista catálogo
**Notes:** Schema.json update: partition_keys ganha cidade_key; partitions expande para 18 entries (3 datas × 6 cidades). Terraform consome o schema.json como single source of truth (CAT-03, D-01 da Fase 1).

---

## Claude's Discretion

Nenhuma — todas as questões tinham recomendações claras e o utilizador escolheu as recomendadas.

## Deferred Ideas

- **IAM OIDC (v2):** GitHub OIDC role em vez de long-lived AWS access keys nos workflows. Melhora security mas adiciona configuração AWS.
- **terraform fmt/validate no pre-commit:** Executar via pre-commit hook — útil mas fora do scope atual.
- **Múltiplos ambientes:** Terraform workspaces ou terragrunt — não aplicável a um template single-account.
