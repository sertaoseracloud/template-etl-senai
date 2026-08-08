# Phase 6: Performance Testing - Research

**Researched:** 2026-08-08
**Domain:** Dynamic test data generation and performance benchmarking for ETL pipelines
**Confidence:** HIGH

## Summary

Phase 6 adds two capabilities: (1) a configurable CSV test data generator (`scripts/generate_test_data.py`) that creates N-row datasets matching the existing temperaturas schema, and (2) a performance test runner integrated into `run.sh` (`perf-test` subcommand) that uploads generated data, runs the full pipeline, and logs structured throughput metrics. The implementation uses only Python stdlib — `csv` for generation and `time.perf_counter()` for timing — to keep the toolchain minimal and reproducible.

**Primary recommendation:** Build `scripts/generate_test_data.py` as a stdlib-only script with `argparse`, `csv`, `random`, and `unicodedata` (for `normalize_city_key`). Add `cmd_perf_test()` to `run.sh` that wires generate → upload → job → log into a single command.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSV test data generation | API/Backend (Python script) | — | Pure computation, no service dependency |
| Configurable row count | API/Backend | — | CLI argument parsing, loop generation |
| Schema compliance (cidade_key) | API/Backend | — | Must match `normalize_city_key()` in transforms |
| S3 upload of generated data | API/Backend (tools/s3_upload.py) | — | Reuses existing upload_file() |
| Glue job execution | API/Backend (run.sh glue profile) | — | Existing job.py infrastructure |
| Performance timing | API/Backend | — | `time.perf_counter()` for wall-clock accuracy |
| Structured JSON logging | API/Backend | — | `json.dumps()` to file/stdout |

## Standard Stack

### Core (Phase 6 additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `csv` | built-in | Write CSV rows efficiently | No external dependency, sufficient for N < 10M rows |
| Python stdlib `argparse` | built-in | CLI argument parsing | Stdlib, consistent with job.py pattern |
| Python stdlib `random` | built-in | Random temperature generation | Sufficient for synthetic test data |
| Python stdlib `time` | built-in | `perf_counter()` for timing | Highest-resolution monotonic clock in stdlib |
| Python stdlib `json` | built-in | Structured log output | Stdlib, no serialization library needed |
| Python stdlib `unicodedata` | built-in | `normalize_city_key()` | Replicates transform logic without Spark dependency |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `csv` | `pandas.DataFrame.to_csv()` | Pandas adds ~100 MB image weight; csv is sufficient for generation |
| stdlib `random` | `numpy.random` | NumPy adds dependency; stdlib random.uniform() is sufficient |
| Custom city_key logic | Import from transforms | D-08 forbids Spark imports in non-job context; must inline |

## Test Data Generation

### Generator Pattern

The generator must produce CSV rows matching the existing sample schema:

```
cidade,cidade_key,data_medicao,temp_min,temp_max
Florianópolis,florianopolis,2026-01-15,21.5,29.8
```

**Key constraints from schema:**

| Field | Source | Constraint |
|-------|--------|------------|
| `cidade` | Static list | 6 cities: Florianopolis, Joinville, Blumenau, Chapeco, Lages, Criciuma (with accents) |
| `cidade_key` | Derived | `unicodedata.normalize("NFKD", cidade).encode("ascii", "ignore").decode().lower()` — replicates `normalize_city_key()` |
| `data_medicao` | CLI or random | YYYY-MM-DD format, default to single date for test data |
| `temp_min` | Random | Range 10.0–25.0 C (SC winter lows) |
| `temp_max` | Random | Range 20.0–35.0 C (SC summer highs), must be > temp_min |

**Row generation loop:**

