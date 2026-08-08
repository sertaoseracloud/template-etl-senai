# template_etl — Template de ETL com AWS Glue

## What This Is

Um template open-source para iniciar projetos de ETL com AWS Glue 5.0, containerizado e com emulação local completa dos serviços AWS. Quem clona o repositório roda um único comando e vê o ambiente subir, um job PySpark executar de ponta a ponta e os testes passarem — sem precisar de conta AWS, credencial ou qualquer passo manual. É publicado como GitHub template repository, para ser o ponto de partida de novos pipelines de ETL na comunidade.

## Core Value

Clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

## Requirements

### Validated

- ✓ **ENV-01 through ENV-07** — v1.0 (Phase 1)
- ✓ **RUN-01 through RUN-04** — v1.0 (Phase 1-2)
- ✓ **CAT-01 through CAT-04** — v1.0 (Phase 1)
- ✓ **JOB-01 through JOB-05** — v1.0 (Phase 2)
- ✓ **TEST-01 through TEST-05** — v1.0 (Phase 2)
- ✓ **IAC-01 through IAC-04** — v1.0 (Phase 3)
- ✓ **CI-01 through CI-03** — v1.0 (Phase 3)
- ✓ **DOC-01 through DOC-06** — v1.0 (Phase 4)

### Active

_(None — v1.0 complete)_

### Out of Scope

- **Emulação de Glue jobs, crawlers, triggers e workflows** — Floci não implementa essas APIs; o job PySpark executa dentro do container `aws-glue-libs`, que é o comportamento correto para desenvolvimento local. Crawler é substituído pelo script de bootstrap do Catalog.
- **LocalStack** — a edição Community foi descontinuada em março de 2026 (passou a exigir auth token) e os recursos de Glue sempre foram exclusivos da edição Pro. Não atende ao requisito de custo zero.
- **Pipeline medallion (bronze/silver/gold) e Apache Iceberg** — o produto do template é o scaffolding, não o exemplo de negócio. Um exemplo elaborado aumentaria o custo de manutenção e o esforço de quem precisa arrancá-lo para colocar o próprio pipeline.
- **Cookiecutter / copier** — o mecanismo de reuso é o botão "Use this template" do GitHub, com rename manual. Não introduz ferramenta extra de scaffolding.
- **Makefile e devcontainer** — substituídos por `./run.sh`, que funciona igual no Git Bash do Windows e no Linux sem exigir `make` instalado.
- **Deploy real validado em conta AWS** — o Terraform é entregue e revisado, mas "pronto" não exige tê-lo aplicado numa conta de verdade.
- **AWS CDK e SAM/CloudFormation** — Terraform é o padrão de mercado em data engineering e é agnóstico de provedor de estado.

## Context

**Shipped v1.0 MVP** (2026-08-08): 4 phases, 9 plans, 38 requirements, 57 files changed, 4593 insertions.

**Ecossistema e decisões técnicas apuradas durante o questionamento:**

- A imagem citada originalmente (`amazon/aws-glue-libs` no Docker Hub) para na Glue 4.0 (`glue_libs_4.0.0_image_01`, Spark 3.3, Python 3.10). A Glue 5.0 migrou para o ECR Public: `public.ecr.aws/glue/aws-glue-libs:5`. O template alveja 5.0.
- O LocalStack Community foi descontinuado em março de 2026 e passou a exigir auth token, o que eliminou a opção "LocalStack gratuito". No LocalStack, o Glue Data Catalog sempre foi recurso Pro.
- Floci (MIT, v1.5.11, ~18.3k stars) é drop-in do LocalStack: mesma porta 4566, mesmo endpoint, traduz variáveis de ambiente do LocalStack e serve os endpoints `/_localstack/init` e `/_localstack/health`. Suporta 69 serviços AWS.
- Cobertura de Glue no Floci — **suportado**: Data Catalog (CreateDatabase, GetDatabase, GetDatabases, DeleteDatabase, CreateTable, GetTable, GetTables, DeleteTable, CreatePartition, GetPartitions, User-Defined Functions) e Schema Registry (AVRO, JSON, PROTOBUF). **Não suportado**: Glue jobs (CreateJob, StartJobRun, GetJobRun) e crawlers (CreateCrawler, StartCrawler).
- `BatchCreatePartition` **não** consta na lista de operações suportadas do Floci. Se o script de bootstrap ou o job precisar registrar muitas partições, será necessário usar `CreatePartition` em laço — verificar no planejamento.
- Athena no Floci executa via sidecar DuckDB e resolve nomes de tabela pelo Glue Data Catalog. Isso abre a possibilidade de validar a saída do job com SQL real nos testes de integração — capacidade que o LocalStack gratuito nunca ofereceu.

