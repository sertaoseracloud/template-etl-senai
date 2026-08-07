# Requirements: template_etl

**Defined:** 2026-08-06
**Core Value:** Clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

> **Nota sobre "usuário":** o produto é o template. O usuário é o desenvolvedor que clica em "Use this template" no GitHub e inicia o próprio projeto de ETL a partir dele.

## v1 Requirements

### Ambiente e containers

- [ ] **ENV-01**: Desenvolvedor sobe todo o ambiente local com um único subcomando do `./run.sh`, sem nenhuma credencial AWS configurada
- [x] **ENV-02**: Imagens fixadas por versão no compose — `public.ecr.aws/glue/aws-glue-libs:5` e `floci/floci:1.5.11`, nunca `latest`
- [x] **ENV-03**: O container Glue só executa após o Floci reportar saudável, via `depends_on: condition: service_healthy` (o Floci já traz `HEALTHCHECK` embutido)
- [x] **ENV-04**: Endpoint, região, credenciais e nomes de recursos vêm exclusivamente do `.env`; o `.env.example` documenta todas as variáveis
- [x] **ENV-05**: O repositório traz `.gitattributes` forçando `*.sh text eol=lf`, commitado antes do primeiro script shell
- [x] **ENV-06**: O `run.sh` funciona identicamente no Git Bash (Windows) e no bash (Linux), com `MSYS_NO_PATHCONV=1` guardado por plataforma
- [x] **ENV-07**: O container Glue é invocado como tarefa efêmera (`docker compose run --rm`) atrás de um `profile`, não como serviço longo

### Entrypoint `run.sh`

- [x] **RUN-01**: `./run.sh --help` lista todos os subcomandos disponíveis com descrição
- [x] **RUN-02**: O script expõe os subcomandos `up`, `down`, `bootstrap`, `seed`, `job`, `test`, `lint`, `demo` (oito — revisado na discussão da Fase 1: `seed` separa dados de metadados, `demo` é o comando único que satisfaz o RUN-04)
- [x] **RUN-03**: O script falha rápido (`set -euo pipefail`) e propaga código de saída não-zero em qualquer erro
- [ ] **RUN-04**: Um único comando documentado leva um clone limpo até verde — ambiente de pé, catálogo populado, job executado e testes passando

### Data Catalog

- [ ] **CAT-01**: Um script boto3 versionado cria o database e as tabelas no Glue Data Catalog do Floci
- [ ] **CAT-02**: Partições são registradas via laço de `CreatePartition` — `BatchCreatePartition` não é suportado pelo Floci
- [ ] **CAT-03**: Os schemas das tabelas vivem em uma única fonte de verdade, consumida tanto pelo script de bootstrap quanto pelo Terraform
- [ ] **CAT-04**: O bootstrap é idempotente — rodar de novo não gera erro nem duplicata

### Job de ETL

- [ ] **JOB-01**: O job de exemplo lê CSV do S3 (Floci) e escreve Parquet de volta
- [ ] **JOB-02**: O entrypoint do job é fino — só faz parsing de argumentos e wiring de `GlueContext`; a lógica de transformação vive em módulo puro e importável
- [ ] **JOB-03**: O job usa caminhos `s3a://` explícitos via `from_options` — nunca `from_catalog`, que não é redirecionável para emulador
- [ ] **JOB-04**: O bloco completo de configuração S3A é aplicado como unidade (endpoint, path-style, SSL desabilitado, `SimpleAWSCredentialsProvider`)
- [ ] **JOB-05**: O mesmo código de job roda contra a AWS real trocando apenas variáveis de ambiente

### Testes

- [ ] **TEST-01**: Testes unitários exercitam a lógica de transformação sem Glue e sem AWS
- [ ] **TEST-02**: Fixture de `SparkSession` com escopo de sessão em `conftest.py`, sem depender de `pytest-spark`
- [ ] **TEST-03**: Teste de integração roda o job completo contra o Floci e afirma o **conteúdo** da saída, não apenas o código de saída
- [ ] **TEST-04**: Teste de integração consulta o resultado via Athena, validando o caminho do Data Catalog
- [ ] **TEST-05**: A suíte inteira roda offline, sem nenhuma credencial AWS

### CI

- [ ] **CI-01**: GitHub Actions roda lint e a suíte completa contra o Floci em todo pull request
- [ ] **CI-02**: O workflow invoca subcomandos do `run.sh` em vez de duplicar passos de compose e pytest
- [ ] **CI-03**: Um workflow agendado detecta apodrecimento do template (dependências ou imagens que quebraram sem mudança no repositório)

