# Phase 02: ETL Job & Green Test Suite - Research

**Researched:** 2026-08-08
**Domain:** S3A committer selection for Parquet output to S3A (Floci/MinIO) in append mode
**Confidence:** MEDIUM-HIGH on committer mechanics (Apache Hadoop official docs, corroborated by multiple community sources); MEDIUM on Floci-specific behavior (Floci GitHub issue #30 read directly, gives specific constraints); MEDIUM-LOW on whether "trivial scale" changes the calculus (no source addresses this scale regime specifically)

---

## Summary

Three committers are available in Spark 3.5 / Hadoop 3.3+. For the specific context of this phase -- 18 tiny Parquet files, append mode, Floci (MinIO-backed S3 emulator) -- the **default FileOutputCommitter** is the correct choice. It writes files directly to their final destination without staging, multipart, or rename overhead, and at this scale there is nothing to gain from any of the more sophisticated committers while the Magic committer carries a documented Floci-specific incomigibility (Floci's `GetObjectAttributes` does not return complete data after `CompleteMultipartUpload`, which is exactly the operation the Magic committer relies on). The V2 staging committers are designed for overwrite semantics and have a non-obvious interaction with append mode that makes them the wrong default even if they are technically safe. The content-assertion test from D-04 provides the safety net that makes "use the default" a defensible choice.

---

## Committer Options

### Option 1: Default FileOutputCommitter (no committer / direct write)

Spark's default committer, equivalent to not setting any committer at all.

- **Mechanism:** Task writers open output files directly at the final destination path and write data as it arrives. No staging, no multipart upload, no rename.
- **Commit phase:** For each file, Spark records the file path in `_spark_metadata/` (Spark 3+) and writes a `_SUCCESS` marker. Files already exist at their final location; commit is essentially a metadata operation.
- **Abort on failure:** Files written by a failed task remain in place. If Spark overwrites (mode=`overwrite`), it deletes first; in append mode, failed-task files are orphaned at their final paths.
- **S3 operations used:** `PutObject` (one per file), `PutObject` (success marker), `PutObject` (_spark_metadata). No multipart, no rename, no staging.
- **Consistency requirements:** Minimal. Data is written with standard `PutObject` and is immediately consistent (readable) after the TCP write completes.
- **Append mode interaction:** In append mode, Spark does not delete pre-existing files. A failed task's partial file is visible at its final path immediately upon write, before any commit action.
- **Configuration needed:** None -- this is the default.

### Option 2: Magic Committer (S3A committer, `fs.s3a.committer.name=magic`)

The committer purpose-built for object stores. Enabled by default since Hadoop 3.3.1 (`fs.s3a.committer.magic.enabled=true` by default).

- **Mechanism (per Apache Hadoop official docs):** Task writers open a "magic" file at the final destination using S3 multipart upload, writing part-by-part. The file is NOT visible to readers until the job commit phase, which calls `CompleteMultipartUpload` on all files, making them appear atomically. A rename-by-rename operation (calling `CopyObject` then `DeleteObject` on the original) is used to resolve conflicts in overwrite mode.
- **Commit phase:** Job commit calls `CompleteMultipartUpload` on all pending multipart uploads, then performs `CopyObject`+`DeleteObject` for each file to move it to its final location.
- **Abort on failure:** Pending multipart uploads are aborted (default: `fs.s3a.committer.abort.pending.uploads=true`); no orphaned files at the final path.
- **S3 operations used:** `CreateMultipartUpload`, `UploadPart` (many per file), `CompleteMultipartUpload`, `CopyObject`, `DeleteObject`, `GetObjectAttributes` (to enumerate task output before commit).
- **Consistency requirements:** The store must be strictly consistent: readers must not see partial multipart upload data (files before `CompleteMultipartUpload` is called). AWS S3 provides this guarantee; MinIO requires strict consistency mode enabled.
- **Append mode interaction:** Magic committer has no defined append conflict mode -- "conflict management is left to the execution engine itself" (Apache Hadoop docs). In append mode, Spark's commit protocol typically calls `CompleteMultipartUpload` without the rename step, making the files visible without conflict resolution.
- **Configuration needed:** `fs.s3a.committer.magic.enabled=true` (already default); can also set `fs.s3a.committer.name=magic` to force it explicitly.

### Option 3: Directory Staging Committer (`fs.s3a.committer.name=directory`)

The V2 committer optimized for HDFS-to-S3 migration. Uses a staging directory on a fast filesystem, then copies to S3 at commit time.

- **Mechanism:** Task writers write to a local staging directory (`tmp/staging/` by default, configurable via `fs.s3a.committer.staging.tmp.path`). At job commit, the committer uploads files from staging to S3 using parallel `PutObject` calls, then deletes the staging directory.
- **Conflict modes (via `fs.s3a.committer.staging.conflict-mode`):**
  - `append` (default): New files are added to the destination; if a file with the same name exists, it is overwritten.
  - `replace`: All files in the destination directory are deleted before new files are committed.
  - `fail`: The job fails if any destination file already exists.
- **Abort on failure:** Staging directory is cleaned up; no S3 artifacts are created until commit succeeds.
- **S3 operations used:** `PutObject` (parallel, from staging), `DeleteObject` (for conflict resolution in `replace` mode). No multipart upload, no rename-by-copy.
- **Consistency requirements:** Low. Files are uploaded via `PutObject` and are immediately consistent after upload. No dependency on object store read-after-write consistency.
- **Append mode interaction:** The `directory` committer supports append conflict mode explicitly, which makes it technically safe for append writes. However, the append semantics ("overwrite any file with the same name") means files from a failed task are NOT present in S3 at all (staging not committed), but files from a successful task DO overwrite existing files with the same name -- which is the intended append behavior. The committer is designed for overwrite-first semantics; append is a mode it tolerates rather than one it is optimized for.
- **Configuration needed:** `fs.s3a.committer.name=directory` plus optionally `fs.s3a.committer.staging.conflict-mode=append`.

### Option 4: None (no committer configuration)

Equivalent to Option 1 -- the FileOutputCommitter with default settings. Explicitly listed for completeness to show the full option space.

---

## Evidence

### Evidence 1: Does MinIO (via Floci) properly support multipart upload and the Magic committer?

**Short answer:** Basic multipart upload works (CreateMultipartUpload, UploadPart, CompleteMultipartUpload all exist and function), but `GetObjectAttributes` returns incomplete data after a multipart upload is completed, which is a specific Magic committer dependency.

**Evidence:**
- [Floci GitHub Issue #30](https://github.com/floci-io/floci/issues/30) ("Missing attributes functionality for S3 Objects", March 2026, read directly) documents that `CompleteMultipartUpload` does not retain the manifest data needed to serve `ObjectParts` in `GetObjectAttributes` responses. The `GetObjectAttributes` API should return `ETag, ObjectSize, StorageClass, Checksum, ObjectParts` for completed multipart uploads -- but Floci returns incomplete data. This is not an edge case; it is a documented, labeled (bug) gap in Floci's multipart attribute persistence.
- The Magic committer relies on `GetObjectAttributes` (and `GetObject`) to enumerate task-level output before the job commit phase. The committer needs to verify which files were written and their attributes before calling `CompleteMultipartUpload`. If `GetObjectAttributes` returns incomplete or missing data, the committer cannot reliably enumerate the task output it must commit.
- Basic multipart operations (CreateMultipartUpload, UploadPart, CompleteMultipartUpload) function -- the issue is specifically about the attribute/query layer on top of completed multipart uploads.

**Verdict:** The Magic committer is **not reliably usable against Floci** in its current state (v1.5.11). The failure mode is not a silent data correctness bug -- pending multipart uploads are aborted on job failure (default behavior) -- but the committer may fail to enumerate or commit task output correctly if `GetObjectAttributes` returns empty/incomplete data, producing a job failure that appears as a commit error rather than a data correctness problem.

### Evidence 2: What is the actual risk/reward of each committer at this scale (18 files, trivial data)?

**Scale context:** 18 rows total, 18 partitions, 18 small Parquet files. Each file is a few kilobytes. There is no meaningful performance difference between any committer option at this scale.

**Risk/reward breakdown:**

| Committer | Performance gain at this scale | Risk added | Net |
|-----------|-------------------------------|-----------|-----|
| Default | Zero (already optimal -- direct PutObject) | Failed task leaves partial file at final path; caught by test D-04 assertion | Neutral |
| Magic | Zero (files are too small for multipart to help; overhead of multipart setup > direct PutObject savings) | Floci `GetObjectAttributes` gap may cause commit failure or silent enumeration error | Negative |
| Directory staging | Zero (staging overhead >> direct PutObject for KB-sized files) | Extra config; append conflict mode is tolerated not optimized; risk of misconfiguration | Negative |
| None | Zero (same as default) | Same as default | Neutral |

**Source:** [Apache Hadoop S3A Committers docs](https://hadoop.apache.org/docs/current/hadoop-aws/tools/hadoop-aws/committers.html) -- no minimum file size or scale threshold is documented for the Magic committer, but the multipart upload mechanism has per-part overhead that makes it a net negative for small files in general.

### Evidence 3: Are there known incompatibilities between S3A committers and MinIO emulators?

**General MinIO:** MinIO's S3 API implementation has a documented compliance gap in `ListMultipartUploads` (GitHub issue #13246, September 2021). This affects cleanup of stale multipart uploads (the abort-path), not the happy path. MinIO supports strict consistency mode, which is required for the Magic committer to function correctly against MinIO. The Magic committer also requires multipart upload support, which MinIO provides.

**Floci specifically:** Floci is a MinIO-based emulator (it uses the MinIO server internally). The Floci-specific gap is `GetObjectAttributes` returning incomplete data after `CompleteMultipartUpload` (Floci Issue #30, March 2026, read directly). This is distinct from the general MinIO `ListMultipartUploads` gap and specifically blocks the Magic committer's task-enumeration phase.

**For the directory committer:** Uses `PutObject` (not multipart) and `DeleteObject` (for conflict resolution). No dependency on `GetObjectAttributes` or multipart-specific enumeration. This is the safest committer option against Floci if a non-default committer is desired, but it adds configuration complexity for zero benefit at this scale.

### Evidence 4: Given append mode, which committers interact correctly with append writes?

**Default (FileOutputCommitter):** Correct. In append mode, Spark does not delete existing files. The committer writes each file to its final path. If a task fails mid-write, the partial file remains. This is the expected behavior in append mode (new data is appended to existing data), and the integration test (D-04) asserts content correctly so a partial file would cause the test to fail, providing the safety net.

**Magic committer:** Works in append mode at the protocol level (completes multipart uploads without rename), but the Floci `GetObjectAttributes` gap (Evidence 1) makes it unreliable in practice.

**Directory committer (`conflict-mode=append`):** Works correctly. The `append` conflict mode is explicitly documented in the Apache Hadoop docs: "Add new data to the directories at the destination; overwriting any with the same name." In append mode, Spark's commit protocol calls the committer with append semantics, and the directory committer handles this correctly. However, this committer is designed primarily for overwrite-first workflows (migration from HDFS) where the staging-then-overwrite pattern is natural; append is a mode it tolerates.

**V2 partitioned committer:** Not relevant here -- partition-level commit is only beneficial with hundreds of partitions; at 18 partitions, the overhead is pure cost.

### Evidence 5: What does DuckDB-backed Athena see if partial files appear due to failed writes?

**DuckDB behavior:** DuckDB reads Parquet files by listing the directory and reading each file found. If a partial/incomplete Parquet file is present in the output directory (which can happen with the default committer if a task fails mid-write in append mode), DuckDB will attempt to read it. A partial Parquet file (an incomplete page structure) will typically cause a DuckDB query to fail with a parse/footer error, not to silently return wrong data.

**Integration test consequence:** The D-04 integration test uses `COUNT(*)` as its primary assertion. If a partial file is present, DuckDB's attempt to read it may raise an exception rather than returning an incorrect count -- which would cause the test to fail, which is the correct behavior. If the partial file happens to be a complete but smaller-than-expected Parquet (task wrote some rows before failing), DuckDB reads it and the count assertion catches the shortfall. In neither case does DuckDB silently return wrong data from a malformed Parquet file.

**Source:** [Apache Hadoop S3A Committers docs](https://hadoop.apache.org/docs/current/hadoop-aws/tools/hadoop-aws/committers.html) -- "Conflict management is left to the execution engine itself" for Magic committer append mode. DuckDB's Parquet reader behavior is standard open-source DuckDB behavior.

---

## Recommendation

**Use the default FileOutputCommitter (no explicit committer configuration).** Document the choice in a code comment.

### Rationale

1. **No performance benefit from any other option at this scale.** The Magic committer's multipart upload mechanism has per-call overhead that exceeds its savings for kilobyte-sized files. The directory staging committer's staging-then-upload pattern adds latency for zero gain. The default committer writes directly via `PutObject`, which is optimal for small files.

2. **The Magic committer is blocked by a documented Floci bug.** Floci Issue #30 (read directly) shows that `GetObjectAttributes` returns incomplete data after `CompleteMultipartUpload`. The Magic committer uses `GetObjectAttributes` to enumerate task output before committing it. This is not a hypothetical incompatibility -- it is a documented bug in the specific emulator this project uses. There is no configuration workaround.

3. **The default committer's failure mode is already covered.** The D-04 integration test prepares state, runs the job, and asserts content via `COUNT(*)` and aggregate assertions. A failed task that leaves a partial file at its final path will cause the test to fail (DuckDB either cannot read the partial file or reads it and finds fewer rows than expected). The test is the safety net.

4. **Append mode is handled correctly by the default committer.** In append mode, Spark writes to the final path without deletion. Existing files from previous runs coexist with new files. The integration test's D-04 precondition ("clean the curated prefix before running") ensures the test sees only the current run's output, making the `COUNT` deterministic regardless of how many times `./run.sh job` ran previously.

5. **Minimum configuration surface.** The default committer requires no configuration at all. Any explicit committer choice adds Spark configuration that must be verified, documented, and kept in sync between `run.sh`, the Terraform Glue job arguments, and the integration test. The default eliminates this surface area entirely.

### What to document in the job code

A comment explaining why no committer is explicitly configured, referencing the Floci `GetObjectAttributes` gap and the trivial scale:

```python
# No S3A committer is explicitly configured here. The options are:
#
# - Magic committer (fs.s3a.committer.name=magic):
#   NOT used. Floci v1.5.11 does not correctly persist ObjectParts metadata
#   after CompleteMultipartUpload (floci-io/floci#30), which breaks the Magic
#   committer's task-enumeration step. This is a known Floci gap, not a
#   configuration problem.
#
# - Directory staging committer (fs.s3a.committer.name=directory):
#   NOT used. Adds staging-then-upload overhead that yields zero benefit for
#   18-kilobyte Parquet files across 18 partitions. Append conflict mode is
#   tolerated but not optimized for.
#
# - Default FileOutputCommitter (what you get with no configuration):
#   USED. Direct PutObject to the final path. No multipart, no staging, no
#   rename. Failed tasks leave partial files at their final paths; the
#   integration test's content assertion (D-04) is the safety net.
#
# If this job is migrated to real AWS S3, re-evaluate the Magic committer:
# real S3 has no GetObjectAttributes gap and multipart upload is beneficial
# for files larger than ~100 MB.
```

---

## Decision Criteria

Use the following criteria to revisit this decision if the project's context changes:

### Switch to Magic committer if:
- Floci ships a fix for Issue #30 (`GetObjectAttributes` returning incomplete multipart metadata), verified by running the job against Floci and confirming no commit errors
- The job is migrated to real AWS S3 (where the Magic committer's multipart optimization pays off for larger files)
- File size grows to the point where multipart upload is genuinely faster than direct `PutObject`

### Switch to Directory staging committer if:
- Append mode is changed to overwrite mode (the directory committer is optimized for overwrite-first workflows)
- The job runs in a multi-writer scenario where concurrent jobs write to the same output prefix (the directory committer's conflict modes provide more explicit control than the default committer)
- A staging filesystem with better I/O than S3 is available and the committer can be configured to use it

### Keep default committer if:
- Output files remain small (under ~100 MB per file) -- direct `PutObject` is faster than multipart upload
- Floci remains the target storage (Magic committer is blocked by Issue #30)
- Append mode is in use (the default committer handles this correctly)
- The integration test (D-04) provides content assertions (it does)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Floci v1.5.11 ships with the MinIO server and has the GetObjectAttributes gap described in Issue #30 | Recommendation | MEDIUM -- if Floci's MinIO base is newer and fixes the gap, the Magic committer becomes viable; the risk is only that we rejected a better option unnecessarily. The fix would be a one-line config change. |
| A2 | DuckDB raises an exception (not silently wrong data) when reading a partial Parquet file | Evidence 5 | LOW -- DuckDB's Parquet reader is robust and standard; even if the exact error type differs, the test fails either way. |
| A3 | The default committer's partial-file failure mode is deterministic enough to be caught by the COUNT assertion in D-04 | Evidence 5 + Recommendation | LOW -- either DuckDB fails to read the partial file (test fails) or it reads fewer rows (COUNT assertion fails). |

---

## Open Questions

1. **Floci multipart attribute fix timeline:** Floci Issue #30 is labeled as a bug, but no milestone or fix version is visible in the GitHub issue. If the project needs the Magic committer for a future large-file use case, someone needs to track whether Floci ships a fix and retest.

2. **Overwrite vs. append in production:** The Phase 02 decision is append mode for the local simulation. If the Terraform-provisioned Glue job uses overwrite mode in production (a common real-world choice for reprocessing), the directory staging committer becomes more relevant because its overwrite conflict mode is the design target. Worth a comment in the Terraform module.

3. **MinIO strict consistency mode in Floci:** The Magic committer requires strict consistency from the object store. Floci is MinIO-based; MinIO supports strict consistency mode but it must be explicitly enabled in the MinIO server config. Whether Floci enables it by default is not documented. This is a secondary reason to avoid the Magic committer against Floci, but is lower confidence than the Issue #30 finding.

---

## Sources

### Primary (HIGH confidence)
- [Apache Hadoop S3A Committers documentation](https://hadoop.apache.org/docs/current/hadoop-aws/tools/hadoop-aws/committers.html) -- committer options, conflict modes, magic committer mechanism, default settings. Official source.
- [Floci GitHub Issue #30](https://github.com/floci-io/floci/issues/30) -- GetObjectAttributes returning incomplete data after CompleteMultipartUpload. Read directly from the issue, March 2026. Primary source for the Floci-specific incompatibility.

### Secondary (MEDIUM confidence)
- [MinIO GitHub Issue #13246](https://github.com/minio/minio/issues/13246) -- ListMultipartUploads compliance gap in MinIO. Community-reported, September 2021. Corroborates the general MinIO S3 API compliance landscape.
- [AWS EMR S3-optimized commit protocol and multipart uploads](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-spark-commit-protocol-multipart.html) -- EMRFS commit protocol context for multipart upload in Spark/Glue workloads.
- [MinIO Blog: Migrating from HDFS to AIStor](https://www.min.io/blog/migrating-hdfs-to-object-storage) -- notes Magic committer requires strict consistency on object stores.

### Tertiary (LOW confidence)
- [Stack Overflow: Hadoop Parquet Magic Committer with Custom S3 Server](https://stackoverflow.com/questions/53388976/how-to-use-new-hadoop-parquet-magic-commiter-to-custom-s3-server-with-spark) -- practitioner discussion of Magic committer with MinIO. Unable to fetch directly; corroborated by Hadoop docs and MinIO blog.
- [Medium: Improve S3 write performance with Magic Committer in Spark 3](https://medium.com/towards-data-engineering/improve-s3-write-performance-with-magic-committer-in-spark3-d509e49f9710) -- practitioner guide. Useful for general context but not authoritative on the Floci-specific question.

---

*Research for: Phase 02 ETL Job & Green Test Suite -- S3A committer decision*
*Date: 2026-08-08*