**Ambiente de desenvolvimento:** Windows 10 com Git Bash. Daí a escolha de `./run.sh` em vez de Makefile.

## Constraints

- **Tech stack**: AWS Glue 5.0 (Spark 3.5, Python 3.11), imagem `public.ecr.aws/glue/aws-glue-libs:5` — fixa a versão de Python e das bibliotecas Spark disponíveis.
- **Custo**: zero dependências pagas ou com auth token — foi o critério que eliminou LocalStack e definiu Floci.
- **Offline**: o fluxo local completo não pode exigir conta AWS, credencial real ou acesso à internet além do pull inicial das imagens.
- **Portabilidade**: precisa funcionar em Windows (Git Bash) e Linux — sem `make`, sem dependência de toolchain fora do container.
- **Público**: repositório aberto — sem acoplamento a infraestrutura, contas, naming ou convenções proprietárias.
- **Risco de dependência**: Floci é projeto novo (2026). O acoplamento a ele deve ficar restrito a configuração de endpoint, para que a substituição custe uma variável de ambiente.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Glue 5.0 em vez de 4.0 | Versão atual (Spark 3.5, Python 3.11); 4.0 é a última tag do Docker Hub, mas está defasada | ✓ Implemented — Glue 5.0 with Python 3.11 |
| Floci em vez de LocalStack | LocalStack Community descontinuado em mar/2026 e Glue Catalog é Pro; Floci é MIT, sem token, e cobre Catalog + Schema Registry + Athena | ✓ Implemented — Floci 1.5.11 |
| Job roda no container `aws-glue-libs`, não no emulador | Floci não emula StartJobRun — e executar Spark no container oficial é mais fiel ao runtime real de qualquer forma | ✓ Implemented — `docker compose run --rm` ephemeral task |
| Bootstrap do Catalog via script boto3 | Substitui o crawler ausente; é determinístico, versionado e serve como fonte única de schema que o Terraform também consome | ✓ Implemented — `catalog/bootstrap.py` + `catalog/schema/temperaturas.json` |
| Exemplo mínimo CSV → Parquet | O produto é o scaffolding; exemplo elaborado encarece manutenção e atrapalha quem vai substituí-lo | ✓ Implemented — Simple CSV to Parquet transform |
| Terraform em vez de CDK/SAM | Padrão de mercado em data engineering, agnóstico, estado explícito | ✓ Implemented — `terraform/` module with AWS provider ~> 6.0 |
| `./run.sh` em vez de Makefile | Funciona igual em Git Bash (Windows) e Linux sem exigir `make` | ✓ Implemented — 8 subcommands with MSYS_NO_PATHCONV guard |
| GitHub template repository em vez de cookiecutter | Reuso sem introduzir ferramenta extra de scaffolding para manter | ✓ Implemented — README, CONTRIBUTING, issue templates |
| Endpoint AWS configurável só por env | Isola o risco de maturidade do Floci — trocar de emulador não deve custar refatoração | ✓ Implemented — All config via .env |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-08 after v1.0 MVP milestone*
