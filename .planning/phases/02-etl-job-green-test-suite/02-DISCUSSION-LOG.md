# Phase 02: ETL Job & Green Test Suite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-07
**Phase:** 02-etl-job-green-test-suite
**Areas discussed:** Asserção via Athena (TEST-04), Isolamento dos testes com append, Committer S3A e integridade de saída, Fronteira unit vs integração, Entrada e particionamento

---

## Asserção via Athena (TEST-04)

### O que a asserção afirma de fato

| Option | Description | Selected |
|--------|-------------|----------|
| COUNT + WHERE na partição + 1 agregado | Dentro do subconjunto portável; prova que a tabela resolve pelo catálogo, que as partições são enxergadas, e que o dado é o que o job escreveu | ✓ |
| Só smoke: a consulta responde | Risco de dialeto quase zero, mas passa mesmo com números errados ou partições faltando | |
| Conteúdo completo, linha a linha | Asserção mais forte, mas depende de ordenação e precisão de tipos onde DuckDB e Trino divergem | |

**User's choice:** COUNT + WHERE na partição + 1 agregado
**Notes:** O ROADMAP havia marcado esta questão como determinante de "validação real ou teatro". A opção escolhida é a que fica dentro do subconjunto portável documentado pela pesquisa (`SELECT`/`WHERE`/`COUNT`/agregados básicos) sem cair no smoke test.

### Comportamento em caso de falha do Athena do Floci

| Option | Description | Selected |
|--------|-------------|----------|
| Bloqueante + marker para deselecionar | Roda e derruba por padrão; `@pytest.mark.athena` e `-m "not athena"` documentado como escape hatch | ✓ |
| Bloqueante, sem escape | Mais estrito, mas deixa quem clonou com vermelho que não causou e não sabe contornar | |
| Informacional, nunca derruba | Suíte sempre verde; na prática transforma o TEST-04 em decoração | |

**User's choice:** Bloqueante + marker para deselecionar
**Notes:** Consistente com o PROJECT.md, que nomeia o Floci como a dependência frágil e prescreve mitigação estrutural.

### Onde a fronteira do SQL portável fica registrada

| Option | Description | Selected |
|--------|-------------|----------|
| Comentário no teste + KNOWN_DIFFERENCES | A informação fica onde a decisão de estender é tomada | ✓ |
| Só no KNOWN_DIFFERENCES | Arquivo de teste limpo, informação distante | |
| Nada explícito | Transfere ao adotante a descoberta de um limite já conhecido | |

**User's choice:** Comentário no teste + KNOWN_DIFFERENCES

---

## Isolamento dos testes com append

### Quem garante o estado inicial

| Option | Description | Selected |
|--------|-------------|----------|
| O teste prepara o próprio estado | Limpa o prefixo curated e dispara o job; determinístico e faz `./run.sh test` funcionar sozinho | ✓ |
| Depende da ordem do demo | Mais simples, mas `./run.sh test` isolado falha ou passa conforme o histórico da sessão | |
| Afirmar só o que é invariante | Nunca depende do histórico, mas perde a capacidade de detectar duplicação | |

**User's choice:** O teste prepara o próprio estado
**Notes:** Observação que motivou a pergunta — `COUNT` é exatamente a métrica que `append` desestabiliza, enquanto agregados como `AVG` sobrevivem a duplicação exata. O `COUNT` travado na área anterior só vale se alguém controlar a precondição.

### Onde vive o bloco de configuração S3A

| Option | Description | Selected |
|--------|-------------|----------|
| No código do job, lendo do ambiente | Um lugar só; funciona sob spark-submit, sob pytest e no Glue real | ✓ |
| No spark-submit dentro do run.sh | Fonte do job limpo, mas configuração espalhada por run.sh + Terraform + testes | |

**User's choice:** No código do job, lendo do ambiente

### Como o teste dispara o job

| Option | Description | Selected |
|--------|-------------|----------|
| subprocess spark-submit | Exercita o entrypoint real — args, GlueContext, S3A em processo limpo | ✓ |
| In-process, importando o job | Mais rápido e traceback legível, mas pula o spark-submit e muta a sessão compartilhada | |

**User's choice:** subprocess spark-submit
**Notes:** Consequência deliberada e bem-vinda — o teste de integração não usa a fixture de Spark, então a fixture do TEST-02 fica pyspark puro para os unitários.

---

## Committer S3A e integridade de saída

| Option | Description | Selected |
|--------|-------------|----------|
| Não fixar, mas documentar por quê | Usa o default e trata a asserção de conteúdo como rede | |
| Fixar o magic committer | Projetado para object stores, mas território não testado contra o Floci | |
| Deixar o planejador investigar | Registra como questão aberta no CONTEXT; decisão vem com evidência levantada na hora | ✓ |

**User's choice:** Deixar o planejador investigar
**Notes:** Foi sinalizado ao operador que `workflow.research` está `false` na config, então nenhum RESEARCH.md será produzido por padrão — se a decisão merecer evidência nova, o comando é `/gsd-plan-phase 02 --research`.

---

## Fronteira unit vs integração

### O que `./run.sh test` executa

