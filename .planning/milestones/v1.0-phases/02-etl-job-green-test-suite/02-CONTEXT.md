# Phase 02: ETL Job & Green Test Suite - Context

**Gathered:** 2026-08-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Esta fase entrega o job de ETL em si e a suíte de testes que prova que ele funciona. É o que
alguém **roda** (`./run.sh job`, `./run.sh test`, `./run.sh demo`) e o que alguém **lê** para
aprender como se estrutura e se testa um job Glue.

É aqui que o core value do projeto aterrissa: um comando documentado leva um clone limpo do nada
até tudo verde — ambiente de pé, catálogo populado, job executado, testes passando — sem conta
AWS, sem credencial, sem passo manual.

**Fora de escopo desta fase:** Terraform (Fase 3), CI (Fase 3), documentação pública e
`KNOWN_DIFFERENCES.md` (Fase 4). Esta fase *alimenta* o KNOWN_DIFFERENCES com achados, mas não o
escreve.

</domain>

<decisions>
## Implementation Decisions

### Asserção via Athena (TEST-04)

- **D-01:** A asserção via Athena executa **três consultas dentro do subconjunto portável**
  DuckDB/Trino: `COUNT(*)` sobre a tabela inteira, `COUNT(*)` com `WHERE` na chave de partição, e
  um agregado (`AVG(temp_media)`) sobre uma partição. Rationale: as três juntas provam de uma vez
  que a tabela resolve pelo Glue Data Catalog, que as partições registradas pelo `bootstrap.py`
  são realmente enxergadas, e que o dado lido é o que o job escreveu. Se qualquer elo quebrar, o
  teste acusa. Asserção linha-a-linha foi rejeitada explicitamente: depende de ordenação e
  formatação de tipos (double, data como string) onde DuckDB e Trino têm mais chance de divergir,
  e um falso negativo num template é caro. Smoke test foi rejeitado como o que o ROADMAP chamou de
  teatro.
- **D-02:** O teste Athena é **bloqueante por padrão**, com `@pytest.mark.athena` e uma linha no
  README documentando `pytest -m "not athena"` como escape hatch. Rationale: `./run.sh demo` verde
  precisa continuar significando que o caminho do catálogo foi exercitado. Mas o PROJECT.md já
  nomeia o Floci como a dependência frágil do projeto, e o Athena dele é DuckDB-backed; o marker é
  a mitigação estrutural na camada de teste, ao custo de um decorator e uma linha de doc. `xfail`
  não-estrito foi rejeitado: um teste que nunca pode falhar não valida nada, e o TEST-04 deixaria
  de ser requisito para virar decoração.
- **D-03:** A fronteira do SQL portável é registrada em **dois lugares**: um bloco de comentário no
  próprio arquivo de teste, listando o que é seguro (`SELECT`/`WHERE`/`COUNT`/agregados básicos) e o
  que é território não testado, mais a entrada formal em `docs/KNOWN_DIFFERENCES.md` na Fase 4.
  Rationale: quem for adicionar um `JOIN` ou uma window function está com o teste aberto na tela,
  não com a documentação.

### Isolamento dos testes e modo de escrita

- **D-04:** O teste de integração **prepara o próprio estado**: limpa o prefixo curated e dispara o
  job antes de afirmar. Rationale: o modo de escrita é `append`, e `COUNT` é exatamente a métrica
  que `append` desestabiliza (agregados como `AVG` sobrevivem a duplicação exata; contagem não).
  Com o teste controlando a precondição, o `COUNT` travado no D-01 vira determinístico
  independentemente de quantas vezes `./run.sh job` rodou antes. Resolve de quebra um problema
  separado: `./run.sh test` sozinho, num ambiente recém-subido, funciona em vez de falhar por não
  achar saída.
