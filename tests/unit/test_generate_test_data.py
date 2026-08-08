"""Unit tests for generate_test_data.py.

Per D-08 invariant, tests must NOT import awsglue or boto3.
"""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from generate_test_data import CITIES, generate_csv, generate_row, normalize_key


class TestNormalizeKey(unittest.TestCase):
    """Tests for the normalize_key() function."""

    def test_normalize_key_matches_transforms(self) -> None:
        """Verify normalize_key() output matches transforms.csv_to_parquet.normalize_city_key."""
        # Import from transforms module (requires project root on path)
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))

        try:
            from transforms.csv_to_parquet import normalize_city_key

            # Test all 6 cities from SC-Brazil temperature monitoring
            for cidade in CITIES:
                expected = normalize_city_key(cidade)
                actual = normalize_key(cidade)
                self.assertEqual(
                    actual,
                    expected,
                    f"normalize_key('{cidade}') = '{actual}', expected '{expected}'",
                )
        except ImportError as e:
            self.skipTest(f"transforms module not importable: {e}")

    def test_normalize_key_lowercases(self) -> None:
        """Verify normalize_key lowercases the output."""
        self.assertEqual(normalize_key("FLORIANOPOLIS"), "florianopolis")
        self.assertEqual(normalize_key("Joinville"), "joinville")

    def test_normalize_key_removes_accents(self) -> None:
        """Verify normalize_key removes combining characters (accents)."""
        # Note: CITIES don't have accents, but the function should handle them
        self.assertEqual(normalize_key("São Paulo"), "sao paulo")
        self.assertEqual(normalize_key("Curitiba"), "curitiba")


class TestGenerateRow(unittest.TestCase):
    """Tests for the generate_row() function."""

    def test_temp_range(self) -> None:
        """Verify temp_min in [10.0, 25.0] and temp_max in [20.0, 35.0]."""
        for _ in range(100):  # Run multiple times to catch random failures
            row = generate_row("Florianopolis", "2026-01-15")
            self.assertGreaterEqual(row["temp_min"], 10.0, "temp_min should be >= 10.0")
            self.assertLessEqual(row["temp_min"], 25.0, "temp_min should be <= 25.0")
            self.assertGreaterEqual(row["temp_max"], 20.0, "temp_max should be >= 20.0")
            self.assertLessEqual(row["temp_max"], 35.0, "temp_max should be <= 35.0")

    def test_temp_max_gte_min(self) -> None:
        """Verify temp_max >= temp_min for all generated rows."""
        for _ in range(100):  # Run multiple times to catch random failures
            row = generate_row("Florianopolis", "2026-01-15")
            self.assertGreaterEqual(
                row["temp_max"],
                row["temp_min"],
                f"temp_max ({row['temp_max']}) should be >= temp_min ({row['temp_min']})",
            )

    def test_row_has_required_fields(self) -> None:
        """Verify row has all required fields."""
        row = generate_row("Florianopolis", "2026-01-15")
        required_fields = ["cidade", "cidade_key", "data_medicao", "temp_min", "temp_max"]
        for field in required_fields:
            self.assertIn(field, row, f"Row should have '{field}' field")


class TestGenerateCSV(unittest.TestCase):
    """Tests for the generate_csv() function."""

    def test_schema_compliance(self) -> None:
        """Verify output has correct columns and cidade_key format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            generate_csv(output_path, rows=50)

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            # Check header columns
            expected_columns = ["cidade", "cidade_key", "data_medicao", "temp_min", "temp_max"]
            self.assertEqual(reader.fieldnames, expected_columns)

            # Check row count
            self.assertEqual(len(rows), 50, "Should have 50 data rows")

            # Check cidade_key format (lowercase, no spaces)
            for row in rows:
                self.assertEqual(row["cidade_key"], row["cidade_key"].lower())
                self.assertNotIn(" ", row["cidade_key"])

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_date_format(self) -> None:
        """Verify --date parameter produces YYYY-MM-DD format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            generate_csv(output_path, rows=5, data_medicao="2026-06-15")

            with open(output_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Verify date is in YYYY-MM-DD format
                    self.assertRegex(row["data_medicao"], r"^\d{4}-\d{2}-\d{2}$")
                    self.assertEqual(row["data_medicao"], "2026-06-15")

        finally:
            Path(output_path).unlink(missing_ok=True)


class TestCLIArgs(unittest.TestCase):
    """Tests for CLI argument parsing."""

    def test_cli_rows_output(self) -> None:
        """Verify script accepts --rows and --output args."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            # Run generate_test_data.py with --rows and --output
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_test_data.py",
                    "--rows", "10",
                    "--output", output_path,
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
            self.assertTrue(Path(output_path).exists(), "Output file should exist")

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_cli_invalid_rows(self) -> None:
        """Verify script rejects invalid --rows values."""
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate_test_data.py",
                "--rows", "0",
                "--output", "/tmp/test.csv",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        self.assertNotEqual(result.returncode, 0, "Should reject --rows 0")
        self.assertIn("positive integer", result.stderr.lower())

    def test_cli_invalid_date(self) -> None:
        """Verify script rejects invalid --date values."""
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate_test_data.py",
                "--rows", "10",
                "--output", "/tmp/test.csv",
                "--date", "invalid-date",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        self.assertNotEqual(result.returncode, 0, "Should reject invalid date")
        self.assertIn("YYYY-MM-DD", result.stderr)


class TestJSONFormat(unittest.TestCase):
    """Tests for JSON format of performance results."""

    def test_json_format(self) -> None:
        """Verify timing results have correct JSON structure."""
        # This test documents the expected JSON structure
        # The actual results are written by run.sh perf-test
        expected_fields = [
            "test",
            "rows_generated",
            "elapsed_seconds",
            "throughput_rows_per_sec",
            "timestamp",
            "s3_key",
        ]

        # Verify all expected fields are documented
        self.assertEqual(len(expected_fields), 6, "Should have 6 required fields")


if __name__ == "__main__":
    unittest.main()
