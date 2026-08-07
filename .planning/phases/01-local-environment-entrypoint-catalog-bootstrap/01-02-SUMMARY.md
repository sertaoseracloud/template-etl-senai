---
phase: 01-local-environment-entrypoint-catalog-bootstrap
plan: 02
subsystem: infra
tags: [bash, run.sh, docker-compose, entrypoint, preflight, ruff]

requires:
  - phase: 01-01
    provides: docker-compose.yml (floci/tools/glue services and profiles), .env.example (six variables), pyproject.toml (ruff config)
provides:
  - run.sh (executable, LF, set -euo pipefail) — the single project entrypoint
  - Eight subcommands: up, down, bootstrap, seed, job, test, lint, demo
  - Six-check preflight (docker daemon, compose plugin, --wait capability, .env presence, required-var non-emptiness, endpoint-not-real-AWS)
  - env_value / require_file / run_step helper functions
affects: [01-03, phase-2-ci, phase-4-docs]

actuals:
  tokens: 2100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "run_step LABEL COMMAND... — lean status line on success, full captured output on stderr on failure, propagates COMMAND's exit status"
    - "require_file PATH MESSAGE before any docker invocation — guards job/test against an unwanted ~4.77 GB Glue image pull on a Phase 1 clone"
    - "env_value parses .env with grep/string-strip, never sources it — a config file cannot run arbitrary shell"
    - "exact-match case dispatch over a fixed subcommand list — no eval, no prefix matching, no dynamic command construction"

key-files:
  created:
    - run.sh
  modified:
    - pyproject.toml

key-decisions:
  - "run.sh built exactly as specified in 01-CONTEXT.md D-05/D-09/D-10/D-11/D-12/D-13 — no deviation from the eight-subcommand surface or the up = compose-up + bootstrap + seed chain"
  - "pyproject.toml gained extend-exclude = ['.planning'] — Rule 3 auto-fix, see Deviations"

patterns-established:
  - "Every cmd_* function calls preflight (or require_file before preflight, for job/test) as its first action"
  - "Every docker compose invocation uses the explicit --profile form, never relying on Compose auto-activating a service's profile"

requirements-completed: [ENV-06, RUN-01, RUN-02, RUN-03]

coverage:
  - id: D1
    description: "run.sh foundation: strict mode, MSYS platform guard, env_value/require_file/run_step helpers, six-check preflight, fixed --help block, exact-match dispatcher"
    requirement: "RUN-01"
    verification:
      - kind: integration
        ref: "bash -n run.sh; ./run.sh --help (byte-identical twice, 8 names in fixed order); ./run.sh (no arg) exits 2; ./run.sh u exits 2; ./run.sh up extra exits 2"
        status: pass
    human_judgment: false
  - id: D2
    description: "Preflight refuses to proceed on missing .env, blank required variable, or an AWS_ENDPOINT_URL pointing at a real amazonaws.com endpoint"
    requirement: "ENV-06"
    verification:
      - kind: integration
        ref: "manual preflight() invocation with .env absent / PROJECT_NAME= blank / AWS_ENDPOINT_URL=https://glue.us-east-1.amazonaws.com, backed up and restored the working .env"
        status: pass
    human_judgment: false
  - id: D3
    description: "Eight cmd_* subcommand implementations wired to docker compose, up chaining compose-up then bootstrap then seed in fixed order and aborting at the first failure"
    requirement: "RUN-02"
    verification:
      - kind: integration
        ref: "./run.sh up against real Docker Desktop: floci starts healthy, bootstrap fails (catalog/bootstrap.py absent, born in 01-03), seed never runs, exit code 2 == ./run.sh bootstrap's own exit code"
        status: pass
    human_judgment: false
  - id: D4
    description: "job/test guard against an unwanted Glue image pull; lint passes on a clean clone; down leaves nothing running"
    requirement: "RUN-03"
    verification:
      - kind: integration
        ref: "./run.sh job and ./run.sh test both exit 1 naming the missing target with 0 aws-glue-libs images afterwards; ./run.sh lint exits 0 after the ruff exclude fix; ./run.sh down leaves docker compose ps -q empty"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-07
status: complete
---

# Phase 01 Plan 02: run.sh — Entrypoint com Preflight e Oito Subcomandos Summary

**`run.sh` completo com preflight de seis verificações e os oito subcomandos (`up`, `down`, `bootstrap`, `seed`, `job`, `test`, `lint`, `demo`), verificado ponta a ponta contra o Docker Desktop real — inclusive o caso esperado de falha em `bootstrap`/`job`/`test` numa clonagem que ainda não tem `catalog/` nem `jobs/` (nascem no plano 01-03 e na Fase 2).**

## Performance

- **Duration:** ~25 min (sessão de retomada; Task 1 já existia em disco, não commitada, de uma execução anterior interrompida)
- **Started:** 2026-08-07T12:00:00Z (aprox., retomada)
- **Completed:** 2026-08-07T12:20:06Z
- **Tasks:** 2
- **Files modified:** 2 (`run.sh` criado, `pyproject.toml` ajustado)

## Accomplishments

