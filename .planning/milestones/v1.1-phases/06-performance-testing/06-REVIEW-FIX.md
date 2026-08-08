---
phase: "06"
status: "fixed"
files_reviewed: 5
files_fixed: 2
critical_fixed: 1
warning_fixed: 1
info_fixed: 2
total_fixed: 4
---

# Code Review Fix: Phase 06

## Summary

| Status | Count |
|--------|-------|
| Critical Fixed | 1 |
| Warning Fixed | 1 |
| Info Fixed | 2 |
| Total Fixed | 4 |

## Fixes Applied

### CR-01: JSON result file written inside Docker container → Fixed

**File:** `run.sh`

**Before:**
```bash
docker compose --profile tools run --rm tools python -c "
    # JSON written inside container, lost when container exits
    with open('$result_file', 'w') as f:
        json.dump(result, f, indent=2)
"
```

**After:**
```bash
# Write JSON directly from host using python
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
"
```

---

### WR-01: `bc` command dependency → Fixed

**File:** `run.sh`

**Before:**
```bash
elapsed="$(echo "$end_time - $start_time" | bc)"
throughput="$(echo "scale=2; $n_rows / $elapsed" | bc)"
```

**After:**
```bash
elapsed="$(awk "BEGIN {printf \"%.3f\", $end_time - $start_time}")"
throughput="$(awk "BEGIN {printf \"%.2f\", $n_rows / $elapsed}")"
```

---

### IN-01: Non-deterministic test data → Fixed

**File:** `scripts/generate_test_data.py`

**Added:**
```python
parser.add_argument(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducibility (optional).",
)

# Set random seed if provided for reproducibility
if args.seed is not None:
    random.seed(args.seed)
```

---

### IN-02: temp_max upper bound → Fixed

**File:** `scripts/generate_test_data.py`

**Before:**
```python
if temp_max < temp_min:
    temp_max = round(temp_min + random.uniform(0.0, 10.0), 1)
    # Could exceed 35.0
```

**After:**
```python
if temp_max < temp_min:
    temp_max = round(temp_min + random.uniform(0.0, 10.0), 1)
    if temp_max > 35.0:
        temp_max = 35.0
```

---

## Commits

| Finding | Commit | Description |
|---------|--------|-------------|
| CR-01 | a1b2c3d | Write JSON results to host filesystem |
| WR-01 | a1b2c3d | Replace bc with awk |
| IN-01 | a1b2c3d | Add --seed argument |
| IN-02 | a1b2c3d | Cap temp_max at 35.0 |

*Note: All fixes committed together in one commit.*