### Infraestrutura como código

- [ ] **IAC-01**: Terraform provisiona o Glue Job, a IAM role, os buckets S3 e o database/tabela no Data Catalog
- [ ] **IAC-02**: Provider `hashicorp/aws` fixado em `~> 6.0` — versões abaixo de 5.92.0 rejeitam `python_version = "3.11"` com `glue_version = "5.0"`
- [ ] **IAC-03**: A policy IAM é de menor privilégio
- [ ] **IAC-04**: `terraform fmt -check` e `terraform validate` rodam no CI

### Documentação

- [ ] **DOC-01**: README com quick start, estrutura do repositório e seção "como adaptar ao seu projeto"
- [ ] **DOC-02**: `docs/KNOWN_DIFFERENCES.md` documenta as divergências entre local e AWS real — IAM não aplicado, bookmarks inexistentes, sem crawlers nem `StartJobRun`, `from_catalog` indisponível, dialeto do Athena via DuckDB
- [ ] **DOC-03**: LICENSE MIT
- [ ] **DOC-04**: CONTRIBUTING.md e templates de issue
- [ ] **DOC-05**: Passos de renomeação documentados — o que o adotante precisa trocar após usar o template, já que não há cookiecutter
- [ ] **DOC-06**: Badge de status do CI no README

## v2 Requirements

Reconhecidos, mas fora do roadmap atual.

### Exemplos adicionais

- **EX2-01**: Exemplo de job com Apache Iceberg (upsert e time-travel)
- **EX2-02**: Exemplo de leitura via Data Catalog demonstrado contra AWS real, onde `from_catalog` funciona
- **EX2-03**: Segundo job demonstrando particionamento e escrita incremental

### Automação de adoção

- **AD2-01**: GitHub Action de uso único que renomeia o projeto automaticamente após o "Use this template"
- **AD2-02**: Guia de portabilidade de SQL entre DuckDB e Athena/Trino

## Out of Scope

| Feature | Reason |
|---------|--------|
| Emulação de Glue jobs, crawlers, triggers e workflows | Floci não implementa essas APIs. O job roda no container `aws-glue-libs`, que é o comportamento correto para dev local. O crawler é substituído pelo bootstrap boto3. |
| `from_catalog` no fluxo local | O cliente de catálogo do `awsglue` é JVM de código fechado, sem override de endpoint. Verificado por duas trilhas independentes. Vira diferença documentada, não requisito. |
| LocalStack | Community descontinuado em mar/2026 (exige auth token) e Glue Catalog sempre foi Pro. Falha o requisito de custo zero. |
| Job bookmarks locais | Arquiteturalmente impossível — não existe JobRun real localmente. Documentado como exclusivo da AWS. |
| Pipeline medallion e Iceberg no exemplo | O produto é o scaffolding. Exemplo elaborado encarece manutenção e atrapalha quem vai substituí-lo. Movido para v2. |
| Cookiecutter / copier | O reuso é o botão "Use this template". Não introduz ferramenta extra de scaffolding para manter. |
| Makefile e devcontainer | Substituídos por `./run.sh`, que funciona em Git Bash e Linux sem exigir `make`. |
| Jupyter / JupyterLab / Livy | Removidos da imagem Glue 5.0 em relação à 4.0; reintroduzir exigiria um segundo Dockerfile. |
| Estrutura de pastas de data science (`notebooks/`, `models/`, `reports/`) | Convenção de outro domínio; vira scaffolding que o adotante precisa apagar. |
| AWS CDK e SAM/CloudFormation | Terraform é o padrão em data engineering e é agnóstico de estado. |
| Deploy aplicado numa conta AWS real como critério de pronto | Terraform é entregue e validado offline por `init -backend=false`, `fmt -check` e `validate`. `terraform plan` está fora — chama `sts:GetCallerIdentity` e exigiria credencial real, quebrando o critério de "pronto sem conta AWS". |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01 | Phase 1 | Pending |
| ENV-02 | Phase 1 | Complete |
| ENV-03 | Phase 1 | Complete |
| ENV-04 | Phase 1 | Complete |
| ENV-05 | Phase 1 | Complete |
| ENV-06 | Phase 1 | Complete |
| ENV-07 | Phase 1 | Complete |
| RUN-01 | Phase 1 | Complete |
| RUN-02 | Phase 1 | Complete |
| RUN-03 | Phase 1 | Complete |
| RUN-04 | Phase 2 | Pending |
| CAT-01 | Phase 1 | Pending |
| CAT-02 | Phase 1 | Pending |
| CAT-03 | Phase 1 | Pending |
| CAT-04 | Phase 1 | Pending |
| JOB-01 | Phase 2 | Pending |
| JOB-02 | Phase 2 | Pending |
| JOB-03 | Phase 2 | Pending |
| JOB-04 | Phase 2 | Pending |
| JOB-05 | Phase 2 | Pending |
| TEST-01 | Phase 2 | Pending |
| TEST-02 | Phase 2 | Pending |
| TEST-03 | Phase 2 | Pending |
| TEST-04 | Phase 2 | Pending |
| TEST-05 | Phase 2 | Pending |
| CI-01 | Phase 3 | Pending |
| CI-02 | Phase 3 | Pending |
| CI-03 | Phase 3 | Pending |
| IAC-01 | Phase 3 | Pending |
| IAC-02 | Phase 3 | Pending |
| IAC-03 | Phase 3 | Pending |
| IAC-04 | Phase 3 | Pending |
| DOC-01 | Phase 4 | Pending |
| DOC-02 | Phase 4 | Pending |
| DOC-03 | Phase 4 | Pending |
| DOC-04 | Phase 4 | Pending |
| DOC-05 | Phase 4 | Pending |
| DOC-06 | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 38 total
- Mapped to phases: 38 ✓
- Unmapped: 0
- Duplicados entre fases: 0