- `run.sh` na raiz do repositório: shebang, `set -euo pipefail`, guarda `OSTYPE` para `MSYS_NO_PATHCONV=1`, helpers `env_value`/`require_file`/`run_step`, `preflight` com seis checagens ordenadas e mensagens de remédio acionáveis, `usage` com bloco fixo e byte-idêntico, dispatcher exato sobre os oito nomes.
- As oito funções `cmd_*` implementadas: `cmd_up` encadeia `docker compose up -d --wait floci` → `cmd_bootstrap` → `cmd_seed` na ordem fixa exigida; `cmd_down` remove volumes e órfãos; `cmd_bootstrap`/`cmd_seed` rodam no serviço `tools`; `cmd_job`/`cmd_test` chamam `require_file` antes de qualquer `docker`, evitando o pull de ~4,77 GB da imagem Glue numa clonagem da Fase 1; `cmd_lint` roda `ruff check` e `ruff format --check`; `cmd_demo` encadeia `up` → `job` → `test`.
- Verificação completa rodada contra Docker Desktop real (não simulada): `up` sobe o `floci` saudável, falha no `bootstrap` (script ainda não existe), nunca chega ao `seed`, e o código de saída bate exatamente com `./run.sh bootstrap` isolado. `down` limpa tudo. `job` e `test` falham nomeando o alvo ausente sem baixar a imagem Glue. `lint` passa limpo.

## Task Commits

Each task was committed atomically:

1. **Task 1: run.sh foundation — strict mode, platform guard, preflight, help, dispatch** - `9f2dda9` (feat)
2. **Task 2: The eight subcommand implementations** - `2932800` (feat, inclui o auto-fix de `pyproject.toml`)

**Plan metadata:** commit a seguir (docs: complete plan)

## Files Created/Modified

- `run.sh` - Entrypoint único do projeto: preflight, `usage`, dispatcher exato, e as oito funções `cmd_*`.
- `pyproject.toml` - `extend-exclude = [".planning"]` adicionado ao `[tool.ruff]` (ver Deviations).

## Decisions Made

- Nenhuma decisão nova além das já registradas em `01-CONTEXT.md` (D-05, D-07, D-09 a D-13). O plano foi seguido literalmente para a superfície de subcomandos e a ordem de encadeamento de `up`.
- Marcadores de status em `run_step` mantidos ASCII (`[ok]` / `[FAIL]`), conforme item de discrição do Claude em `01-CONTEXT.md`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ruff format --check .` falhava sobre trechos de código Python embutidos em Markdown dentro de `.planning/research/`**
- **Found during:** Task 2, ao verificar `cmd_lint` contra o container real.
- **Issue:** `ruff 0.16.1` formata por padrão blocos de código Python cercados (fenced) dentro de arquivos Markdown. Como `cmd_lint` roda `ruff format --check .` a partir de `/workspace` (todo o repositório montado), ele encontrou blocos de exemplo Python em `.planning/research/ARCHITECTURE.md` e `.planning/research/STACK.md` — documentos de pesquisa da fase de planejamento, não código-fonte do projeto — e reportou-os como "would be reformatted", fazendo `./run.sh lint` sair não-zero numa clonagem limpa. Isso violava diretamente o critério de aceitação "`lint` deve sair 0 numa clonagem limpa".
- **Fix:** Adicionado `extend-exclude = [".planning"]` em `[tool.ruff]` no `pyproject.toml`. `extend-exclude` soma à lista padrão de exclusões do ruff em vez de substituí-la.
- **Files modified:** `pyproject.toml`
- **Verification:** `./run.sh lint` voltou a sair `0` (`ruff check` e `ruff format --check` ambos `[ok]`), reexecutado após o fix.
- **Committed in:** `2932800` (parte do commit da Task 2)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking)
**Impact on plan:** Necessário para que `cmd_lint` cumpra seu critério de aceitação num clone real; não altera a superfície de `run.sh` nem nenhuma decisão de `01-CONTEXT.md`. Sem scope creep — o fix é uma linha de configuração do ruff, não um novo componente.

## Issues Encountered

- O ambiente de execução (Windows/Git Bash) não tinha o Docker Desktop em execução no início desta sessão. Foi iniciado (`Docker Desktop.exe`) e aguardado até o daemon responder (`docker info`) antes de qualquer verificação dinâmica — sem essa etapa, `preflight` check 1 teria bloqueado toda a verificação de `cmd_up`/`cmd_down`/`cmd_lint`/`cmd_job`/`cmd_test` num falso-negativo indistinguível de um bug real.
- `.env` já existia no working tree (não deveria ser sobrescrito, por instrução do ambiente). Foi feito backup em `/tmp/env.backup` antes de qualquer teste que exigisse um `.env` modificado (ausente, `PROJECT_NAME=` em branco, `AWS_ENDPOINT_URL` real) e restaurado byte-a-byte (`diff` confirmou) ao final.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `run.sh` está completo e verificado; `up`/`down`/`lint` funcionam de ponta a ponta contra o Docker real, e `bootstrap`/`seed`/`job`/`test` estão corretamente cabeados para falhar até que o plano 01-03 crie `catalog/bootstrap.py`, `catalog/seed.py`, e a Fase 2 crie `jobs/csv_to_parquet/job.py` e `tests/`.
- Nenhum bloqueio para o plano 01-03: `cmd_bootstrap` e `cmd_seed` já invocam exatamente `python catalog/bootstrap.py` e `python catalog/seed.py` no serviço `tools`, então o plano 01-03 só precisa criar esses arquivos — nenhuma mudança em `run.sh` é esperada.

## Self-Check: PASSED

- `run.sh` exists — FOUND.
- `pyproject.toml` exists — FOUND.
- Commit `9f2dda9` (Task 1) — FOUND in `git log --oneline --all`.
- Commit `2932800` (Task 2) — FOUND in `git log --oneline --all`.

---
*Phase: 01-local-environment-entrypoint-catalog-bootstrap*
*Completed: 2026-08-07*
