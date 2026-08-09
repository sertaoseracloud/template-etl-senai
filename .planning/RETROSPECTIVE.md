# Retrospective: template_etl

Documento vivo. Cada marco acrescenta uma seção; tendências entre marcos ficam no final.

---

## Milestone: v1.2 — Hexagonal Architecture & Developer Experience

**Shipped:** 2026-08-09
**Phases:** 3 | **Plans:** 3 | **Commits:** 50

### What Was Built

- **Phase 1 — Arquitetura Hexagonal:** domain layer isolado (sem imports de
  Spark/Glue/boto3), ports como ABC com `@abstractmethod`, adapters
  primary/secondary, DI container, e `job.py` reduzido de 105 para 50 linhas.
- **Phase 2 — Testes & DX:** suítes de domínio e contratos de ports com mocks de
  Spark DataFrame (17 testes), e `./run.sh lint --fix` com auto-fix do ruff.
- **Phase 3 — Integração & Performance:** fixtures S3 contra Floci, testes
  end-to-end do GlueAdapter, 8 testes do DI container, 17 testes de PySpark real,
  pre-commit hooks e pipeline CI de 4 jobs.

### What Worked

- **A arquitetura hexagonal pagou o próprio custo dentro do mesmo marco.** Isolar
  o domínio permitiu que a Phase 2 escrevesse 17 testes unitários que rodam em
  0,1s sem container nenhum. Antes disso, testar qualquer lógica exigia Spark.
- **Code review por fase, não só no fim.** 22 issues encontrados e 21 corrigidos
  ao longo das três fases, em vez de acumular para o fechamento.
- **Verificação encontrou contradição real.** A Phase 1 tinha frontmatter
  `passed` e cabeçalho `gaps_found` no mesmo arquivo. Só apareceu porque a
  verificação leu o documento em vez de confiar no status agregado.

### What Was Inefficient

- **Duas fases entregues sem VERIFICATION.md.** As fases 2 e 3 foram dadas como
  completas com base no autorrelato dos summaries. No fechamento foi preciso
  verificar retroativamente — o trabalho estava certo, mas a confiança nele era
  não-fundamentada até então. Verificar na hora custa menos que reconstruir depois.
- **Dois marcos com fechamento pela metade.** v1.1 e v1.2 tiveram arquivos
  arquivados e ROADMAP atualizado, mas MILESTONES.md, STATE.md e tags ficaram
  para trás. Um fechamento parcial é pior que nenhum: o estado passa a mentir.
- **Checkboxes de REQUIREMENTS.md nunca atualizados.** 23 de 26 requisitos
  ficaram `[ ]` enquanto a tabela de rastreabilidade no mesmo arquivo dizia
  "✅ Complete" em tudo. Duas fontes de verdade no mesmo documento, divergindo.
- **Caçar o caminho errado no CI.** O passo de Terraform falhou quatro vezes
  seguidas com sintomas diferentes (`-chdir`, `cd`, `working-directory`) — todas
  pela mesma causa: o diretório era `terraform/`, não `infra/`. Verificar a
  premissa antes da terceira tentativa teria economizado três ciclos.

### Patterns Established

- **Ports como ABC com `@abstractmethod`**, não Protocol — dá erro em tempo de
  instanciação, não só no type-checker.
- **Marcadores para testes que exigem container** (`@pytest.mark.spark`,
  `@requires_glue`) — mantêm a suíte offline rápida sem apagar o caminho fiel.
- **Floci como container standalone no CI**, não como `services:` — o GitHub
  Actions não aceita `--network host` junto da rede que ele mesmo cria.

### Key Lessons

1. **Verificar é ler o código, não o resumo.** Todo achado desta rodada
   (contradição na Phase 1, drift dos checkboxes, 111k linhas de CSV inflando a
   estatística) veio de conferir a fonte em vez do relato.
2. **Fechamento é atômico ou não é fechamento.** Arquivo arquivado com STATE.md
   desatualizado gera um estado que parece pronto e não está.
3. **Erro repetido com sintoma novo é premissa errada, não bug novo.**
4. **Estatística bruta engana.** "116.802 linhas" viraram 5.698 ao excluir
   fixtures geradas — 95% do número era ruído.

### Cost Observations

- 3 fases planejadas e executadas em 2 dias
- 50 commits; 95 arquivos autorais alterados
- Verificação retroativa de 2 fases no fechamento: custo evitável

---

## Cross-Milestone Trends

| Marco | Fases | Planos | Commits | Arquivos | Closeout |
|-------|-------|--------|---------|----------|----------|
| v1.0 MVP | 4 | 9 | — | 57 | — |
| v1.1 Event-Driven & Perf | 2 | 3 | — | — | incompleto (corrigido em v1.2) |
| v1.2 Hexagonal & DX | 3 | 3 | 50 | 95 | verified_closeout |

### Tendências observadas

- **Disciplina de verificação caiu antes de subir.** v1.2 começou com a Phase 1
  verificada e re-verificada após fechar gaps, e terminou com duas fases sem
  verificação nenhuma. Corrigido no fechamento, mas o padrão vale vigiar.
- **Dívida técnica está sendo registrada, não escondida.** WR-03 aparece no code
  review da Phase 1, no arquivo do marco, no ROADMAP e no PROJECT.md.
- **Higiene de fechamento é o ponto fraco recorrente.** Dois marcos seguidos
  fecharam pela metade. É o candidato mais claro a virar checklist obrigatório.
