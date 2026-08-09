---
phase: 02-tests-developer-experience-hex-02-dx-01
fixed_at: 2026-08-09T13:10:00Z
review_path: C:/repo/template_etl/.planning/phases/02-tests-developer-experience-hex-02-dx-01/02-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-08-09T13:10:00Z
**Source review:** `C:/repo/template_etl/.planning/phases/02-tests-developer-experience-hex-02-dx-01/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (2 Critical + 5 Warnings; Info findings excluded per fix_scope)
- Fixed: 7
- Skipped: 0

---

## Fixed Issues

### CR-01: Shell unbound variable error in cmd_lint

**Files modified:** `run.sh`
**Commit:** `4aac160`
**Applied fix:** Changed `if [ "$1" = "--fix" ]` to `if [ "${1:-}" = "--fix" ]` at line 216 to handle unbound variable when `set -u` is enabled.

### CR-02: Malformed Docker command in cmd_test

**Files modified:** `run.sh`
**Commit:** `4aac160`
**Applied fix:** Removed the `-c` flag and shell string wrapper from the pytest command. The Docker `run` command now correctly executes `python3 -m pytest --disable-warnings --with-integration -m 'not athena'` directly.

### WR-01: Dead lint-fix case branch

**Files modified:** `run.sh`
**Commit:** `4aac160`
**Applied fix:** Removed the unreachable `lint-fix) cmd_lint --fix ;;` case branch as it was not a valid subcommand (users should use `lint --fix` instead).

### WR-02: Variable shadowing in cmd_perf_test

**Files modified:** `run.sh`
**Commit:** `4aac160`
**Applied fix:** Removed redundant `local n_rows` and `n_rows="$1"` lines that shadowed the function parameter. The function parameter `$n_rows` is now used directly.

### WR-03: Missing validate-* commands in extra-argument check

**Files modified:** `run.sh`
**Commit:** `4aac160`
**Applied fix:** Added `validate-spark` and `validate-athena` to the list of commands that allow extra arguments at line 327.

### WR-04: require_file on directory instead of file

**Files modified:** `run.sh`
**Commit:** `4aac160`
**Applied fix:** Changed `require_file tests` to `require_file tests/conftest.py` so the preflight check correctly validates that the test file exists (not just the directory).

### WR-05: Add edge case tests for JobResult

**Files modified:** `tests/unit/test_domain/test_entities.py`
**Commit:** `4aac160`
**Applied fix:** Added two new test methods:
- `test_to_dict_pending`: Tests `JobResult` with PENDING status
- `test_to_dict_failed_without_message`: Tests `JobResult` with FAILED status but no error message

---

## Skipped Issues

None - all in-scope findings were fixed.

---

_Generated: 2026-08-09T13:10:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