```python
# Source: pattern derived from data/sample/*.csv (6 cities per date)
import csv, random, unicodedata

CITIES = [
    "Florianópolis", "Joinville", "Blumenau",
    "Chapecó", "Lages", "Criciúma"
]

def normalize_key(cidade: str) -> str:
    nfkd = unicodedata.normalize("NFKD", cidade)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

with open(output, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["cidade", "cidade_key", "data_medicao", "temp_min", "temp_max"])
    for _ in range(n_rows):
        cidade = random.choice(CITIES)
        writer.writerow([
            cidade,
            normalize_key(cidade),
            date_str,
            round(random.uniform(10.0, 25.0), 1),
            round(random.uniform(20.0, 35.0), 1),
        ])
```

### CLI Interface (PERF-01, PERF-02)

```bash
python scripts/generate_test_data.py --rows 10000 --output /tmp/test.csv
python scripts/generate_test_data.py --rows 50000 --output data/perf/50k.csv --date 2026-01-20
python scripts/generate_test_data.py --rows 100000 --output data/perf/100k.csv
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--rows` | Yes | — | Number of data rows to generate |
| `--output` | Yes | — | Output CSV path |
| `--date` | No | `2026-01-15` | Data measurement date (YYYY-MM-DD) |
| `--schema` | No | `temperaturas` | Schema name (reserved for future; validates output path) |

### Scalability Considerations

- **N < 100K rows:** stdlib `csv` with `csv.writer` is fast enough (< 2 sec).
- **N > 1M rows:** Consider `io.StringIO` buffer + single `f.write()` to avoid row-by-row I/O overhead, or chunked writing with 10K-row batches.
- **Memory:** Generator uses O(1) memory — writes row-by-row, does not hold dataset in memory.

## Performance Timing & Logging

### Timing Methodology

Use `time.perf_counter()` (monotonic, highest-resolution) for wall-clock measurements:

```python
import time, json
from pathlib import Path

start = time.perf_counter()

# ... ETL pipeline execution ...

end = time.perf_counter()
elapsed = end - start
throughput = rows_read / elapsed if elapsed > 0 else 0

result = {
    "test": "csv_to_parquet_perf",
    "rows_generated": n_rows,
    "rows_read": rows_read,
    "rows_written": rows_written,
    "elapsed_seconds": round(elapsed, 3),
    "throughput_rows_per_sec": round(throughput, 2),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "data_file": output_path,
    "s3_key": s3_key,
}
print(json.dumps(result, indent=2))
```

### Timing Granularity

| Phase | What to Time | Where |
|-------|-------------|-------|
| Data generation | `generate_test_data.py` wall clock | Script itself, logged separately |
| S3 upload | Upload phase | `cmd_perf_test()` in run.sh |
| Glue job | Full Spark job (from `spark-submit` to `job.commit()`) | job.py logs |
| End-to-end | Generate → Upload → Job | `cmd_perf_test()` in run.sh |

### JSON Log Format (PERF-05)

```json
{
  "test": "csv_to_parquet_perf",
  "rows_generated": 10000,
  "rows_read": 10000,
  "rows_written": 10000,
  "elapsed_seconds": 12.345,
  "throughput_rows_per_sec": 810.05,
  "timestamp": "2026-08-08T10:30:00.123456+00:00",
  "data_file": "/tmp/perf_test_10k.csv",
  "s3_key": "temperaturas/perf_test_10k.csv",
  "phases": {
    "generate_seconds": 0.045,
    "upload_seconds": 0.120,
    "job_seconds": 12.180
  }
}
```

**Log destination:** Write to `results/perf-{timestamp}.json` and also print to stdout for CI capture.

## run.sh Integration

### New Subcommand: `perf-test`

Add to `usage()` help block and `cmd_` dispatch in `run.sh`:

```bash
perf-test  Run performance test with N rows of generated data
```

### cmd_perf_test() Implementation

