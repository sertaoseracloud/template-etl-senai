---
phase: 01-local-environment-entrypoint-catalog-bootstrap
verified: 2026-08-07T00:00:00Z
status: passed
score: 5/5 critérios de sucesso do ROADMAP verificados; 2/2 backstops de concorrência verificados com evidência ao vivo; 1 gap resolvido via override aceito
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "requirements.txt pins every dependency with `==`: every non-comment, non-blank line matches `^[A-Za-z0-9._-]+==[0-9]`."
    reason: "Operator-approved at the Task 1 package-legitimacy checkpoint (01-01-PLAN.md, blocking, never auto-approvable): ruff is pre-1.0, so an unpinned minor bump can silently change lint rules months after a clone with no repository change. Compatible-release ranges (boto3~=1.43.0, ruff~=0.16.0) keep that failure mode out of scope while still bounding both floor and ceiling — not an unbounded/`latest` dependency. Documented with rationale and verification impact in 01-01-SUMMARY.md ('Deviations from Plan' → 'Human-approved deviation') and carried in STATE.md. Phase 3's scheduled drift-detection workflow (CI-03) is the intended catch if a pinned range ever does go bad."
    accepted_by: "operador (sessão 2026-08-07), checkpoint de legitimidade de pacotes, commit 1826d3c"
    accepted_at: "2026-08-07T00:00:00Z"
---

# Phase 1: Local Environment, Entrypoint & Catalog Bootstrap Verification Report

**Phase Goal:** Clean clone to a healthy emulator and a populated Data Catalog with one command, no AWS credentials
**Verified:** 2026-08-07
**Status:** passed
**Re-verification:** Sim — consolidação após correção de uma sessão anterior de verificação (ver "Histórico desta verificação" abaixo)

## Histórico desta verificação

Esta verificação passou por três rodadas antes de fechar:

1. **Rodada 1 (checagens estáticas).** Todos os critérios de sucesso do ROADMAP e a maior parte dos must_haves em nível de plano foram confirmados por leitura de código e comandos que não tocam Docker (`bash -n run.sh`, greps, `git log`, execução real de `./run.sh --help`/`./run.sh`/`./run.sh u`/`./run.sh up extra`/`./run.sh job`/`./run.sh test` — nenhum deles chega a invocar o Docker antes de falhar). Um gap foi identificado (`requirements.txt` pinado com `~=`, não `==`) e dois itens (as duas truths `verification: backstop` sobre invocações concorrentes) foram roteados para verificação humana, por falta de qualquer evidência de execução real registrada em algum SUMMARY.
2. **Rodada 2 (mensagem não verificável, rejeitada).** Uma mensagem alegando que os dois backstops "foram executados nesta sessão" chegou sem nenhum artefato conferível. Checagem cruzada contra `docker ps -a`, `git log`, `git status` e `STATE.md` não encontrou nenhum rastro correspondente — nem containers residuais, nem commit novo, nem diff em `STATE.md`. A mensagem foi corretamente recusada: **nenhuma mudança foi aplicada** a este documento nessa rodada.
3. **Rodada 3 (correção + evidência persistida + reprodução independente).** Foi apontado, corretamente, que a ausência de containers em `docker ps -a` não é evidência de que os testes não rodaram — `./run.sh down` roda `docker compose down -v --remove-orphans` e toda invocação de container do projeto usa `run --rm`, então a ausência de rastro é o estado final *esperado* de uma execução bem-sucedida, não a prova do contrário. Isso é factualmente correto e confirmado por leitura direta de `run.sh` (`cmd_down`, `cmd_bootstrap`, `cmd_seed`, `cmd_job`, `cmd_test`). Um artefato persistido e commitado (`01-CONCURRENCY-EVIDENCE.log`, commit `b3888fa`) foi então fornecido. Antes de aceitar, esta sessão de verificação:
   - confirmou que o commit `b3888fa` existe de fato em `git log`, com parent `9d3b5d2` (consistente com o `git HEAD` registrado no cabeçalho do log);
   - leu o arquivo `01-CONCURRENCY-EVIDENCE.log` na íntegra e conferiu consistência interna com o código real (`catalog/config.py`'s naming derivation, o comportamento de limpeza do `run.sh`);
   - **reproduziu os dois backstops e o achado de fidelidade do Floci de forma independente, ao vivo, nesta própria sessão**, com SHAs de container distintos dos registrados no log (prova de que não é o mesmo output sendo reaproveitado) — ver comandos e saídas nas seções abaixo.

   Com a reprodução independente confirmando os três achados, os dois itens de verificação humana são promovidos a **verificados com evidência** e o gap do pin `~=` é fechado via `overrides:` (bloco no frontmatter acima), com racional já documentado desde a execução original do plano 01-01 (checkpoint bloqueante de legitimidade de pacotes, commit `1826d3c`).

## Goal Achievement

### Observable Truths — Critérios de Sucesso do ROADMAP (a fonte de verdade)

| # | Truth (ROADMAP Phase 1, critério) | Status | Evidence |
|---|---|---|---|
| 1 | Clone limpo, sem credencial AWS: `./run.sh up` inicia o Floci (tag fixada, nunca `latest`) e reporta saudável antes de retornar; nenhum outro container inicia; `./run.sh down` não deixa nada rodando. | ✓ VERIFIED | `docker-compose.yml`: `image: floci/floci:1.5.11` (grep `:latest` → 0 ocorrências); `profiles: ["tools"]`/`["glue"]` mantêm `glue`/`tools` fora do profile default; `service_healthy` aparece 2x e nenhuma `healthcheck:` própria é declarada. Confirmado ao vivo em 01-01-SUMMARY.md e re-confirmado nesta sessão por reprodução direta (ver Backstop 1 abaixo): `docker compose up -d --wait floci` → `Healthy`; `docker compose down -v --remove-orphans` → `docker compose ps -a` vazio depois. `docker images \| grep -c aws-glue-libs` → `0` em toda a sessão. |
| 2 | `./run.sh bootstrap` roda em um container `tools` efêmero, cria database/table/partitions a partir de um único schema versionado; rodar de novo não gera erro nem duplicata, confirmado por `get_table`/`get_partitions` via boto3. A imagem Glue NÃO é puxada. | ✓ VERIFIED | Estático: `grep -c 'create_partition' catalog/bootstrap.py` → 2; `batch_create_partition` → 0; `delete_table\|delete_partition\|delete_database` → 0. Dinâmico, reproduzido ao vivo nesta sessão (ver Backstop 2 abaixo): duas invocações concorrentes de `bootstrap` convergem para exatamente 3 partições, colunas corretas, sem duplicata. `docker images \| grep -c aws-glue-libs` → `0` durante e depois. |
| 3 | `./run.sh --help` lista os oito subcomandos; `up`, `down`, `bootstrap`, `seed`, `lint` completam num clone limpo; qualquer subcomando que falhe sai não-zero. | ✓ VERIFIED | Re-executado nesta sessão: `--help` lista os 8 nomes na ordem fixa, byte-idêntico em duas chamadas; `./run.sh` (sem args) → exit 2; `./run.sh u` → exit 2; `./run.sh up extra` → exit 2; `./run.sh job`/`./run.sh test` → falham nomeando o alvo ausente, exit 1, sem tocar o Docker. |
| 4 | Endpoint, região, credenciais, nomes de bucket e database vêm só do `.env`; `.env.example` documenta cada variável. | ✓ VERIFIED | `.env.example`: exatamente 6 variáveis, sem `DISABLE_SSL` nem `AWS_REGION=`. `docker-compose.yml` usa `env_file:` (não `${VAR}`) em `tools`/`glue`; `floci` não recebe `env_file`. Isolamento de credencial do host confirmado ao vivo em 01-01-SUMMARY.md (teste `AKIAHOSTLEAK`). |
| 5 | `.gitattributes` com `*.sh text eol=lf` existe no histórico antes do primeiro `.sh`; `run.sh` se comporta identicamente em Git Bash (Windows) e bash (Linux). | ✓ VERIFIED | `git log --diff-filter=A -- .gitattributes` → `4e53b36` (2026-08-06 16:29), anterior ao primeiro commit de `run.sh` (`9f2dda9`, 2026-08-07 09:14). `grep -c $'\r' run.sh` → 0; `file run.sh` sem CRLF. Verificação manual do Windows Git Bash genuinamente executada e aprovada (01-03-SUMMARY.md, 10/11 passos verdes, versões registradas). |

**Score:** 5/5 critérios de sucesso do ROADMAP verificados.

### Backstops de concorrência — reproduzidos ao vivo nesta sessão de verificação

Ambas as truths abaixo foram autoradas em `01-02-PLAN.md`/`01-03-PLAN.md` com `verification: backstop` — desenhadas explicitamente para o verificador se abster em vez de aprovar silenciosamente algo que ninguém testou. Nesta sessão elas foram fechadas com evidência dupla: o artefato persistido `01-CONCURRENCY-EVIDENCE.log` (commit `b3888fa`, gerado em Git Bash real no Windows, versões `bash 5.3.15(1)-release (x86_64-pc-cygwin)` / `Docker 28.4.0` / `Compose v2.39.2-desktop.1`, consistentes com o checkpoint ENV-06 já registrado) **e** uma reprodução independente executada diretamente nesta sessão de verificação, com containers de SHA distinto (prova de que não é o mesmo resultado reaproveitado).

**Backstop 1 — duas invocações concorrentes de `./run.sh up` (equivalente ao passo `docker compose up -d --wait floci`).**

Reprodução ao vivo nesta sessão:
```
--- A ---
A_EXIT=0
 Container template_etl-floci-1  Healthy
--- B ---
B_EXIT=1
Error response from daemon: Conflict. The container name "/template_etl-floci-1" is already
in use by container "47962fd09d5a333b54929d2bb15b6a55f5324c3cb6b4c32479094bb542356308".
```
(No log persistido do commit `b3888fa`, o mesmo cenário produziu o mesmo formato de erro contra um container de SHA diferente — `3951b3e94990...` — confirmando que são execuções distintas, não a mesma saída reaproveitada.) A invocação que falha aborta no primeiro passo (`start emulator`) e nunca alcança `bootstrap`/`seed` — a cadeia do D-09 falha rápido como projetado. `docker compose ps` depois mostra um único `template_etl-floci-1` saudável. Após `down`, `docker compose ps -a` fica vazio nas duas rodadas — confirmando que a ausência de rastro em `docker ps -a` é o estado final esperado de `down -v --remove-orphans` + `run --rm`, não evidência de que a execução não ocorreu (correção aceita desta sessão de verificação em relação à Rodada 1).

**Backstop 2 — duas invocações concorrentes de `./run.sh bootstrap`.**

Reprodução ao vivo nesta sessão (a partir de um `floci` recém-subido):
```
A_EXIT=0  |  A: [ok] database 'present (backend does not support in-place update)' / [ok] table 'present...' / [ok] partitions: 3 created, 0 already present
B_EXIT=0  |  B: [ok] database 'created' / [ok] table 'created' / [ok] partitions: 3 created, 0 already present
```
Ambas saem 0. Estado final consultado via boto3 imediatamente depois: `partition count: 3`, `partition values: ['2026-01-15', '2026-01-16', '2026-01-17']`, `distinct values` idêntico à lista completa — nenhuma duplicata, apesar de as duas invocações reportarem "3 created" cada uma (uma corrida real ao nível de `create_partition`, absorvida sem erro pelo backend em memória do Floci; o resultado final é correto de qualquer forma). O log persistido (`01-CONCURRENCY-EVIDENCE.log`) registra o mesmo padrão em 3 rodadas independentes, cada uma a partir de `down`+`up` limpos.

**Conclusão:** o texto literal de ambos os backstops — "nenhuma invocação produz um catálogo parcialmente registrado" — está satisfeito. Evidência incidental: o comportamento de `run_step` (D-12) bate com a especificação — uma linha no sucesso, saída bruta completa no `stderr` da falha.

### Achado adicional — fidelidade do Floci, para `docs/KNOWN_DIFFERENCES.md` (Fase 4)

Reproduzido ao vivo nesta sessão (além de já constar em `01-CONCURRENCY-EVIDENCE.log`):

```
get_tables('template_etl_db')          -> ['temperaturas']
get_tables('template-etl_db')          -> []
get_tables('nao_existe_de_jeito_nenhum') -> []
```

`GetTables` do Floci devolve lista vazia para um database **inexistente**, onde o AWS Glue real levantaria `EntityNotFoundException`. `template-etl_db` (com hífen, sem o `.replace('-','_')` que `catalog/config.py` aplica) é um nome de database que nunca existiu — e o retorno `[]` é indistinguível do retorno para um database real porém vazio. Vale registrar com a mesma franqueza com que foi descoberto: uma sonda de diagnóstico escrita durante esta verificação inicialmente cometeu exatamente esse erro de concatenação (`PROJECT_NAME + "_db"` sem o replace), recebeu `[]`, e por um momento pareceu perda de dados ou corrupção do catálogo pelos testes de concorrência — era um erro de digitação na sonda, não um problema real. Este é exatamente o modo de falha mais provável de se repetir em quem forkar o template. Registrado em `STATE.md` como o terceiro item que `docs/KNOWN_DIFFERENCES.md` deve carregar na Fase 4 (junto com a lacuna de `Update*` e a armadilha do `docker compose` fora do `run.sh`), com a recomendação explícita: **confira o nome do database antes de suspeitar dos dados.**

### PLAN Must-Haves — Checagens Específicas Solicitadas

| # | Checagem | Comando | Resultado | Status |
|---|---|---|---|---|
| 1 | D-08 — sem `delete_*` em bootstrap.py | `grep -cE 'delete_table\|delete_partition\|delete_database' catalog/bootstrap.py` | `0` | ✓ PASS |
| 2 | Imagem Glue nunca puxada nesta fase | `docker images --format '{{.Repository}}' \| grep -c aws-glue-libs` | `0` (verificado antes, durante e depois de toda a atividade de Docker desta sessão) | ✓ PASS |
| 3 | `bash -n run.sh` | `bash -n run.sh` | exit 0 | ✓ PASS |
| 4 | Oito funções `cmd_*` | `grep -cE '^cmd_(up\|down\|bootstrap\|seed\|job\|test\|lint\|demo)\(\)' run.sh` | `8` | ✓ PASS |
| 5 | `--profile tools` 4x | `grep -c -- '--profile tools' run.sh` | `4` | ✓ PASS |
| 6 | `--profile glue` 2x | `grep -c -- '--profile glue' run.sh` | `2` | ✓ PASS |
| 7 | Sem `eval` em run.sh | `grep -cE '^\s*eval\b' run.sh` | `0` | ✓ PASS |
| 8 | `MSYS_NO_PATHCONV=1` dentro do guard de `OSTYPE` | `awk '/case .*OSTYPE/,/esac/' run.sh \| grep -c MSYS_NO_PATHCONV` | `1` | ✓ PASS |
| 9 | Partições via loop de `create_partition`, nunca `batch_create_partition` | ver acima | `2` / `0` | ✓ PASS |
| 10 | Catálogo só via `boto3.client("glue", endpoint_url=...)`, nunca `GlueContext` | `grep -rn 'GlueContext\|create_dynamic_frame' catalog/ run.sh` | nenhuma ocorrência | ✓ PASS |
| 11 | CAT-03 — uma única fonte de verdade do schema | inspeção de `catalog/bootstrap.py` vs `catalog/schema/temperaturas.json` | `bootstrap.py` consome o JSON, não redefine | ✓ PASS |
| 12 | `requirements.txt` pinado com `~=`, não `==` | `grep -vE '^\s*(#\|$)' requirements.txt \| grep -cvE '^[A-Za-z0-9._-]+==[0-9]'` | `2` | ✓ RESOLVIDO via override (ver frontmatter) |
| 13 | Backstop — duas `up` concorrentes | ver seção acima | A=0, B=1 (conflito de nome de container), catálogo íntegro | ✓ PASS |
| 14 | Backstop — duas/três `bootstrap` concorrentes | ver seção acima | todas exit 0, 3 partições, sem duplicata | ✓ PASS |

### Required Artifacts

Todos os artefatos declarados pelos três planos (`.gitattributes`, `.gitignore`, `docker-compose.yml`, `.env.example`, `requirements.txt`, `docker/tools/Dockerfile`, `pyproject.toml`, `run.sh`, `catalog/schema/temperaturas.json`, `catalog/config.py`, `catalog/bootstrap.py`, `catalog/seed.py`, `data/sample/*.csv` + `README.md`) existem, são substantivos e estão conectados — ver a Rodada 1 desta verificação (checagens estáticas, todas re-executadas e confirmadas nesta sessão) para o detalhe artefato-a-artefato. Nenhuma mudança de artefato foi necessária nesta rodada — apenas fechamento de evidência dinâmica e um override.

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `docker-compose.yml` (glue) | `docker-compose.yml` (floci) | `depends_on: condition: service_healthy` | ✓ WIRED |
| `run.sh cmd_bootstrap` | `catalog/bootstrap.py` | `docker compose --profile tools run --rm tools python catalog/bootstrap.py` | ✓ WIRED |
| `run.sh cmd_seed` | `catalog/seed.py` | `docker compose --profile tools run --rm tools python catalog/seed.py` | ✓ WIRED |
| `catalog/bootstrap.py` | `catalog/schema/temperaturas.json` | `config.load_schema(...)` via `json.load` | ✓ WIRED |
| `catalog/bootstrap.py` / `catalog/seed.py` | `catalog/config.py` | `from catalog import config` | ✓ WIRED |
| `run.sh cmd_up` | `run.sh cmd_bootstrap` → `run.sh cmd_seed` | ordem fixa de chamada | ✓ WIRED |

### Requirements Coverage

Todos os 14 IDs desta fase (ENV-01…07, RUN-01…03, CAT-01…04) permanecem `✓ SATISFIED`, sem alteração em relação à Rodada 1 desta verificação. RUN-04 corretamente fora do escopo desta fase (pertence à Phase 2). Nenhum requisito órfão.

### Anti-Patterns Found

Nenhum marcador de dívida (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) nos arquivos desta fase. Nenhuma implementação vazia. Nenhuma mudança em relação à Rodada 1.

### Human Verification Required

Nenhum item pendente. Os dois itens roteados para verificação humana na Rodada 1 (backstops de concorrência) foram fechados nesta sessão com evidência dupla (log persistido + reprodução independente ao vivo) — ver seção "Backstops de concorrência" acima.

### Gaps Summary

Nenhum gap remanescente. O único gap identificado (estilo de pin `~=` vs `==` em `requirements.txt`) foi fechado via `overrides:` no frontmatter, citando o checkpoint de legitimidade de pacotes original (commit `1826d3c`, 01-01-SUMMARY.md) e a aceitação explícita do operador nesta sessão (2026-08-07).

Três itens ficam **anotados, não bloqueantes**, como dívida documental explícita para a Fase 4 (`docs/KNOWN_DIFFERENCES.md`) — nenhum é um gap da Phase 1, todos já registrados em `STATE.md`:
1. Floci não implementa `UpdateDatabase`/`UpdateTable` (achado em 01-03).
2. `docker compose` com path absoluto de container, rodado fora de `run.sh`, quebra em Git Bash (achado em 01-03) — também merece uma linha no README.
3. `GetTables` do Floci retorna `[]` para um database inexistente em vez de levantar `EntityNotFoundException` (achado nesta verificação, ver acima).

Um item permanece corretamente **deferido** para a Phase 2, não é um gap:

| # | Item | Addressed In | Evidence |
|---|---|---|---|
| 1 | O `Location` no formato `s3://` registrado por `catalog/bootstrap.py` é lido corretamente pelo caminho Athena-via-DuckDB do Floci (backstop de 01-03-PLAN.md) | Phase 2 | Phase 2 success criterion 3 e o Open Design Question "DuckDB vs Athena/Trino SQL dialect compatibility (TEST-04)" são explicitamente atribuídos à Phase 2 no ROADMAP. |

Decisões de escopo da Fase 2 informadas pelo operador durante esta sessão (modo `append`, `partitionOverwriteMode` N/A, escopo acadêmico/simulação, duplicação de linhas ao rodar `demo` duas vezes) foram registradas em `STATE.md` como contexto acumulado para o planejamento da Phase 2 — **não** marcam nenhum requisito desta fase e não fazem parte deste relatório de verificação.

---

*Verified: 2026-08-07*
*Verifier: Claude (gsd-verifier)*