| Option | Description | Selected |
|--------|-------------|----------|
| Unit + integração, ambos no container | Um comando, tudo verde — critério 4 da fase e RUN-04 | ✓ |
| Só integração | Suíte mais rápida, mas `demo` verde deixa de significar "todos os testes passam" | |
| Unit + integração, saídas separadas | Mais legível na falha, mas duas invocações e mais verbosidade contra o D-12 da Fase 1 | |

**User's choice:** Unit + integração, ambos no container

### Como a promessa "sem Glue e sem AWS" é garantida

| Option | Description | Selected |
|--------|-------------|----------|
| Teste que falha se tests/unit importar awsglue | Invariante executável em vez de promessa | ✓ |
| Só documentar no README | Zero código extra, mas um import futuro quebra a promessa em silêncio | |
| Separação por diretório basta | Estado natural sem esforço, mesma fragilidade sem a documentação | |

**User's choice:** Teste que falha se tests/unit importar awsglue

---

## Entrada e particionamento

> Área aberta após as quatro iniciais, motivada por uma inconsistência encontrada durante a discussão: o esboço de planos do ROADMAP lista `data/sample/input.csv` como artefato do plano 02-02, mas a Fase 1 já criou três CSVs (`temperaturas_2026-01-15/16/17.csv`) e o `seed.py` já os sobe. Não existe nenhum `input.csv`.

### O que o job lê como entrada

| Option | Description | Selected |
|--------|-------------|----------|
| O prefixo inteiro, os três CSVs | 18 linhas, exatamente o COUNT travado; padrão realista de ETL | ✓ |
| Introduzir um input.csv consolidado | Contradiz D-18 e o README da Fase 1, deixa os três CSVs sem uso claro | |

**User's choice:** O prefixo inteiro, os três CSVs
**Notes:** O esboço do ROADMAP fica marcado como desatualizado no CONTEXT.md (D-09).

### Falha em zero linhas

| Option | Description | Selected |
|--------|-------------|----------|
| Sim, falhar com mensagem | `./run.sh job` sozinho não tem asserção de conteúdo; sem isso, prefixo errado vira sucesso silencioso | ✓ |
| Não, deixar os testes pegarem | Job mais enxuto, mas quem roda só `job` vê verde com bucket vazio | |

**User's choice:** Sim, falhar com mensagem ("siga o recomendado")
**Notes:** Na mesma resposta o operador adicionou um pedido novo — particionamento considerando as cidades de Santa Catarina — que abriu as duas perguntas seguintes.

### Resumo do `demo`

| Option | Description | Selected |
|--------|-------------|----------|
| Números concretos | Linhas lidas/escritas, partições, testes, caminho da saída | ✓ |
| Uma linha por etapa | Consistente com o D-12, mas não mostra que o dado existe | |

**User's choice:** Números concretos

### Como particionar por cidade

| Option | Description | Selected |
|--------|-------------|----------|
| Composto: data_medicao + cidade | 18 partições; preserva o WHERE por data e faz o laço de CreatePartition ser um laço de verdade | ✓ |
| Só cidade, trocando a data | Quebraria a asserção Athena travada e ensinaria a particionar série temporal por entidade | |

**User's choice:** Composto: data_medicao + cidade
**Notes:** Foi comunicado ao operador, antes da escolha, que isto reabre artefatos da Fase 1 já verificados e commitados (`schema.json`, `bootstrap.py`) e supersede o D-17 da Fase 1. O inventário do que muda está no `<code_context>` do CONTEXT.md.

### Acentos nos nomes de cidade no caminho da partição

| Option | Description | Selected |
|--------|-------------|----------|
| Normalizar a chave, manter o nome na coluna | Evita `%C3%B3` no caminho S3 sem perder a grafia correta | ✓ |
| Usar o nome acentuado direto | Menos código, mas assume risco de encoding onde o emulador não tem evidência de fidelidade | |

**User's choice:** Normalizar a chave, manter o nome na coluna
**Notes:** Levantado proativamente — Florianópolis, Chapecó e Criciúma têm acento, e caminho Hive-style com acento vira URL-encoding, uma fonte clássica de dor no S3A e no Athena, especialmente contra emulador.

---

## Claude's Discretion

- Como o `schema.json` representa as 18 partições compostas (18 entradas explícitas versus produto cartesiano computado no `bootstrap.py`)
- Onde vive a função de normalização de `cidade_key` e sua implementação (`unicodedata.normalize` versus tabela de mapeamento)
- Nomes de arquivos e funções sob `transforms/`, `jobs/` e `tests/`, respeitado o caminho `jobs/csv_to_parquet/job.py` que o `run.sh` já invoca
- Formatação exata do resumo do `demo`, desde que traga os números nomeados
- Estrutura interna de `tests/unit/` e `tests/integration/` e nomes das fixtures

## Deferred Ideas

Nenhuma ideia fora de escopo surgiu — a discussão ficou dentro da fronteira da fase.

Dois itens levantados e deliberadamente não discutidos:
- Se o teste deve conferir que não sobraram arquivos temporários de commit no bucket (relacionado à questão aberta do committer)
- Onde ficam os resultados de consulta do Athena e se o template expõe um helper de consulta em vez de `boto3` inline no teste
