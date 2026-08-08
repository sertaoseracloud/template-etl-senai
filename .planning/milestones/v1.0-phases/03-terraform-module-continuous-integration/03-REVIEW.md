---
phase: "03"
review_depth: standard
files_reviewed: 23
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/workflows/drift.yml
  - catalog/schema/temperaturas.json
  - data/sample/temperaturas_2026-01-15.csv
  - data/sample/temperaturas_2026-01-16.csv
  - data/sample/temperaturas_2026-01-17.csv
  - terraform/main.tf
  - terraform/modules/catalog-table/main.tf
  - terraform/modules/catalog-table/outputs.tf
  - terraform/modules/catalog-table/variables.tf
  - terraform/modules/glue-job/main.tf
  - terraform/modules/glue-job/outputs.tf
  - terraform/modules/glue-job/variables.tf
  - terraform/modules/iam-role/main.tf
  - terraform/modules/iam-role/outputs.tf
  - terraform/modules/iam-role/policy.tf
  - terraform/modules/iam-role/variables.tf
  - terraform/modules/s3-buckets/main.tf
  - terraform/modules/s3-buckets/outputs.tf
  - terraform/modules/s3-buckets/variables.tf
  - terraform/outputs.tf
  - terraform/providers.tf
  - terraform/variables.tf
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: findings_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-08-08T00:00:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Reviewed all 23 Phase 03 source files including GitHub Actions workflows, Terraform modules (root and 4 sub-modules), JSON schema, and sample CSV data files. Found 1 critical issue (hardcoded production tag creates environment mismatch risk), 2 warnings (unused variable and hardcoded project name), and 1 info item (floating image tag). The core Terraform structure and IAM least-privilege implementation are sound.

## Critical Issues

### CR-01: Hardcoded "production" tag in S3 bucket module

**File:** `terraform/modules/s3-buckets/main.tf:6-7` and `terraform/modules/s3-buckets/main.tf:29-30`

**Issue:** Both S3 bucket resources use `Environment = "production"` hardcoded in their tags. This creates a risk of deploying infrastructure to a non-production environment with production tags, which could cause confusion in cost allocation, access policies, and monitoring. If this Terraform is ever applied to a staging or development account, the tags will incorrectly indicate production.

**Fix:**
```hcl
variable "environment" {
  description = "Environment name for resource tagging"
  type        = string
  default     = "production"
}

resource "aws_s3_bucket" "raw" {
  bucket = var.raw_bucket_name

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}
```

Update the module variables to accept `environment` and `project_name` parameters, then update the root module to pass appropriate values.

---

## Warnings

### WR-01: Unused variable `glue_version` in catalog-table module

**File:** `terraform/modules/catalog-table/main.tf:1-86`

**Issue:** The `glue_version` variable is declared in `variables.tf`, accepted as a parameter in the module block in `main.tf` (line 38), but never used in `main.tf`. This creates confusion about whether the catalog table should be versioned and makes the variable dead code.

**Fix:** Either:
1. Remove the unused variable if the catalog table does not need version tracking, or
2. Document its intended use or implement the version tracking feature.

```hcl
# If version tracking is not needed, remove from catalog-table/main.tf line 38:
# glue_version        = var.glue_version

# And remove from variables.tf:
# variable "glue_version" { ... }
```

### WR-02: Hardcoded project name in S3 bucket tags

**File:** `terraform/modules/s3-buckets/main.tf:6-7` and `terraform/modules/s3-buckets/main.tf:29-30`

**Issue:** The tag `Project = "template_etl"` is hardcoded instead of using the `project_name` variable. This means the project tag will not reflect actual project name if someone overrides the default `project_name` variable.

**Fix:**
```hcl
variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
}

resource "aws_s3_bucket" "raw" {
  bucket = var.raw_bucket_name

  tags = {
    Environment = "production"
    Project     = var.project_name
  }
}
```

Update the root module to pass `project_name` to the s3-buckets module.

---

## Info

### IN-01: Floating image tag for Glue library

**File:** `.github/workflows/ci.yml:80` and `.github/workflows/drift.yml:28`

**Issue:** The Glue image tag `public.ecr.aws/glue/aws-glue-libs:5` is a floating tag without a digest. While acceptable for local development (Dockerfile already pins this tag), CI/CD pipelines may benefit from digest pinning to ensure reproducible builds.

**Fix (optional):** Consider pinning to a specific digest for production CI:
```yaml
- name: Cache Glue image
  uses: docker/build-push-action@v6
  with:
    ...
    tags: public.ecr.aws/glue/aws-glue-libs:5@sha256:<digest>
```

---

## Verification Checklist

| Check | Status |
|-------|--------|
| Provider pinning: hashicorp/aws ~> 6.0 | PASS |
| Backend: no backend block (offline validation) | PASS |
| IAM: no wildcard actions, named resource ARNs | PASS |
| Schema consumption: jsondecode(file()) path is correct | PASS |
| Partition count: 18 partitions | PASS |
| Name derivation matches catalog/config.py logic | PASS |
| YAML "on:" quoted to avoid boolean parsing | PASS |
| Job dependencies: lint -> terraform -> test | PASS |
| ./run.sh invocations present | PASS |
| Glue image caching: docker/build-push-action with type=gha | PASS |
| Cron schedule: twice-weekly drift detection | PASS |
| partition_keys: 2 entries (data_medicao, cidade_key) | PASS |
| partitions: exactly 18 entries | PASS |
| Columns include temp_media as derived column | PASS |
| CSV: cidade_key column present | PASS |
| CSV: Column order correct | PASS |
| CSV: All 6 cities present per date | PASS |

---

_Reviewed: 2026-08-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
