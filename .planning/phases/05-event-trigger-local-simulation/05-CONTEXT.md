# Phase 5: Event Trigger & Local Simulation - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Add event-driven ETL capabilities: the Glue job accepts a file key parameter (via CLI arg with env var fallback), local trigger simulation validates the flow in Floci, and Terraform provisions EventBridge infrastructure for real AWS deployment.
</domain>

<decisions>
## Implementation Decisions

### File Key Reception
- **D-01:** Glue job accepts file key via both `--file-key` CLI argument (priority) and `FILE_KEY` environment variable (fallback). CLI arg takes precedence if both are provided.
- **D-02:** If file key points to non-existent S3 object, the job skips silently and exits 0.

### Upload Mechanism
- **D-03:** `./run.sh upload <file>` uploads to S3 using the existing `tools` service (boto3). The S3 key is printed to stdout after successful upload.

### Watch / File Detection
- **D-04:** `./run.sh watch` polls S3 using `list_objects_v2` every **5 seconds** (configurable via `POLL_INTERVAL` env var). Triggers job with file key when new files are detected.

### EventBridge Provisioning
- **D-05:** Terraform provisions S3 EventBridge integration (EventBridge data source pointing to raw bucket, filtered for ObjectCreated events). Uses Input Transformer to pass S3 key as job parameter.
- **D-06:** Job logs trigger events to CloudWatch Logs (standard Glue job logging).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project References
- `.planning/PROJECT.md` — Core value, constraints, and key decisions from v1.0
- `.planning/REQUIREMENTS.md` — v1.1 requirements (EVT-01 through EVT-05, SIM-01 through SIM-04, IAC-05 through IAC-07)
- `.planning/STATE.md` — Accumulated context including Floci limitations

### Existing Code
- `jobs/csv_to_parquet/job.py` — Job entry point; already uses argparse and reads config from `os.environ`
- `run.sh` — CLI entry point; established `run_step` pattern, `env_value()` helper, `preflight()` checks, and `require_file()` guards
- `terraform/main.tf` — Terraform structure; modules for S3, IAM, catalog, and Glue job already exist

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`run.sh` functions:** `run_step()`, `env_value()`, `preflight()`, `require_file()` — all usable by new subcommands (upload, watch)
- **tools service:** Already has boto3 available — can be used for S3 upload without adding new dependencies
- **Existing Terraform modules:** `s3-buckets`, `iam-role`, `glue-job` — new EventBridge module can follow same pattern

### Established Patterns
- **CLI argument pattern:** Job uses argparse with `--JOB_NAME`; `--file-key` follows same pattern
- **Environment variable pattern:** Job already reads AWS config from `os.environ`; `FILE_KEY` env var fits existing pattern
- **Terraform module pattern:** Each resource has its own module in `terraform/modules/`; EventBridge should follow same structure
- **run_step pattern:** All docker commands use `run_step "description" command` for consistent output

### Integration Points
- **Job entry point:** `jobs/csv_to_parquet/job.py` needs new `--file-key` argument and modified input path logic
- **run.sh:** Needs new `upload` and `watch` subcommands added to case statement
- **Terraform:** Needs new module for EventBridge rule, IAM role for EventBridge→Glue invocation, and Input Transformer

</code_context>

<specifics>
## Specific Ideas

- **Polling interval:** 5 seconds default, configurable via `POLL_INTERVAL` env var
- **Output format:** S3 key printed to stdout after upload (simple, parseable)
- **Error handling:** Non-existent file key → skip silently and exit 0
- **EventBridge:** S3 ObjectCreated events → Input Transformer → Glue job with file parameter
- **Logging:** CloudWatch Logs (standard Glue logging, compatible with real AWS)
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-Event Trigger & Local Simulation*
*Context gathered: 2026-08-08*
