# Phase 03: Terraform Module & Continuous Integration - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Esta fase entrega duas coisas: um módulo Terraform que provisiona Glue Job, IAM role, buckets S3 e Data Catalog para AWS real, e dois workflows GitHub Actions — um para pull requests e outro para deteção de apodrecimento em schedule.

O módulo reproduz a topologia já comprovada localmente (Phases 1-2) contra AWS real. O CI repete `./run.sh` em cada PR e periodicamente.

**In scope:** `terraform/` com módulos para glue-job, iam-role, s3-buckets, catalog-table; `.github/workflows/ci.yml` (PR) + `.github/workflows/drift.yml` (schedule); atualização do `catalog/schema/temperaturas.json` para refletir D-12 da Fase 2 (particionamento composto `data_medicao × cidade_key`).

**Out of scope (later phases):** documentação pública, README, CONTRIBUTING, LICENSE, KNOWN_DIFFERENCES.md (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Cache da imagem Glue no CI

- **D-01:** A imagem Glue (~4.77 GB) é guardada em GitHub Actions cache via `docker/build-push-action` com `cache-from: type=gha` e `cache-to: type=gha,mode=max`. **Reversibility:** reversible — trocar para outra estratégia de cache custa uma change no workflow.
- **D-02:** Medir o tempo real de CI antes de otimizar. Small dependencies (boto3, ruff, pytest) são cacheadas independentemente via actions/cache standard — direto fazer, sem medição prévia.

### Estrutura do módulo Terraform

- **D-03:** Módulos em sub-diretórios: `terraform/modules/glue-job/`, `terraform/modules/iam-role/`, `terraform/modules/s3-buckets/`, `terraform/modules/catalog-table/`. O root module `terraform/main.tf` chama os sub-módulos com variáveis. — **Reversibility:** costly — adicionar módulos depois exige re-factoring; manter tudo num main.tf é mais simples mas menos reutilizável.

### Variáveis do módulo Terraform

- **D-04:** Todas as variáveis relevantes expostas com defaults seguros: `project_name`, `aws_region`, `glue_version`, `glue_worker_type`, `glue_timeout_minutes`, `glue_number_of_workers`, `s3_raw_bucket_suffix`, `s3_curated_bucket_suffix`. Defaults cobrem o caso de uso do template sem alteração — o adotante override só o que precisa. — **Reversibility:** costly — adicionar variável depois pode quebrar consumers.

### Jobs CI sequenciais

- **D-05:** Jobs CI em sequência: lint → terraform → test. Falha rápida com diagnóstico claro por job. Total ~6-10 min.

### Terraform regista o Data Catalog

- **D-06:** O Terraform cria o `aws_glue_catalog_database` e o `aws_glue_catalog_table` via `jsondecode(file("catalog/schema/temperaturas.json"))`. As partições são registadas com `aws_glue_partition` em loop. — **Reversibility:** costly — remover depois significa migrar para o script bootstrap.py e manter ambos sincronizados.
- **D-07:** O `catalog/schema/temperaturas.json` é atualizado para refletir D-12 da Fase 2: `partition_keys` ganha `cidade_key`; `partitions` expande para 18 entradas (3 datas × 6 cidades); `columns` ganha `temp_media` como derived column. O Terraform consome este ficheiro como single source of truth (CAT-03, D-01 da Fase 1).

### Schema JSON shape (vinculante de Fase 1)

- **D-08:** O `temperaturas.json` usa a neutral shape definida em D-02/D-03 da Fase 1. Terraform mapeia da forma neutra para `aws_glue_catalog_table` input. Não é a Glue API TableInput shape — é legível por um adotante sem conhecer a API.

### CI workflow invoca run.sh

- **D-09:** O workflow CI invoca `./run.sh lint`, `./run.sh bootstrap`, `./run.sh seed`, `./run.sh job`, `./run.sh test` — não дублирует passos de compose ou pytest. CI-02 satisfied.

### Drift detection workflow

- **D-10:** O workflow agendado executa `./run.sh demo` completo (up → bootstrap → seed → job → test) sem alteração de código. Falha se qualquer imagem ou dependência upstream quebrou sem mudança no repositório.

### IAM least-privilege

- **D-11:** A IAM policy lista só as ações específicas que o job precisa: `s3:GetObject`, `s3:PutObject` nos buckets do projeto, `s3:ListBucket` nos buckets, `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`, `glue:GetTable`, `glue:GetPartitions`, `glue:CreatePartition`. Sem wildcard action. Recursos nomeados com ARNs completos.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Escopo e restrições do projeto
- `.planning/PROJECT.md` — Glue 5.0, Floci, `run.sh`, Terraform, constraints, Out of Scope
- `.planning/REQUIREMENTS.md` — IAC-01…04, CI-01…03 são os requisitos desta fase
- `.planning/ROADMAP.md` §"Phase 3" — goal, success criteria, ordering constraints

### Decisões de fases anteriores que vinculam esta fase
- `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-CONTEXT.md` — D-01 (schema JSON como single source of truth), D-02 (neutral shape), D-03 (tabela completa no schema), D-04 (Spark job NÃO lê o schema), D-16 (nomes derivam de `PROJECT_NAME`)
- `.planning/phases/02-etl-job-green-test-suite/02-CONTEXT.md` — D-06 (subprocess spark-submit), D-12 (particionamento composto `data_medicao × cidade_key` = 18 partitions)

### Pesquisa técnica existente
- `.planning/research/STACK.md` §1 — imagem Glue 5.0, versões fixadas
- `.planning/research/ARCHITECTURE.md` — topologia de containers, compose service shape
- `.planning/research/PITFALLS.md` — credential provider traps

### Documentação externa
- Floci Glue service coverage: https://floci.io/floci/services/glue/
- Floci service overview: https://floci.io/aws/
- Terraform AWS Provider ~> 6.0: https://registry.terraform.io/providers/hashicorp/aws/latest/docs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `catalog/config.py` — as funções de derivação de nomes (`raw_bucket()`, `curated_bucket()`, `database_name()`) replicam-se no Terraform com os mesmos `replace('_', '-')` / `replace('-', '_')`. O Terraform usa `jsondecode(file())` do schema.json; a derivação de nomes deve ser idêntica.
- `catalog/schema/temperaturas.json` — a source of truth atual é de 3 datas × 1 chave de partição. O Terraform vai consumi-la para criar a catalog table. O schema precisa de update (D-07) antes de plan 03-01 começar.
- `./run.sh` — `cmd_up`, `cmd_job`, `cmd_test` são chamados pelo CI. `cmd_lint` também.

### Established Patterns
- **Terraform provider pinning:** `hashicorp/aws ~> 6.0` — versões < 5.92.0 rejeitam `python_version = "3.11"` com `glue_version = "5.0"` (IAC-02).
- **Idempotência de bootstrap vs Terraform:** ambos gerem o catálogo. O script `bootstrap.py` usa `update_table` (correto contra AWS real, Floci cai em `InvalidAction` e loga drift). Terraform usa `create`/`update` resource. Os dois não devem correr em paralelo contra a mesma conta — distinguir env.

### Integration Points
- `catalog/schema/temperaturas.json` → Terraform `aws_glue_catalog_table` (D-06)
- `catalog/config.py` → Terraform variable derivation (mesmos `replace()`)
- `.github/workflows/` → `./run.sh` subcommands (D-09)
- A workflow `ci.yml` precisa de credenciais AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) — usar OIDC role em vez de long-lived keys é a melhor prática mas está fora do scope do template (v2 se的需求)

</code_context>

<specifics>
## Specific Ideas

- **Provider version pinning (IAC-02):** `required_providers` com `hashicorp/aws` pinned `~> 6.0` no root module.
- **Terraform validate offline:** `terraform init -backend=false` + `terraform fmt -check` + `terraform validate` não precisam de credenciais nem de estado remoto — validação completa offline.
- **IAM policy comoficheiro separado:** a policy IAM pode viver em `terraform/modules/iam-role/policy.tf` para legibilidade, sem aumentar a complexidade.

</specifics>

<deferred>
## Deferred Ideas

### IAM OIDC (v2)
- Usar GitHub OIDC role em vez de long-lived AWS access keys nos workflows. Melhora security posture mas adiciona configuração AWS (IAM role com trust policy para GitHub). Prioridade para v2.

### terraform fmt/validate no pre-commit
- Executar `terraform fmt -check` via pre-commit hook. Útil mas fora do scope do CI workflow actual.

### Múltiplos ambientes (dev/staging/prod)
- Terraform workspace ou terragrunt para múltiplos ambientes. Não aplicável a um template com uma única conta AWS.

</deferred>

---

*Phase: 03-Terraform Module & Continuous Integration*
*Context gathered: 2026-08-09*