- **D-05:** O bloco completo de configuração S3A (JOB-04) vive **no código do job, lido do
  ambiente** — não na invocação `spark-submit` dentro do `run.sh`. Uma função aplica o bloco
  inteiro: endpoint, `path.style.access`, SSL desabilitado, `SimpleAWSCredentialsProvider`,
  `endpoint.region`. Rationale: o JOB-04 pede "aplicado como unidade" e isto o satisfaz
  literalmente; funciona igual sob `spark-submit`, sob pytest, e no Glue real, onde as variáveis
  chegam como job parameters. A alternativa espalharia a configuração por `run.sh`, pelo Terraform
  da Fase 3 e por qualquer teste — três lugares que precisam concordar e divergem em silêncio. O
  grep do critério 5 continua limpo porque os valores vêm do ambiente, não do fonte.
  — **Reversibility:** costly — mover para `--conf` depois significa alterar `run.sh`, o
  `aws_glue_job` do Terraform e a invocação do teste simultaneamente, e a divergência entre eles só
  aparece em runtime.
- **D-06:** O teste de integração dispara o job por **`subprocess spark-submit`**, a mesma
  invocação que `./run.sh job` usa. Rationale: exercita o entrypoint de verdade — parsing de
  argumentos, wiring do `GlueContext`, configuração S3A aplicada num processo Spark limpo. In-process
  seria mais rápido, mas pularia o `spark-submit` (um entrypoint quebrado passaria despercebido) e
  mutaria a `SparkSession` compartilhada da fixture de sessão. Consequência boa e deliberada: o
  teste de integração **não** usa a fixture de Spark, então a fixture do TEST-02 pode ficar pyspark
  puro para os unitários.

### Fronteira unit vs integração

- **D-07:** `./run.sh test` roda **unit + integração, ambos dentro do container Glue**. Rationale: é
  literalmente o critério 4 da fase e o que o RUN-04 exige do `demo` — um comando, tudo verde.
  Rodar os unitários no container também prova que eles não dependem do ambiente do dev. O caminho
  "fora do container" (`pip install pyspark && pytest tests/unit`) é um segundo caminho
  documentado, não o principal.
- **D-08:** A promessa do critério 2 — unitários rodam sem Glue e sem AWS — é garantida por um
  **teste-invariante executável**, não por documentação: uma asserção que falha se qualquer coisa
  sob `tests/unit/` ou `transforms/` importar `awsglue` ou `boto3`. Rationale: sem isso, um import
  conveniente entra num commit futuro e quebra a promessa em silêncio — e o CI, que roda tudo
  dentro do container, nunca acusa. Vira invariante executável em vez de intenção.

### Entrada, saída e particionamento

- **D-09:** O job lê **o prefixo inteiro** `s3a://${PROJECT_NAME}-raw/temperaturas/` — os três CSVs
  que a Fase 1 commitou e que o `seed.py` sobe — como um dataset só: 18 linhas (3 datas × 6
  cidades). **Não existe e não será criado um `data/sample/input.csv`.** O esboço de planos do
  ROADMAP para a Fase 2 menciona `input.csv`; ele é anterior às decisões D-14/D-17/D-18 da Fase 1 e
  está **desatualizado**. Rationale: um job real lê uma partição de arquivos, não um arquivo; e
  introduzir um CSV consolidado contradiria o D-18 e o `data/sample/README.md` já commitado,
  deixando os três CSVs existentes sem uso claro.
- **D-10:** O job **falha explicitamente com mensagem** se o DataFrame de saída estiver vazio, em
  vez de sair 0. Rationale: `./run.sh job` sozinho não tem asserção de conteúdo — só os testes têm.
  Sem essa checagem, um prefixo de entrada errado produz sucesso silencioso, que é o pior modo de
  falha em ETL e o que um template não deveria ensinar.
- **D-11:** O resumo do `demo` (D-10 da Fase 1) imprime **números concretos**: linhas lidas, linhas
  escritas, partições registradas, testes passados e o caminho `s3a://` da saída. Rationale: o
  `demo` é o comando que o README lidera e o primeiro contato de quem clona; "tudo verde" sem número
  nenhum não convence ninguém de que algo real aconteceu.
