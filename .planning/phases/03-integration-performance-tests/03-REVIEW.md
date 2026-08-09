---
phase: 03-integration-performance-tests
reviewed: 2026-08-09T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - tests/integration/test_adapters/test_glue_adapter.py
  - tests/integration/test_adapters/test_di_container.py
  - tests/integration/test_spark_real.py
  - .pre-commit-config.yaml
  - .github/workflows/ci.yml
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
status: issues_found
---

## Summary

Reviewed 5 files from Phase 3 - Integration & Performance Tests. Found 1 critical security issue (CI/CD leaking real AWS credentials to tests) and 5 warnings ranging from outdated dependency versions to orphaned pipeline jobs. The test logic itself is sound, but the CI/CD configuration requires attention before shipping.

---

## Critical Issues

### CR-01: CI/CD leaks real AWS secrets to integration tests

**File:** `.github/workflows/ci.yml:98-184`
**Issue:** The `test-integration` job runs `pytest tests/integration/` using real AWS secrets (`${{ secrets.AWS_ACCESS_KEY_ID }}`, `${{ secrets.AWS_SECRET_ACCESS_KEY }}`). Integration tests should use test-only credentials (`AWS_ACCESS_KEY_ID: test`, `AWS_SECRET_ACCESS_KEY: test`) since they run against the local Floci emulator, not real AWS. This creates a security risk: if a test is compromised or misconfigured, it could inadvertently interact with real AWS resources.

**Fix:**
```yaml
      - name: Run integration tests
        run: pytest tests/integration/ -v --ignore=tests/integration/test_job.py
        env:
          AWS_ENDPOINT_URL: http://localhost:4566
          AWS_ACCESS_KEY_ID: test          # Use test credentials
          AWS_SECRET_ACCESS_KEY: test      # Use test credentials
          AWS_DEFAULT_REGION: us-east-1
```

---

## Warnings

### WR-01: Outdated pre-commit hook versions

**File:** `.pre-commit-config.yaml:4-18`
**Issue:** Both pre-commit hooks use very old versions:
- `pre-commit-hooks`: v4.5.0 (latest is v5.x)
- `ruff-pre-commit`: v0.1.0 (CLAUDE.md documents v0.16.1)

The CLAUDE.md documents ruff v0.16.1 as the project's pinned version, but pre-commit uses v0.1.0. This inconsistency means the linter behavior in pre-commit hooks may differ from the project's documented tooling.

**Fix:** Update to documented versions:
```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.1.0
    hooks:
      - id: trailing-whitespace
      ...

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

---

### WR-02: Orphaned `test` job with no content

**File:** `.github/workflows/ci.yml:62-95`
**Issue:** The `test` job has `needs: terraform` and Docker setup steps but no `runs-on`, no test steps, and no meaningful output. This job appears abandoned mid-development.

**Fix:** Either remove the orphaned job or complete its implementation:
```yaml
  # Option 1: Remove if redundant with test-integration
  # Option 2: Complete the implementation:
  test:
    name: Test (subprocess)
    runs-on: ubuntu-latest
    needs: terraform
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      # ... complete implementation
```

---

### WR-03: Floci service lacks health check

**File:** `.github/workflows/ci.yml:135-140`
**Issue:** The Floci service is started but not verified ready before tests run. Docker Compose `--wait` waits for ports but not application readiness. Floci may need time to initialize its internal state.

**Fix:** Add a health check step:
```yaml
      - name: Wait for Floci
        run: |
          for i in {1..30}; do
            curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1 && exit 0
            sleep 2
          done
          exit 1
```

---

### WR-04: Terraform init missing explicit directory

**File:** `.github/workflows/ci.yml:50`
**Issue:** `terraform init -backend=false` is run without a path argument. If Terraform files are in a subdirectory (e.g., `infra/`), this may fail or operate on the wrong directory.

**Fix:**
```yaml
      - name: Terraform init
        run: terraform init -backend=false infra/
        env:
          AWS_ACCESS_KEY_ID: ""
          AWS_SECRET_ACCESS_KEY: ""
```

---

### WR-05: Fixture `clean_curated` is misleading

**File:** `tests/integration/test_adapters/test_glue_adapter.py:70-73`
**Issue:** The `clean_curated` fixture does nothing (just `pass`) despite its docstring claiming it "ensures curated bucket is clean". The actual cleanup is performed by the `clean_curated_prefix` fixture it depends on. The `pass` statement is confusing and could mislead future developers.

**Fix:**
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

## Info

### IN-01: Inline import in test function

**File:** `tests/integration/test_adapters/test_glue_adapter.py:175`
**Issue:** `import re` is placed inside the function body rather than at the top of the file.

**Fix:** Move to top-level imports:
```python
import re  # at top with other imports
```

---

### IN-02: Magic number 18 without explanation

**File:** `tests/integration/test_adapters/test_glue_adapter.py:198, 249`
**Issue:** The assertion checks for `>= 18` parquet files but 18 is not explained. This equals 3 dates x 6 cities, which should be documented.

**Fix:**
```python
# 3 dates x 6 cities = 18 partitions
assert parquet_count >= 18, f"Expected at least 18 parquet files (3 dates x 6 cities), got {parquet_count}"
```

---

## Structural Findings (fallow)

No structural findings were provided in the review request.

---

_Reviewed: 2026-08-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