```bash
cmd_perf_test() {
  local n_rows="${1:-}"
  if [ -z "$n_rows" ]; then
    echo "Usage: ./run.sh perf-test <n_rows>" >&2
    exit 1
  fi

  preflight

  local tmp_csv
  tmp_csv="$(mktemp --suffix=.csv)"
  local timestamp
  timestamp="$(date +%Y%m%d_%H%M%S)"
  local result_file="results/perf-${timestamp}.json"

  mkdir -p results

  # Step 1: Generate test data
  run_step "generate ${n_rows} rows" docker compose --profile tools run --rm tools \
    python scripts/generate_test_data.py --rows "$n_rows" --output "$tmp_csv"

  # Step 2: Upload to S3
  local s3_key
  s3_key="$(run_step "upload test data" docker compose --profile tools run --rm tools \
    python -c "
import sys; sys.path.insert(0, '/workspace')
from tools.s3_upload import upload_file
print(upload_file('$tmp_csv'))
" | tail -n1)"

  # Step 3: Run Glue job with the uploaded file
  run_step "run csv_to_parquet job (${n_rows} rows)" docker compose --profile glue run --rm glue \
    spark-submit jobs/csv_to_parquet/job.py --JOB_NAME csv_to_parquet --file-key "$s3_key"

  # Step 4: Log result
  cat > "$result_file" << EOF
{
  "test": "csv_to_parquet_perf",
  "rows_generated": $n_rows,
  "s3_key": "$s3_key",
  "timestamp": "$(date -Iseconds)"
}
EOF

  echo "Results: $result_file"
  rm -f "$tmp_csv"
}
```

### Dispatch Update

```bash
# In case statement, add perf-test to allowed subcommands:
up|down|bootstrap|seed|upload|watch|job|test|lint|demo|perf-test)

# In cmd dispatch:
perf-test) cmd_perf_test "$2" ;;
```

**Note:** `run_step` already handles extra arguments correctly for `perf-test` — it is the only subcommand that takes a positional argument (n_rows).

## Common Pitfalls

### Pitfall 1: cidade_key Mismatch
**What goes wrong:** Generated CSV has `cidade_key` that does not match what `normalize_city_key()` produces in Spark, causing partition key mismatches or empty output.
**Why it happens:** Accent normalization in Python and Java/Spark use different Unicode libraries; NFKD normalization is consistent but the combining-character removal must match exactly.
**How to avoid:** Inline the exact same logic from `transforms/csv_to_parquet.py` (NFKD + filter combining + lower).
**Warning signs:** Job runs but produces 0 output rows, or partitions use wrong cidade_key values.

### Pitfall 2: temp_max < temp_min
**What goes wrong:** Generated temperatures violate domain logic (max must be >= min).
**How to avoid:** Generate `temp_min` first, then `temp_max = max(temp_min, random.uniform(min_max, max_max))`.

### Pitfall 3: Large CSV Memory Pressure
**What goes wrong:** For N > 1M rows, `csv.writer()` row-by-row can be slow.
**How to avoid:** Use buffered writing or batch generation in chunks of 50K rows.
**Warning signs:** Generation takes > 30 seconds for 100K rows on standard hardware.

### Pitfall 4: Spark Job Reads Entire Directory
**What goes wrong:** When `--file-key` is provided, `read_csv(spark, raw_path)` with `s3a://bucket/temperaturas/file.csv` works, but the job still falls back to reading the entire prefix if file_key is not correctly parsed.
**Why it happens:** `job.py` logic checks `file_key` before constructing the path; if s3_key returned from upload has a trailing `/` or unexpected prefix, path construction fails.
**How to avoid:** Verify s3_key format is `temperaturas/{filename}` — matches `upload_file()` in `tools/s3_upload.py`.

### Pitfall 5: Result Directory Not Created
**What goes wrong:** `results/perf-*.json` write fails because `results/` does not exist.
**How to avoid:** `mkdir -p results` before writing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV generation | Custom file writer with string formatting | Python stdlib `csv` | Handles quoting, escaping, newline edge cases correctly |
| Performance timing | `time.time()` (wall clock, can jump) | `time.perf_counter()` | Monotonic, nanosecond resolution |
| JSON logging | Manual string formatting | `json.dumps()` with indent | Handles escaping, types, pretty-print automatically |
| City key normalization | String replace tricks | `unicodedata.normalize("NFKD", ...)` | Matches exact Spark/Java Unicode behavior |