- **D-12:** O particionamento da tabela curated passa a ser **composto: `data_medicao` +
  `cidade_key`** — 3 datas × 6 cidades = **18 partições registradas**. Rationale: particionamento
  composto é o padrão realista de ETL, e faz o laço de `CreatePartition` virar um laço de verdade
  com 18 iterações — que era exatamente o argumento do D-17 da Fase 1 para ter três. Particionar só
  por cidade foi rejeitado: quebraria o `WHERE data_medicao` travado no D-01 e ensinaria o hábito
  errado (particionar série temporal por entidade em vez de por data).
  **Isto supersede o D-17 da Fase 1** ("três partições") e **modifica artefatos da Fase 1 já
  verificados e commitados** — ver `<code_context>` para o inventário exato do que muda.
  — **Reversibility:** costly — voltar para chave única depois significa alterar o schema JSON, o
  laço do `bootstrap.py`, o `partitionBy` do job, a asserção Athena e o `aws_glue_catalog_table` do
  Terraform da Fase 3 ao mesmo tempo.
- **D-13:** A chave de partição da cidade é **normalizada**: `cidade_key` em minúsculas e sem
  acento (`florianopolis`, `chapeco`, `criciuma`), enquanto a coluna `cidade` preserva a grafia
  correta com acento no dado. Rationale: caminho Hive-style com acento vira `cidade=Florian%C3%B3polis/`
  por URL-encoding, e nem o S3A nem o Athena do Floci têm evidência de fidelidade nisso — é assumir
  risco justamente onde o projeto já sabe que o emulador diverge. Normalizar a chave e preservar o
  nome na coluna é também o que se faz em produção real.
  **Os CSVs de entrada NÃO mudam.** Eles já trazem `cidade` como coluna; `cidade_key` é derivada
  pelo job na escrita, exatamente como `temp_media`.

### Questões técnicas em aberto (o planejador decide)

- **Committer S3A.** O ROADMAP registra como pergunta aberta e a discussão a delegou
  deliberadamente ao planejamento. Contexto da restrição: o committer default faz commit por
  rename, e rename no S3 é copy+delete — o risco de saída incompleta mora em falha e retry, não no
  caminho feliz, e a escala aqui é 18 linhas em 18 partições. A asserção de conteúdo do D-04 é a
  rede. O `magic` committer é o projetado para object stores, mas é **território não testado contra
  o Floci** (depende de suporte a multipart upload no emulador, sem evidência de terceiros).
  Decida com evidência; se optar por não fixar nada, registre a escolha em comentário no job — sem
  isso parece esquecimento em vez de decisão.
  **Nota de processo:** `workflow.research` está `false` na config, então nenhum `RESEARCH.md` será
  produzido por padrão. Se esta decisão merecer evidência nova, o comando é
  `/gsd-plan-phase 02 --research`.

### Claude's Discretion

- Como o `schema.json` representa as 18 partições compostas: listar as 18 combinações
  explicitamente, ou listar datas e cidades e o `bootstrap.py` computar o produto cartesiano. O
  trade-off é explicitude versus repetição; ambos são defensáveis.
- Onde vive a função de normalização de `cidade_key` (módulo `transforms/`, dado que precisa ser
  testável sem Glue) e sua implementação exata (`unicodedata.normalize` versus tabela de
  mapeamento).
- Nomes de arquivos e funções sob `transforms/`, `jobs/` e `tests/`, desde que respeitem o caminho
  `jobs/csv_to_parquet/job.py` que o `run.sh` já invoca.
- Formatação exata do resumo do `demo` (D-11), desde que traga os números nomeados.
- Estrutura interna de `tests/unit/` e `tests/integration/` e nomes das fixtures.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Escopo e restrições do projeto
- `.planning/PROJECT.md` — decisões travadas (Glue 5.0, Floci, `run.sh`, Terraform), restrições, e
  a lista de Out of Scope que limita esta fase. Contém a lista autoritativa de operações Glue
  suportadas pelo Floci.
