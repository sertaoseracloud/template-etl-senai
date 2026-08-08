---
phase: "06"
status: "issues_found"
files_reviewed: 5
depth: "standard"
critical: 1
warning: 1
info: 2
total: 4
---

# Code Review: Phase 06 - Performance Testing Infrastructure

## Summary

| Severity | Count |
|----------|-------|
| Critical | 1 |
| Warning | 1 |
| Info | 2 |

## Findings

### CR-01: JSON result file written inside Docker container, not to host filesystem

**File:** `run.sh` (cmd_perf_test function)

**Severity:** Critical

**Issue:** The JSON result file is written inside the Docker tools container, not to the host filesystem:

```bash
docker compose --profile tools run --rm tools python -c "
    # ... JSON generation ...
    with open('$result_file', 'w') as f:
        json.dump(result, f, indent=2)
"
```

The `$result_file` path (`results/perf-${timestamp}.json`) is relative to the container's `/workspace` directory, not the host filesystem. The file will be lost when the container exits.

**Impact:** Performance test results are never persisted. Users cannot review past test results.

**Fix:** Write the JSON to the host filesystem. Options:
1. Use `docker compose cp` to copy the file out
2. Write to a volume mount
3. Write the JSON directly from the host shell using `python` on host

**Suggested fix:**
```bash
# Write JSON directly from host
python -c "
import json

result = {
    'test': 'csv_to_parquet_perf',
    'rows_generated': $n_rows,
    'elapsed_seconds': $elapsed,
    'throughput_rows_per_sec': $throughput,
    'timestamp': '$timestamp',
    's3_key': '$s3_key'
}

with open('$result_file', 'w') as f:
    json.dump(result, f, indent=2)

print(json.dumps(result, indent=2))
"
```

---

### WR-01: `bc` command dependency not guaranteed on all systems

**File:** `run.sh` (cmd_perf_test function)

**Severity:** Warning

**Issue:** The script uses `bc` for floating-point arithmetic:
```bash
elapsed="$(echo "$end_time - $start_time" | bc)"
throughput="$(echo "scale=2; $n_rows / $elapsed" | bc)"
```

While `bc` is POSIX-compliant, it is not installed by default on some minimal Linux distributions and may not be available in all Docker base images.

**Impact:** The `perf-test` subcommand will fail on systems without `bc` installed.

**Fix:** Use `awk` for floating-point arithmetic (more widely available):
```bash
elapsed="$(awk "BEGIN {printf \"%.3f\", $end_time - $start_time}")"
throughput="$(awk "BEGIN {printf \"%.2f\", $n_rows / $elapsed}")"
```

---

### IN-01: Non-deterministic test data (may be intentional)

**File:** `scripts/generate_test_data.py`

**Severity:** Info

**Issue:** The script uses `random` without a seed, producing different output on each run. This is likely intentional for performance testing but means tests cannot reproduce exact datasets.

**Recommendation:** Consider adding `--seed` argument for reproducibility:
```python
parser.add_argument(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility (optional).",
)

if args.seed is not None:
    random.seed(args.seed)
```

---

### IN-02: Missing upper bound enforcement for temp_max after fix

**File:** `scripts/generate_test_data.py` (line 69)

**Severity:** Info

**Issue:** After the fix ensures `temp_max >= temp_min`, temp_max could theoretically exceed 35.0:

```python
temp_max = round(random.uniform(20.0, 35.0), 1)
# If temp_max < temp_min (e.g., 15 < 20):
temp_max = round(temp_min + random.uniform(0.0, 10.0), 1)
# If temp_min = 30, temp_max could become 30 + 10 = 40
```

**Impact:** Minor - spec says temp_max should be in [20.0, 35.0]. Currently, the maximum possible is 35.0 (original) + 10.0 = 45.0 if temp_max < temp_min.

**Recommendation:** Add upper bound check:
```python
if temp_max < temp_min:
    temp_max = min(round(temp_min + random.uniform(0.0, 10.0), 1), 35.0)
```

---

## Files Reviewed

| File | Issues |
|------|--------|
| scripts/generate_test_data.py | IN-01, IN-02 |
| run.sh | CR-01, WR-01 |
| tests/unit/test_generate_test_data.py | None |
| tests/integration/test_perf_test.py | None |
| terraform/modules/eventbridge/VALIDATION.md | None |

## Recommendations

1. **Fix CR-01 immediately** - the perf-test results are being lost
2. **Fix WR-01** for cross-platform compatibility
3. Consider IN-01 for test reproducibility (optional)
4. Consider IN-02 for strict schema compliance (optional)