## Code Examples

### generate_test_data.py (complete script)

```python
#!/usr/bin/env python3
"""Generate synthetic temperaturas CSV data for performance testing.

Usage:
    python scripts/generate_test_data.py --rows N --output <path> [--date YYYY-MM-DD]

Schema: cidade, cidade_key, data_medicao, temp_min, temp_max
Cities: Florianopolis, Joinville, Blumenau, Chapeco, Lages, Criciuma (with accents)
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
import unicodedata
from datetime import date
from pathlib import Path

CITIES = [
    "Florianópolis",
    "Joinville",
    "Blumenau",
    "Chapecó",
    "Lages",
    "Criciúma",
]


def normalize_key(cidade: str) -> str:
    """Normalize city name to partition-safe key.

    Mirrors transforms.csv_to_parquet.normalize_city_key() without Spark.
    """
    nfkd = unicodedata.normalize("NFKD", cidade)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def generate_row(date_str: str) -> list:
    cidade = random.choice(CITIES)
    temp_min = round(random.uniform(10.0, 25.0), 1)
    temp_max = round(max(temp_min + 0.5, random.uniform(20.0, 35.0)), 1)
    return [cidade, normalize_key(cidade), date_str, temp_min, temp_max]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic temperaturas CSV data")
    parser.add_argument("--rows", type=int, required=True, help="Number of data rows")
    parser.add_argument("--output", type=str, required=True, help="Output CSV path")
    parser.add_argument(
        "--date", type=str, default="2026-01-15", help="Date (YYYY-MM-DD, default: 2026-01-15)"
    )
    parser.add_argument("--schema", type=str, default="temperaturas", help="Schema name (unused, reserved)")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["cidade", "cidade_key", "data_medicao", "temp_min", "temp_max"])
        for _ in range(args.rows):
            writer.writerow(generate_row(args.date))

    print(f"Generated {args.rows} rows -> {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Performance test result logger

```python
import json, time
from datetime import datetime, timezone

def log_perf_result(n_rows: int, elapsed: float, s3_key: str, output_path: str) -> dict:
    result = {
        "test": "csv_to_parquet_perf",
        "rows_generated": n_rows,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_rows_per_sec": round(n_rows / elapsed, 2) if elapsed > 0 else 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "s3_key": s3_key,
        "data_file": output_path,
    }
    print(json.dumps(result, indent=2))
    return result
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | stdlib `csv` is sufficient for N <= 100K rows | Test Data Generation | Underestimated I/O time for very large datasets; chunked writing would be needed |
| A2 | 6 cities are the complete set (no new cities will be added) | Test Data Generation | New cities added to schema would need generator update |
| A3 | `normalize_city_key()` in transforms uses exact NFKD+combining-filter pattern | Test Data Generation | If transforms logic changes, generated keys may diverge |

## Open Questions

1. **Should `--schema` parameter accept a path to `temperaturas.json` for validation?**
   - Pro: Self-documenting, future-proof for new schemas
   - Con: Adds complexity; PERF-02 says "match existing schema" which implies hardcoding
   - Recommendation: Reserve `--schema` flag for now, validate against hardcoded schema

2. **Should performance tests be run as part of `pytest` suite?**
   - Current PERF-04/PERF-05 scope is CLI-based (`./run.sh perf-test`)
   - Integration with pytest would require `@pytest.mark.perf` markers and separate test config
   - Recommendation: Keep CLI-only for this phase; pytest integration as a future enhancement

