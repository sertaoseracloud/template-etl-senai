---
phase: "04"
plan: "01"
subsystem: documentation
tags: [docs, readme, contributing, license, github-templates]
dependency_graph:
  requires: []
  provides:
    - README.md
    - docs/KNOWN_DIFFERENCES.md
    - CONTRIBUTING.md
    - LICENSE
    - .github/ISSUE_TEMPLATE/bug_report.yml
    - .github/ISSUE_TEMPLATE/feature_request.yml
  affects: []
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - README.md
    - docs/KNOWN_DIFFERENCES.md
    - CONTRIBUTING.md
    - LICENSE
    - .github/ISSUE_TEMPLATE/bug_report.yml
    - .github/ISSUE_TEMPLATE/feature_request.yml
  modified: []
decisions:
  - D-01 (README onion structure)
  - D-02 (minimal rename checklist)
  - D-03 (ci.yml badge with <org>/<repo>)
  - D-04 (scaffolding-only CONTRIBUTING)
  - D-05 (Floci Update* gap)
  - D-06 (docker compose outside run.sh)
  - D-07 (GetTables fidelity gap)
requirements_addressed: [DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06]
status: complete
---

# Phase 04 Plan 01: Public Documentation Template Launch — Summary

## One-liner

README.md with onion structure, 10-row KNOWN_DIFFERENCES.md local/AWS table, CONTRIBUTING.md with maintenance boundary, MIT LICENSE, and GitHub issue templates.

## Objective

**As a** developer who clicked "Use this template" and has never spoken to the author,
**I want to** clone the repo, run one command, and understand exactly which guarantees are real and which are emulated,
**so that** I can get to green and replace the sample pipeline with my own.

## Completed Tasks

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Wave 1 — README.md (complete tracer) | 0492600 | README.md |
| 2 | Wave 2a — docs/KNOWN_DIFFERENCES.md | c9850e5 | docs/KNOWN_DIFFERENCES.md |
| 3 | Wave 2b — CONTRIBUTING.md | 5a5e311 | CONTRIBUTING.md |
| 4 | Wave 2c — LICENSE (MIT) | 6d3249b | LICENSE |
| 5 | Wave 2d — GitHub Issue Templates | e80d7df | .github/ISSUE_TEMPLATE/bug_report.yml, .github/ISSUE_TEMPLATE/feature_request.yml |

## Success Criteria

- [x] README.md leads with Quick Start (git clone, cp .env.example .env, ./run.sh demo)
- [x] README.md every command appears in `./run.sh --help`
- [x] README.md CI badge has `<org>/<repo>` placeholder
- [x] README.md does not duplicate docs/LOCAL_DEV.md
- [x] README.md Known Differences cross-references docs/KNOWN_DIFFERENCES.md
- [x] README.md Contributing cross-references CONTRIBUTING.md
- [x] docs/KNOWN_DIFFERENCES.md has 10-row table covering all items in task action
- [x] CONTRIBUTING.md states scaffolding scope boundary and MIT license
- [x] LICENSE is MIT with year 2026
- [x] .github/ISSUE_TEMPLATE/bug_report.yml and feature_request.yml exist with correct fields

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface

No new security surface introduced (static documentation only).

## Known Stubs

None.

## Self-Check

- [x] README.md: 6 h2 sections, run.sh demo referenced, org/repo placeholder present, KNOWN_DIFFERENCES and CONTRIBUTING cross-referenced
- [x] docs/KNOWN_DIFFERENCES.md: 10 data rows covering all 10 items
- [x] CONTRIBUTING.md: In scope, Out of scope, MIT License
- [x] LICENSE: MIT License with year 2026
- [x] .github/ISSUE_TEMPLATE/: bug_report.yml and feature_request.yml with labels

## Self-Check: PASSED
