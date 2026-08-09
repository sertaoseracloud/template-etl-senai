---
phase: 03-integration-performance-tests
fixed_at: 2026-08-09T00:00:00Z
review_path: C:/repo/template_etl/.planning/phases/03-integration-performance-tests/03-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 7
skipped: 1
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-08-09T00:00:00Z
**Source review:** 03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8
- Fixed: 7
- Skipped: 1 (CR-01 was already fixed in original code)

## Applied Fixes

### CR-01: CI/CD leaks real AWS secrets to integration tests

**Status:** N/A - Already fixed in original code

The integration tests at lines 135-137 already use `AWS_ACCESS_KEY_ID: test` and `AWS_SECRET_ACCESS_KEY: test` instead of real secrets. No change needed.

---

### WR-01: Outdated pre-commit hook versions

**Files modified:** `.pre-commit-config.yaml`
**Applied fix:**
- Updated `pre-commit-hooks` from `v4.5.0` to `v5.1.0`
- Updated `ruff-pre-commit` from `v0.1.0` to `v0.8.6`

---

### WR-02: Orphaned `test` job with no content

**Files modified:** `.github/workflows/ci.yml`
**Applied fix:** Removed the incomplete `test` job (lines 62-102 in original) and replaced with a comment block explaining why it was removed and pointing to the `test-integration` job that handles the actual integration testing.

---

### WR-03: Floci service lacks health check

**Files modified:** `.github/workflows/ci.yml`
**Applied fix:** Added a "Wait for Floci to be ready" step after the dependencies are installed. The step polls the health endpoint up to 30 times with 2-second intervals before proceeding.

```yaml
      - name: Wait for Floci to be ready
        run: |
          for i in {1..30}; do
            curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1 && exit 0
            sleep 2
          done
          exit 1
```

---

### WR-04: Terraform init missing explicit directory

**Files modified:** `.github/workflows/ci.yml`
**Applied fix:** Added explicit `infra/` path to terraform init command:
```yaml
      - name: Terraform init
        run: terraform init -backend=false infra/
```

---

### WR-05: Fixture `clean_curated` is misleading

**Files modified:** `tests/integration/test_adapters/test_glue_adapter.py`
**Applied fix:** Replaced `pass` with `yield` and improved docstring to clarify delegation:

```python
@pytest.fixture(scope="function")
def clean_curated(clean_curated_prefix):
    """Ensure curated bucket is clean before each test.

    Delegates to clean_curated_prefix which performs the actual cleanup.
    """
    # clean_curated_prefix handles pre-test cleanup
    yield
```

---

### IN-01: Inline import in test function

**Files modified:** `tests/integration/test_adapters/test_glue_adapter.py`
**Applied fix:** Moved `import re` from inside `test_glue_adapter_populates_rows_metrics` function to top-level imports alongside other standard library imports.

---

### IN-02: Magic number 18 without explanation

**Files modified:** `tests/integration/test_adapters/test_glue_adapter.py`
**Applied fix:** Added explanatory comments on lines 201 and 254:
```python
# 3 dates x 6 cities = 18 partitions
assert parquet_count >= 18, (
    f"Expected at least 18 parquet files (3 dates x 6 cities), got {parquet_count}"
)
```

---

## Skipped Issues

None - all issues were successfully fixed.

---

_Fixed: 2026-08-09_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
