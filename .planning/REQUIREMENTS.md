# Requirements: template_etl

**Defined:** 2026-08-06
**Core Value:** Clonar e rodar um comando resulta em ambiente de pé, job executado e testes verdes — offline, sem credencial AWS, sem passo manual.

> **Nota sobre "usuário":** o produto é o template. O usuário é o desenvolvedor que clica em "Use this template" no GitHub e inicia o próprio projeto de ETL a partir dele.

## v1 Requirements

### Ambiente e containers

- [ ] **ENV-01**: Desenvolvedor sobe todo o ambiente local com um único subcomando do `./run.sh`, sem nenhuma credencial AWS configurada
- [ ] **ENV-02**: Imagens fixadas por versão no compose — `public.ecr.aws/glue/aws-glue-libs:5` e `floci/floci:1.5.11`, nunca `latest`
- [ ] **ENV-03**: O container Glue só executa após o Floci reportar saudável, via `depends_on: condition: service_healthy` (o Floci já traz `HEALTHCHECK` embutido)
- [ ] **ENV-04**: Endpoint, região, credenciais e nomes de recursos vêm exclusivamente do `.env`; o `.env.example` documenta todas as variáveis
- [ ] **ENV-05**: O repositório traz `.gitattributes` forçando `*.sh text eol=lf`, commitado antes do primeiro script shell
- [ ] **ENV-06**: O `run.sh` funciona identicamente no Git Bash (Windows) e no bash (Linux), com `MSYS_NO_PATHCONV=1` guardado por plataforma
- [ ] **ENV-07**: O container Glue é invocado como tarefa efêmera (`docker compose run --rm`) atrás de um `profile`, não como serviço longo

### Entrypoint `run.sh`

- [ ] **RUN-01**: `./run.sh --help` lista todos os subcomandos disponíveis com descrição
- [ ] **RUN-02**: O script expõe os subcomandos `up`, `down`, `bootstrap`, `job`, `test`, `lint`
- [ ] **RUN-03**: O script falha rápido (`set -euo pipefail`) e propaga código de saída não-zero em qualquer erro
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
| Deploy aplicado numa conta AWS real como critério de pronto | Terraform é entregue e validado por `plan`/`validate`, mas aplicar numa conta real não é condição de conclusão. |

## Traceability

Preenchido durante a criação do roadmap.

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 36 ⚠️

## Open Design Questions

Levantadas pela pesquisa, não resolvidas. Devem ser fechadas no planejamento das fases indicadas.

| Questão | Impacto | Onde resolver |
|---------|---------|---------------|
| Fonte única de verdade do schema entre `bootstrap.py` e Terraform (CAT-03) | Sem isso os dois divergem silenciosamente e a divergência só aparece em produção | Planejamento das fases de ambiente e IaC |
| Compatibilidade do dialeto DuckDB com o SQL do Athena/Trino (TEST-04) | Define se o teste via Athena é confiável ou teatro | Planejamento da fase de testes de integração |
| Cache da imagem Glue (~4.77 GB comprimida) no CI | Domina o tempo de CI; medir antes de otimizar | Planejamento da fase de CI |
| Eficácia do `MSYS_NO_PATHCONV` entre versões do Git Bash | Só verificável manualmente no Windows — CI Linux não pega | Planejamento da fase de ambiente |
| Fidelidade real das operações do Floci além do `BatchCreatePartition` | Projeto de 2026, sem validação de terceiros; só emerge com uso | Contínuo; mitigado pelo isolamento por endpoint |

---
*Requirements defined: 2026-08-06*
*Last updated: 2026-08-06 after initial definition*