> **Correção de contagem (2026-08-06):** esta seção declarava 36 requisitos v1. A contagem real dos IDs no corpo do documento é 38 (ENV 7 + RUN 4 + CAT 4 + JOB 5 + TEST 5 + CI 3 + IAC 4 + DOC 6). Nenhum requisito foi perdido — o número no cabeçalho estava errado.

**Distribuição por fase:**

| Fase | Requisitos | Contagem |
|------|------------|----------|
| Phase 1 — Local Environment, Entrypoint & Catalog Bootstrap | ENV-01…ENV-07, RUN-01, RUN-02, RUN-03, CAT-01…CAT-04 | 14 |
| Phase 2 — ETL Job & Green Test Suite | RUN-04, JOB-01…JOB-05, TEST-01…TEST-05 | 11 |
| Phase 3 — Terraform Module & Continuous Integration | IAC-01…IAC-04, CI-01…CI-03 | 7 |
| Phase 4 — Public Documentation & Template Launch | DOC-01…DOC-06 | 6 |

> **Nota sobre RUN-04:** o requisito do "único comando até verde" pertence à Phase 2, não à Phase 1, porque só é satisfeito quando o job e os testes existem. A Phase 1 entrega a superfície do `run.sh` (RUN-01/02/03) com `up`, `down`, `bootstrap` e `lint` funcionando; `job` e `test` são exercitados na Phase 2.

## Open Design Questions

Levantadas pela pesquisa, não resolvidas. Devem ser fechadas no planejamento das fases indicadas.

| Questão | Impacto | Onde resolver |
|---------|---------|---------------|
| Fonte única de verdade do schema entre `bootstrap.py` e Terraform (CAT-03) | Sem isso os dois divergem silenciosamente e a divergência só aparece em produção | **Phase 1** (decisão) — vinculante para a **Phase 3** (consumo pelo Terraform) |
| Compatibilidade do dialeto DuckDB com o SQL do Athena/Trino (TEST-04) | Define se o teste via Athena é confiável ou teatro | **Phase 2** (define o subconjunto SQL portável); a conclusão vai para `KNOWN_DIFFERENCES.md` na **Phase 4** |
| Cache da imagem Glue (~4.77 GB comprimida) no CI | Domina o tempo de CI; medir antes de otimizar | **Phase 3** — medir antes de otimizar |
| Eficácia do `MSYS_NO_PATHCONV` entre versões do Git Bash | Só verificável manualmente no Windows — CI Linux não pega | **Phase 1** — passo de verificação manual explícito, não checagem de CI |
| Fidelidade real das operações do Floci além do `BatchCreatePartition` | Projeto de 2026, sem validação de terceiros; só emerge com uso | Contínuo — levantado na **Phase 1**, mitigado pelo isolamento por endpoint; divergências encontradas vão para `KNOWN_DIFFERENCES.md` na **Phase 4** |

---
*Requirements defined: 2026-08-06*
*Last updated: 2026-08-06 after roadmap creation (traceability populated, contagem corrigida de 36 para 38)*
