#!/usr/bin/env python3
"""Automated performance benchmarking for the ETL pipeline.

Runs performance tests with multiple row counts and generates a summary report.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    rows: int
    elapsed_seconds: float
    throughput_rows_per_sec: float
    timestamp: str
    s3_key: str
    success: bool
    error: str | None = None


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report."""

    test: str = "csv_to_parquet_benchmark"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def total_runs(self) -> int:
        return len(self.results)

    @property
    def successful_runs(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def avg_throughput(self) -> float:
        successful = [r.throughput_rows_per_sec for r in self.results if r.success]
        return sum(successful) / len(successful) if successful else 0.0

    def to_dict(self) -> dict:
        return {
            "test": self.test,
            "timestamp": self.timestamp,
            "summary": {
                "total_runs": self.total_runs,
                "successful_runs": self.successful_runs,
                "avg_throughput_rows_per_sec": round(self.avg_throughput, 2),
            },
            "results": [
                {
                    "rows": r.rows,
                    "elapsed_seconds": round(r.elapsed_seconds, 3),
                    "throughput_rows_per_sec": round(r.throughput_rows_per_sec, 2),
                    "timestamp": r.timestamp,
                    "s3_key": r.s3_key,
                    "success": r.success,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


# Default benchmark configurations
DEFAULT_CONFIGS = [
    ("1K", 1000),
    ("10K", 10000),
    ("100K", 100000),
]


def run_perf_test(n_rows: int) -> BenchmarkResult:
    """Run a single performance test with n_rows.

    Args:
        n_rows: Number of rows to generate.

    Returns:
        BenchmarkResult with timing and status.
    """
    import platform

    print(f"  Running with {n_rows:,} rows... ", end="", flush=True)

    start = time.perf_counter()

    try:
        # On Windows, need to use bash to run run.sh
        if platform.system() == "Windows":
            bash_path = "C:/Program Files/Git/usr/bin/bash.exe"
            cmd = [bash_path, "-c", f"./run.sh perf-test {n_rows}"]
        else:
            cmd = ["bash", "./run.sh", "perf-test", str(n_rows)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
        elapsed = time.perf_counter() - start

        if result.returncode == 0:
            # Parse JSON from output
            for line in result.stdout.splitlines():
                try:
                    data = json.loads(line)
                    if "throughput_rows_per_sec" in data:
                        print("OK")
                        return BenchmarkResult(
                            rows=n_rows,
                            elapsed_seconds=elapsed,
                            throughput_rows_per_sec=data["throughput_rows_per_sec"],
                            timestamp=data.get("timestamp", ""),
                            s3_key=data.get("s3_key", ""),
                            success=True,
                        )
                except json.JSONDecodeError:
                    continue

            # If we got here but returncode was 0, report partial success
            print("OK (no JSON)")
            return BenchmarkResult(
                rows=n_rows,
                elapsed_seconds=elapsed,
                throughput_rows_per_sec=n_rows / elapsed if elapsed > 0 else 0,
                timestamp=datetime.now(UTC).isoformat(),
                s3_key="",
                success=True,
            )
        else:
            print("FAILED")
            return BenchmarkResult(
                rows=n_rows,
                elapsed_seconds=elapsed,
                throughput_rows_per_sec=0,
                timestamp="",
                s3_key="",
                success=False,
                error=result.stderr[:200] if result.stderr else "Unknown error",
            )

    except subprocess.TimeoutExpired:
        print("TIMEOUT")
        return BenchmarkResult(
            rows=n_rows,
            elapsed_seconds=600,
            throughput_rows_per_sec=0,
            timestamp="",
            s3_key="",
            success=False,
            error="Test timed out after 10 minutes",
        )
    except Exception as e:
        print(f"ERROR: {e}")
        return BenchmarkResult(
            rows=n_rows,
            elapsed_seconds=0,
            throughput_rows_per_sec=0,
            timestamp="",
            s3_key="",
            success=False,
            error=str(e),
        )


def run_benchmark(configs: list[tuple[str, int]] | None = None) -> BenchmarkReport:
    """Run benchmark suite with multiple configurations.

    Args:
        configs: List of (name, rows) tuples. Defaults to 1K, 10K, 100K.

    Returns:
        BenchmarkReport with all results.
    """
    if configs is None:
        configs = DEFAULT_CONFIGS

    report = BenchmarkReport()

    print("=" * 60)
    print("ETL Performance Benchmark Suite")
    print("=" * 60)
    print()

    for name, rows in configs:
        print(f"[{name}] {rows:,} rows")
        result = run_perf_test(rows)
        report.results.append(result)
        print()

        # Small delay between runs
        if name != configs[-1][0]:
            time.sleep(2)

    return report


def print_report(report: BenchmarkReport) -> None:
    """Print a formatted benchmark report."""
    print()
    print("=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print()

    print(f"Timestamp: {report.timestamp}")
    print(f"Total Runs: {report.total_runs}")
    print(f"Successful: {report.successful_runs}")
    print(f"Average Throughput: {report.avg_throughput:,.2f} rows/sec")
    print()

    print("-" * 60)
    print(f"{'Rows':>10} {'Time (s)':>10} {'Throughput':>15} {'Status':>10}")
    print("-" * 60)

    for r in report.results:
        status = "OK" if r.success else "FAIL"
        throughput_str = f"{r.throughput_rows_per_sec:,.2f}" if r.success else "-"
        elapsed_str = f"{r.elapsed_seconds:.3f}" if r.success else "-"
        print(f"{r.rows:>10,} {elapsed_str:>10} {throughput_str:>15} rows/s {status:>10}")

    print("-" * 60)
    print()


def save_report(report: BenchmarkReport, output_path: str | None = None) -> None:
    """Save benchmark report to JSON file."""
    if output_path is None:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_path = f"results/benchmark_{timestamp}.json"

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    print(f"Report saved: {output}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run automated ETL performance benchmarks."
    )
    parser.add_argument(
        "--configs",
        type=str,
        help="Comma-separated list of row counts (e.g., '1000,10000,100000')",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for JSON report (default: results/benchmark_TIMESTAMP.json)",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip environment preflight check",
    )

    args = parser.parse_args()

    # Build configs from argument
    configs = None
    if args.configs:
        try:
            rows_list = [int(x.strip()) for x in args.configs.split(",")]
            configs = [(f"{x//1000}K" if x >= 1000 else str(x), x) for x in rows_list]
        except ValueError as e:
            print(f"Error parsing --configs: {e}")
            return 1

    # Preflight check
    if not args.skip_preflight:
        print("Running preflight check...")
        result = subprocess.run(
            ["bash", "-c", "docker info > /dev/null 2>&1 && echo 'OK' || echo 'FAILED'"],
            capture_output=True,
            text=True,
        )
        if "FAILED" in result.stdout:
            print("Error: Docker is not running. Start Docker Desktop and retry.")
            print("Or run with --skip-preflight to bypass this check.")
            return 1
        print("OK\n")

    # Run benchmarks
    report = run_benchmark(configs)

    # Print and save results
    print_report(report)
    save_report(report, args.output)

    # Return exit code based on success rate
    if report.successful_runs == 0:
        return 1
    elif report.successful_runs < report.total_runs:
        return 2  # Partial failure
    return 0


if __name__ == "__main__":
    sys.exit(main())
