"""Unit tests for tools/s3_watch.py.

Uses unittest.mock to mock boto3 S3 client and subprocess. Per D-08,
boto3 is not imported directly in unit tests.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestLoadProcessedFiles(unittest.TestCase):
    """Tests for load_processed_files() function."""

    def test_returns_empty_set_when_file_does_not_exist(self):
        """Test that load_processed_files() returns empty set when file doesn't exist."""
        from tools.s3_watch import load_processed_files

        with patch("tools.s3_watch.PROCESSED_FILE", "/nonexistent/processed_files.txt"):
            result = load_processed_files()
            self.assertEqual(result, set())

    def test_loads_existing_processed_files(self):
        """Test that load_processed_files() correctly loads already-processed files."""
        from tools.s3_watch import load_processed_files

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("temperaturas/file1.csv\n")
            f.write("temperaturas/file2.csv\n")
            temp_path = f.name

        try:
            with patch("tools.s3_watch.PROCESSED_FILE", temp_path):
                result = load_processed_files()
                self.assertEqual(result, {"temperaturas/file1.csv", "temperaturas/file2.csv"})
        finally:
            Path(temp_path).unlink()


class TestSaveProcessedFile(unittest.TestCase):
    """Tests for save_processed_file() function."""

    def test_creates_file_with_correct_content(self):
        """Test that save_processed_file() creates file with correct content."""
        from tools.s3_watch import save_processed_file

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "processed_files.txt"
            with patch("tools.s3_watch.PROCESSED_FILE", str(temp_file)):
                save_processed_file("temperaturas/test.csv")

            content = temp_file.read_text()
            self.assertEqual(content, "temperaturas/test.csv\n")

    def test_appends_to_existing_file(self):
        """Test that save_processed_file() appends to existing file."""
        from tools.s3_watch import save_processed_file

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_file = Path(tmpdir) / "processed_files.txt"
            temp_file.write_text("temperaturas/existing.csv\n")
            with patch("tools.s3_watch.PROCESSED_FILE", str(temp_file)):
                save_processed_file("temperaturas/new.csv")

            content = temp_file.read_text()
            self.assertEqual(content, "temperaturas/existing.csv\ntemperaturas/new.csv\n")


class TestPollAndTrigger(unittest.TestCase):
    """Tests for poll_and_trigger() function."""

    @patch("tools.s3_watch.trigger_job")
    @patch("tools.s3_watch.save_processed_file")
    @patch("tools.s3_watch.load_processed_files")
    @patch("tools.s3_watch.config")
    def test_filters_already_processed_files(self, mock_config, mock_load, mock_save, mock_trigger):
        """Test that poll_and_trigger() filters already-processed files."""
        from tools.s3_watch import poll_and_trigger

        # Setup mock S3 client
        mock_s3 = MagicMock()
        mock_config.s3_client.return_value = mock_s3
        mock_config.raw_bucket.return_value = "test-raw"

        # Files in S3
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "temperaturas/processed.csv", "Size": 100},
                {"Key": "temperaturas/new.csv", "Size": 200},
            ]
        }

        # Already processed
        mock_load.return_value = {"temperaturas/processed.csv"}

        # Execute
        result = poll_and_trigger()

        # Only new file should be triggered
        self.assertEqual(result, ["temperaturas/new.csv"])
        mock_trigger.assert_called_once_with("temperaturas/new.csv")
        mock_save.assert_called_once_with("temperaturas/new.csv")

    @patch("tools.s3_watch.trigger_job")
    @patch("tools.s3_watch.save_processed_file")
    @patch("tools.s3_watch.load_processed_files")
    @patch("tools.s3_watch.config")
    def test_skips_directory_objects(self, mock_config, mock_load, mock_save, mock_trigger):
        """Test that poll_and_trigger() skips directory objects (ending with /)."""
        from tools.s3_watch import poll_and_trigger

        # Setup mock S3 client
        mock_s3 = MagicMock()
        mock_config.s3_client.return_value = mock_s3
        mock_config.raw_bucket.return_value = "test-raw"

        # Files in S3 including a directory
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "temperaturas/", "Size": 0},  # Directory
                {"Key": "temperaturas/file.csv", "Size": 100},
            ]
        }

        mock_load.return_value = set()

        # Execute
        result = poll_and_trigger()

        # Only actual file should be triggered, not directory
        self.assertEqual(result, ["temperaturas/file.csv"])
        mock_trigger.assert_called_once_with("temperaturas/file.csv")


class TestTriggerJob(unittest.TestCase):
    """Tests for trigger_job() function."""

    @patch("tools.s3_watch.subprocess.run")
    def test_constructs_correct_docker_compose_command(self, mock_run):
        """Test that trigger_job() constructs correct docker compose command."""
        from tools.s3_watch import trigger_job

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        trigger_job("temperaturas/test.csv")

        # Verify correct command construction
        expected_cmd = [
            "docker",
            "compose",
            "--profile",
            "glue",
            "run",
            "--rm",
            "glue",
            "spark-submit",
            "jobs/csv_to_parquet/job.py",
            "--JOB_NAME",
            "csv_to_parquet",
            "--file-key",
            "temperaturas/test.csv",
        ]
        mock_run.assert_called_once()
        actual_cmd = mock_run.call_args[0][0]
        self.assertEqual(actual_cmd, expected_cmd)

    @patch("tools.s3_watch.subprocess.run")
    def test_uses_list_based_subprocess_args(self, mock_run):
        """Test that trigger_job() uses list-based subprocess args (no shell=True)."""
        from tools.s3_watch import trigger_job

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        trigger_job("temperaturas/test.csv")

        # Verify subprocess.run was called with list, not string
        actual_cmd = mock_run.call_args[0][0]
        self.assertIsInstance(actual_cmd, list)
        self.assertNotIsInstance(actual_cmd, str)


if __name__ == "__main__":
    unittest.main()
