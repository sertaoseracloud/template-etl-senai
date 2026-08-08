---
phase: "03"
fixed_at: "2026-08-08T00:00:00Z"
review_path: ".planning/phases/03-terraform-module-continuous-integration/03-REVIEW.md"
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
fix_scope: all
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-08-08T00:00:00Z
**Source review:** .planning/phases/03-terraform-module-continuous-integration/03-REVIEW.md
**Iteration:** 1
**Fix scope:** all (Critical + Warning + Info)

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Hardcoded "production" tag in S3 bucket module

**Files modified:**
- `terraform/modules/s3-buckets/main.tf`
- `terraform/modules/s3-buckets/variables.tf`
- `terraform/main.tf`
- `terraform/variables.tf`

**Commit:** `fix(phase-03): CR-01 + WR-02 — make environment tag configurable in s3-buckets module`

**Applied fix:** Added `environment` variable to s3-buckets module with default `"production"`, added `project_name` variable to the module, updated S3 bucket tags to use `var.environment` and `var.project_name` instead of hardcoded values. Added `environment` variable to root variables.tf and passed both `environment` and `project_name` from root main.tf to the s3-buckets module.

---

### WR-01: Unused variable `glue_version` in catalog-table module

**Files modified:**
- `terraform/modules/catalog-table/variables.tf`
- `terraform/main.tf`

**Commit:** `fix(phase-03): WR-01 — remove unused glue_version variable from catalog-table module`

**Applied fix:** Removed `glue_version` variable declaration from `terraform/modules/catalog-table/variables.tf`. Removed `glue_version` parameter from the `catalog-table` module block in `terraform/main.tf`. The variable was declared and passed but never used in the module.

---

### WR-02: Hardcoded project name in S3 bucket tags

**Files modified:**
- `terraform/modules/s3-buckets/main.tf`
- `terraform/modules/s3-buckets/variables.tf`
- `terraform/main.tf`
- `terraform/variables.tf`

**Commit:** `fix(phase-03): CR-01 + WR-02 — make environment tag configurable in s3-buckets module`

**Applied fix:** Same commit as CR-01. Added `project_name` variable to s3-buckets module and updated Project tag to use `var.project_name` instead of hardcoded `"template_etl"`. The root main.tf already had `project_name` variable, so it was passed through to the module.

---

### IN-01: Floating image tag for Glue library

**Files modified:**
- `.github/workflows/ci.yml`
- `.github/workflows/drift.yml`

**Commit:** `fix(phase-03): IN-01 — document floating image tag concern`

**Applied fix:** Added comment above the Glue image caching step in both ci.yml and drift.yml documenting that the `:5` floating tag is used and recommending digest pinning for production reproducibility (e.g., `public.ecr.aws/glue/aws-glue-libs:5@sha256:<digest>`). Applied minimal fix as suggested by reviewer since `--all` is active.

---

## Verification

**terraform fmt:** Not available in worktree environment. Files verified manually for Terraform syntax correctness.

**Commits made:** 3
1. `fix(phase-03): CR-01 + WR-02 — make environment tag configurable in s3-buckets module` (4 files)
2. `fix(phase-03): WR-01 — remove unused glue_version variable from catalog-table module` (2 files)
3. `fix(phase-03): IN-01 — document floating image tag concern` (2 files)

---

_Fixed: 2026-08-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