- `.planning/REQUIREMENTS.md` — RUN-04, JOB-01…05, TEST-01…05 são os requisitos desta fase
- `.planning/ROADMAP.md` §"Phase 2" — goal, critérios de sucesso e as duas perguntas em aberto.
  **Atenção:** o esboço de planos menciona `data/sample/input.csv`, superseded pelo D-09 acima.

### Decisões da Fase 1 que vinculam esta fase
- `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-CONTEXT.md` — D-04
  (`transforms/` puro, o job declara o próprio schema e NÃO lê `catalog/schema/*.json`), D-07
  (imagem Glue só no primeiro `job`, com aviso), D-10 (`demo` = up→job→test→resumo), D-14 (colunas
  do CSV e a razão de `temp_media` ser derivada), D-16 (nomes derivam de `PROJECT_NAME`), D-17
  (três partições — **superseded pelo D-12 acima**), D-18 (CSVs commitados, não gerados)
- `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-VERIFICATION.md` — o que
  foi verificado e com que evidência; inclui os overrides aceitos
- `.planning/phases/01-local-environment-entrypoint-catalog-bootstrap/01-CONCURRENCY-EVIDENCE.log` —
  saída capturada da verificação de concorrência e do achado de fidelidade do `GetTables`

### Pesquisa técnica
- `.planning/research/STACK.md` §1 — a imagem Glue 5.0, o formato `-c "<comando>"` do entrypoint
  que o `test` precisa respeitar, e as versões fixadas
- `.planning/research/STACK.md` §3 — o bloco S3A completo e por que
  `SimpleAWSCredentialsProvider` é obrigatório (modo de falha documentado: 403/AccessDenied)
- `.planning/research/STACK.md` §6 — o padrão de fixture pytest do sample oficial da AWS
  (session-scoped), e por que `pytest-spark` foi rejeitado
- `.planning/research/ARCHITECTURE.md` — topologia de containers, e o esboço do job com
  `mode("overwrite")` que o modo `append` escolhido nesta sessão supersede
- `.planning/research/PITFALLS.md` — armadilhas de credential provider e de path

### Dívidas herdadas que esta fase pode encostar
Três itens devidos ao `docs/KNOWN_DIFFERENCES.md` da Fase 4, registrados no `STATE.md`:
1. Floci não implementa nenhuma operação Glue `Update*` — edição de schema local exige restart do
   emulador. **Relevante aqui:** o D-12 muda o schema, então aplicar a mudança localmente exige
   `./run.sh down && ./run.sh up`, não um `bootstrap` isolado.
2. `docker compose` com path absoluto de container quebra em Git Bash fora do `run.sh`
3. `GetTables` do Floci devolve `[]` para database inexistente, onde o Glue real levanta
   `EntityNotFoundException` — nome de database errado é indistinguível de database vazio

### Documentação externa
- Cobertura Glue do Floci: https://floci.io/floci/services/glue/
- Athena do Floci (4 operações, DuckDB-backed) — a base do D-01 e do D-03

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `catalog/config.py` — **a costura de configuração já existe e deve ser reusada, não duplicada**:
  `raw_bucket()`, `curated_bucket()`, `database_name()`, `endpoint_url()`, `glue_client()`,
  `s3_client()`. Todo nome de recurso deriva de `PROJECT_NAME` em exatamente um lugar. O job e os
  testes de integração devem consumir daqui. Atenção: `config.py` importa `boto3`, então o D-08
  proíbe que `tests/unit/` ou `transforms/` o importem.
- `catalog/schema/temperaturas.json` — fonte única da verdade do schema **para o catálogo**. O D-04
  da Fase 1 é explícito: o job Spark declara o próprio schema e não lê este arquivo.
- `data/sample/*.csv` — três CSVs commitados, 6 cidades cada, header
  `cidade,data_medicao,temp_min,temp_max`. Entrada do job, sem alteração.