3. **What row counts should be tested as defaults?**
   - Small: 1K rows (fast feedback, < 5 sec)
   - Medium: 10K rows (comparable to production batch)
   - Large: 100K rows (stress test)
   - Recommendation: Test with 10K and 100K as standard benchmarks

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All scripts | Project env | py311 | — |
| Docker + docker compose | run.sh | Verified by preflight() | v2 | Blocked |
| Floci emulator | S3 upload, job execution | Via docker compose | latest | None |
| tools/s3_upload.py | S3 upload in perf-test | Already implemented | — | None |
| jobs/csv_to_parquet/job.py | ETL job execution | Already implemented | — | None |

**All dependencies satisfied:** No external tools required beyond existing project infrastructure.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project test infra) |
| Config file | `tests/conftest.py` (existing) |
| Quick run command | `pytest tests/unit/test_generate_test_data.py -x` |
| Full suite command | `pytest tests/ -m "not athena"` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Command | File Exists? |
|--------|----------|-----------|---------|--------------|
| PERF-01 | Script accepts --rows and --output | Unit | `pytest tests/unit/test_generate_test_data.py::test_cli_rows_output` | Create |
| PERF-02 | Output matches schema (columns, cidade_key) | Unit | `pytest tests/unit/test_generate_test_data.py::test_schema_compliance` | Create |
| PERF-03 | perf-test subcommand wires generate+upload+job | Integration | `pytest tests/integration/test_perf_test.py` | Create |
| PERF-04 | Execution time and throughput logged | Unit | `pytest tests/unit/test_generate_test_data.py::test_timing_logged` | Create |
| PERF-05 | Results in JSON format | Unit | `pytest tests/unit/test_generate_test_data.py::test_json_format` | Create |

### Wave 0 Gaps
- [ ] `tests/unit/test_generate_test_data.py` — PERF-01, PERF-02, PERF-04, PERF-05
- [ ] `tests/integration/test_perf_test.py` — PERF-03 (run.sh perf-test integration)
- [ ] `scripts/generate_test_data.py` — core implementation
- [ ] `run.sh` update — `cmd_perf_test()` and dispatch update
- [ ] `results/` directory creation (mkdir in run.sh, not committed to git)

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | Partial | `argparse` type validation on --rows (positive int); CSV data is synthetic |
| V4 Access Control | No | Test data only; no user data or auth involved |

### Known Threat Patterns
| Pattern | Applies | Mitigation |
|---------|---------|------------|
| Path traversal in --output | Yes | `Path(output).parent.mkdir()` is safe; output is local temp file |
| Command injection via args | No | argparse passes strings, no shell evaluation |
| Large file DoS | Partial | N is user-controlled; cap at reasonable limit (e.g., 10M rows = ~500MB CSV) |

## Sources

### Primary (HIGH confidence)
- `transforms/csv_to_parquet.py` — normalize_city_key() implementation [VERIFIED: transforms/csv_to_parquet.py:43-69]
- `transforms/csv_to_parquet.py` — read_csv/write_parquet signatures [VERIFIED: transforms/csv_to_parquet.py:76-152]
- `jobs/csv_to_parquet/job.py` — --file-key parameter and path construction [VERIFIED: jobs/csv_to_parquet/job.py:88-123]
- `tools/s3_upload.py` — upload_file() returns s3_key [VERIFIED: tools/s3_upload.py:21-44]
- `run.sh` — run_step() helper, cmd_upload() pattern [VERIFIED: run.sh:47-173]
- `data/sample/temperaturas_2026-01-15.csv` — CSV format [VERIFIED: data/sample/temperaturas_2026-01-15.csv:1-7]
- `catalog/schema/temperaturas.json` — table schema [VERIFIED: catalog/schema/temperaturas.json:1-46]

### Secondary (MEDIUM confidence)
- Python stdlib documentation — csv, argparse, time.perf_counter, json [CITED: docs.python.org/3/library/]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components are stdlib or already-implemented project code
- Architecture: HIGH — wiring existing components (generate, upload, job) is straightforward
- Pitfalls: MEDIUM — unicode normalization edge cases require verification against actual Spark behavior

**Research date:** 2026-08-08
**Valid until:** 2026-09-08 (30 days — Python stdlib patterns are stable)
