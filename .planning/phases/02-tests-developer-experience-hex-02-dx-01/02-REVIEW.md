---
phase: 02-tests-developer-experience-hex-02-dx-01
reviewed: 2026-08-09T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tests/unit/test_domain/test_entities.py
  - tests/unit/test_ports/test_storage_port.py
  - tests/unit/test_transforms.py
  - run.sh
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

## Summary

Reviewed 4 files for Phase 2 (tests and lint --fix). Found 2 critical bugs in `run.sh` that cause shell errors, plus 5 warnings around test coverage gaps and dead code. The test files are generally well-structured but have some redundancy and missing edge case coverage.

---

## Critical Issues

### CR-01: Shell unbound variable error in cmd_lint

**File:** `run.sh:216`
**Issue:** The condition `if [ "$1" = "--fix" ]` fails with "unbound variable" when `$1` is unset. The `set -u` directive at line 2 enables strict error handling for undefined variables.
**Fix:**
```bash
if [ "${1:-}" = "--fix" ]; then
    fix_mode="--fix"
    echo "Running ruff with auto-fix..."
fi
```

### CR-02: Malformed Docker command in cmd_test

**File:** `run.sh:207`
**Issue:** The command `docker compose --profile glue run --rm glue -c "python3 -m pytest ..."` is incorrect. The `-c` flag is passed to the container as a literal argument, not interpreted as shell execution. Docker Compose `run` does not have a `-c` flag for running commands.
**Fix:**
```bash
run_step "run pytest suite" docker compose --profile glue run --rm glue python3 -m pytest --disable-warnings --with-integration -m 'not athena'
```

---

## Warnings

### WR-01: Dead code - lint-fix case branch

**File:** `run.sh:342`
**Issue:** The case statement includes `lint-fix) cmd_lint --fix ;;` but this branch is unreachable. The case pattern at line 318 does not include `lint-fix` as a valid subcommand, so any `lint-fix` invocation falls through to the `*` error case. The `./run.sh lint --fix` syntax (which works) routes through the `lint)` branch at line 341.
**Fix:** Remove the dead branch or add `lint-fix` to the valid subcommands list at line 318:
```bash
lint|lint-fix)
    cmd_lint "${2:-}" ;;
```

### WR-02: Variable shadowing in cmd_perf_test

**File:** `run.sh:254`
**Issue:** `local n_rows` on line 254 shadows the function parameter `$n_rows` from line 237. While functional (the `local` assignment happens first), this is confusing and redundant since `$n_rows` is already set by the caller.
**Fix:**
```bash
# Remove line 254-256; use the function parameter directly
# The mkdir -p on line 252 can stay
```

### WR-03: Missing validate-* commands in extra-argument check

**File:** `run.sh:327`
**Issue:** The extra argument validation at line 327 allows extra args for `lint` but not for `validate-spark` or `validate-athena`. While these commands currently take no arguments, this creates inconsistent validation logic.
**Fix:**
```bash
if [ "$#" -gt 1 ] && [ "$cmd" != "upload" ] && [ "$cmd" != "perf-test" ] && [ "$cmd" != "benchmark" ] && [ "$cmd" != "validate-s3" ] && [ "$cmd" != "validate-spark" ] && [ "$cmd" != "validate-athena" ] && [ "$cmd" != "lint" ]; then
```

### WR-04: require_file on directory instead of file

**File:** `run.sh:205`
**Issue:** `require_file tests` checks if `tests` exists as a file, but `tests` is a directory. The function uses `[ ! -e "$path" ]` which returns true for directories, so this check always fails (directories exist). This means the preflight check does not catch a missing tests directory.
**Fix:**
```bash
require_file tests/conftest.py "tests not found. This subcommand is wired in Phase 1 but only functional from Phase 2 onward."
```

### WR-05: Incomplete test coverage - missing edge cases

**File:** `tests/unit/test_domain/test_entities.py`
**Issue:** Domain entity tests cover happy paths but lack edge cases:
- No test for `JobResult` with FAILED status but no `error_message` (optional field)
- No test for PENDING or RUNNING status in `to_dict`
- No test for empty string values or None inputs
**Fix:** Add tests:
```python
def test_to_dict_pending(self) -> None:
    """JobResult with PENDING status."""
    result = JobResult(status=JobStatus.PENDING)
    data = result.to_dict()
    assert data["status"] == "pending"

def test_to_dict_failed_without_message(self) -> None:
    """JobResult with FAILED status but no error message."""
    result = JobResult(status=JobStatus.FAILED, rows_read=0, rows_written=0)
    data = result.to_dict()
    assert data["status"] == "failed"
    assert data["error"] is None
```

---

## Info

### IN-01: Duplicate test cases

**File:** `tests/unit/test_transforms.py:43-52`
**Issue:** `test_normalize_city_key_florianopolis`, `test_normalize_city_key_chapeco`, and `test_normalize_city_key_criciuma` duplicate cases already covered by `test_normalize_city_key_all_six_cities` parametrized test.
**Fix:** Remove lines 43-52 if the parametrized test provides sufficient coverage.

### IN-02: Missing empty/None input tests for normalize_city_key

**File:** `tests/unit/test_transforms.py`
**Issue:** No tests for edge inputs: empty string, None, or strings with only special characters.
**Fix:** Add parametrized cases:
```python
@pytest.mark.parametrize("cidade,expected", [
    ("", ""),
    ("SAO PAULO", "sao paulo"),  # spaces
])
```

### IN-03: Missing column validation tests

**File:** `tests/unit/test_transforms.py`
**Issue:** `derive_temp_media` and `add_city_key` tests do not verify behavior when required columns are missing from the DataFrame. PySpark will raise an AnalysisException at runtime, but this is not tested.
**Fix:** Add exception handling tests (optional, depends on project requirements).

---

_Reviewed: 2026-08-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