- `run.sh` — `cmd_job` e `cmd_test` já existem e já invocam
  `jobs/csv_to_parquet/job.py` e a suíte pytest com o formato `-c "<comando>"` exigido pelo
  entrypoint da imagem Glue. **Os caminhos são contrato**; não renomeie.

### Established Patterns
- **Guard de arquivo antes de docker:** `cmd_job` e `cmd_test` chamam `require_file` no alvo antes
  de tocar em docker, para não disparar o pull de 4,77 GB. Quando os arquivos desta fase
  existirem, esse guard passa a deixar o comando prosseguir — é o mecanismo, não um bug a remover.
- **`run_step` (D-12 da Fase 1):** saída enxuta no sucesso, saída capturada inteira na falha. O
  resumo do D-11 acima convive com isso.
- **Idempotência com diff-and-warn:** `bootstrap.py` mantém `update_table`/`update_database` no
  caminho de código (corretos contra AWS real) e, no `InvalidAction` do Floci, compara e avisa em
  vez de alegar sincronia. Qualquer alteração no `bootstrap.py` por conta do D-12 deve preservar
  esse padrão.

### Integration Points
**O D-12 modifica artefatos da Fase 1 já verificados e commitados. Inventário do que muda:**
- `catalog/schema/temperaturas.json` — `partition_keys` ganha `cidade_key`; a lista `partitions`
  passa de 3 para 18 entradas (ou passa a ser derivada — ver Claude's Discretion)
- `catalog/bootstrap.py` — o laço de `CreatePartition` passa a registrar 18 partições com dois
  valores cada. Preservar o padrão diff-and-warn e a proibição de `delete_*`.
- `data/sample/README.md` — a seção de colunas documenta `data_medicao` como a chave de partição;
  precisa mencionar `cidade_key` derivada
- Verificar se `.planning/ROADMAP.md` §"Phase 1" critério 2 e o D-17 do `01-CONTEXT.md` merecem
  nota de supersessão, como o D-11 da Fase 1 fez com o RUN-02

**Novos artefatos desta fase:** `transforms/`, `jobs/csv_to_parquet/job.py`, `tests/conftest.py`,
`tests/unit/`, `tests/integration/`. Nenhum existe ainda.

</code_context>

<specifics>
## Specific Ideas

- **Escopo do projeto é simulação de ambiente para fins acadêmicos** (decidido pelo operador nesta
  sessão). Isso justifica o dataset fixo de três datas e o job reprocessando sempre as mesmas datas
  semeadas — catálogo e disco não divergem, e o laço de `CreatePartition` existe para *demonstrar*
  o laço, não para operar um pipeline diário.
- **Modo de escrita é `append`** (decidido pelo operador nesta sessão).
  `spark.sql.sources.partitionOverwriteMode` fica N/A por consequência.
  **Consequência a documentar no README da Fase 4:** com `append`, rodar `./run.sh demo` duas vezes
  sem `down` no meio duplica linhas na mesma partição. Não é defeito, é o modo escolhido — mas
  precisa estar escrito, ou o aluno vê a contagem dobrar e acha que quebrou algo.
- O dataset é sintético e rotulado como tal (D-15 da Fase 1). Cidades: Florianópolis, Joinville,
  Blumenau, Chapecó, Lages, Criciúma.

</specifics>

<deferred>
## Deferred Ideas

Nenhuma ideia fora de escopo surgiu — a discussão ficou dentro da fronteira da fase.

Dois itens levantados e deliberadamente **não** discutidos, disponíveis se o planejamento os
alcançar:
- Se o teste deve conferir que não sobraram arquivos temporários de commit no bucket (relacionado à
  questão em aberto do committer)
- Onde ficam os resultados de consulta do Athena e se o template expõe um helper de consulta em vez
  de `boto3` inline no teste

</deferred>

---

*Phase: 02-etl-job-green-test-suite*
*Context gathered: 2026-08-07*
