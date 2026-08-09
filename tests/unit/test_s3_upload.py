"""Unit tests for tools/s3_upload.py.

Uses unittest.mock to mock boto3 S3 client. Per D-08, boto3 is not
imported directly in unit tests.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestUploadFile(unittest.TestCase):
    """Tests for upload_file() function."""

    @patch("tools.s3_upload.config")
    @patch("tools.s3_upload.Path")
    def test_upload_file_returns_correct_s3_key(self, mock_path_cls, mock_config):
        """Test that upload_file() returns the correct S3 key format."""
        from tools.s3_upload import upload_file

        # Setup mock path
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "test_file.csv"
        mock_path.__str__ = lambda self: "/path/to/test_file.csv"
        mock_path_cls.return_value = mock_path

        # Setup mock S3 client
        mock_s3 = MagicMock()
        mock_config.s3_client.return_value = mock_s3
        mock_config.raw_bucket.return_value = "test-raw"

        # Execute
        result = upload_file("/path/to/test_file.csv")

        # Verify S3 key format
        self.assertEqual(result, "temperaturas/test_file.csv")
        mock_s3.upload_file.assert_called_once_with(
            "/path/to/test_file.csv", "test-raw", "temperaturas/test_file.csv"
        )

    @patch("tools.s3_upload.config")
    @patch("tools.s3_upload.Path")
    def test_upload_file_calls_upload_with_correct_args(self, mock_path_cls, mock_config):
        """Test that upload_file() calls s3.upload_file with correct bucket and key."""
        from tools.s3_upload import upload_file

        # Setup mock path
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "my_data.csv"
        mock_path.__str__ = lambda self: "/data/my_data.csv"
        mock_path_cls.return_value = mock_path

        # Setup mock S3 client
        mock_s3 = MagicMock()
        mock_config.s3_client.return_value = mock_s3
        mock_config.raw_bucket.return_value = "my-project-raw"

        # Execute
        result = upload_file("/data/my_data.csv")

        # Verify correct bucket and key
        mock_s3.upload_file.assert_called_once_with(
            "/data/my_data.csv", "my-project-raw", "temperaturas/my_data.csv"
        )
        self.assertEqual(result, "temperaturas/my_data.csv")

    @patch("tools.s3_upload.config")
    @patch("tools.s3_upload.Path")
    def test_upload_file_raises_on_missing_file(self, mock_path_cls, mock_config):
        """Test that upload_file() raises FileNotFoundError when local file doesn't exist."""
        from tools.s3_upload import upload_file

        # Setup mock path that doesn't exist
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path.__str__ = lambda self: "/nonexistent/file.csv"
        mock_path_cls.return_value = mock_path

        # Execute and verify exception
        with self.assertRaises(FileNotFoundError) as ctx:
            upload_file("/nonexistent/file.csv")

        self.assertIn("File not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
