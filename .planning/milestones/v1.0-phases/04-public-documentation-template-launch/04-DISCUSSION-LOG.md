# Phase 04: Public Documentation & Template Launch - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-09
**Phase:** 04-Public Documentation & Template Launch
**Areas discussed:** README structure, Rename/adapting section detail, CI badge, Contributing scope

---

## README Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Onion (Recommended) | Quick Start → Architecture → Project Structure → How to Adapt → Known Differences → Contributing | ✓ |
| Technical-first | Architecture → Quick Start → Structure → Adapting → Known Differences → Contributing | |
| Adopter-first | Quick Start → Adapting checklist → All other sections | |

**User's choice:** Onion (Recommended)
**Notes:** Quick start leads with `./run.sh demo` as the single command. Architecture section explains the pipeline shape (s3 → EVT bridge → Glue job → s3). Known differences gets its own section, not buried.

---

## Rename/Adapting Section

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal list (Recommended) | Quick checklist of what to search-and-replace: PROJECT_NAME, cities, columns | ✓ |
| Decision guide | Walk through each decision point: new cities, columns, renaming, Glue version | |
| Copy-paste commands | Before/after diffs with exact sed commands | |

**User's choice:** Minimal list (Recommended)
**Notes:** The template's job is scaffolding, not teaching. Keep the adapt section short. Decision guide and copy-paste commands rejected as scope creep for a documentation phase.

---

## CI Status Badge

| Option | Description | Selected |
|--------|-------------|----------|
| CI workflow badge only (Recommended) | Points at ci.yml — PR workflow. Shows if template is currently functional. | ✓ |
| CI + Drift badges | Both ci.yml and drift.yml badges | |
| No badge | Maintainers prefer linking to Actions tab directly | |

**User's choice:** CI workflow badge only (Recommended)
**Notes:** Drift badge excluded — it runs on schedule and its failures are a maintenance concern, not a template health signal for a visitor.

---

## Contributing Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Scaffolding only (Recommended) | PRs improving scaffolding welcome; PRs adding business logic to sample job redirected to own project/fork | ✓ |
| Case-by-case | All improvements welcome; maintainer decides | |
| Formal triage | Feature branches, explicit roadmap/backlog | |

**User's choice:** Scaffolding only (Recommended)
**Notes:** MIT LICENSE. Maintenance boundary stated explicitly in CONTRIBUTING.md. Business-logic PRs (elaborating the sample job) are out of scope and redirected.

---

## Deferred Ideas

No scope creep was introduced — all alternatives were noted and the recommended options selected. No deferred ideas from this discussion.

### Items acknowledged but out of scope
- AD2-01 (GitHub Action for post-template rename automation) — acknowledged in Out of Scope
- AD2-02 (SQL portability guide) — Phase 2 concluded the portable subset; full guide is its own item
