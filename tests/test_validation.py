"""Tests for database path validation and security functions."""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.isa_mcp_server.validation import (
    DatabaseIntegrityError,
    DatabasePathError,
    DatabasePermissionError,
    validate_db_path,
)


class TestValidateDbPath:
    """Test database path validation."""

    def test_valid_relative_path(self):
        """Test validation of valid relative path."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            # Create a valid database
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    CREATE TABLE instructions (
                        id INTEGER PRIMARY KEY,
                        isa TEXT,
                        mnemonic TEXT,
                        description TEXT
                    )
                """)
                conn.commit()

            # Test with relative path
            rel_path = os.path.relpath(db_path)
            result = validate_db_path(rel_path)
            assert result.is_file()

    def test_valid_absolute_path_in_cwd(self):
        """Test validation of absolute path within current working directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Change to temp directory
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)

                db_path = Path(tmp_dir) / "test.db"
                # Create a valid database
                with sqlite3.connect(str(db_path)) as conn:
                    conn.execute("""
                        CREATE TABLE instructions (
                            id INTEGER PRIMARY KEY,
                            isa TEXT,
                            mnemonic TEXT,
                            description TEXT
                        )
                    """)
                    conn.commit()

                result = validate_db_path(str(db_path))
                assert result.is_file()
            finally:
                os.chdir(old_cwd)

    def test_system_path_rejection(self):
        """Test that system paths are rejected."""
        system_paths = [
            "/etc/passwd",
            "/usr/bin/python",
            "/var/log/system.log",
            "C:\\Windows\\System32\\config\\sam",
            "C:\\Program Files\\test.db",
        ]

        for path in system_paths:
            with pytest.raises(DatabasePathError) as exc_info:
                validate_db_path(path)
            assert "is not allowed" in str(exc_info.value)

    def test_nonexistent_file_with_valid_parent(self):
        """Test validation of nonexistent file in valid parent directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "nonexistent.db"
            result = validate_db_path(str(db_path))
            assert result.parent == Path(tmp_dir).resolve()

    def test_nonexistent_parent_directory(self):
        """Test error when parent directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "nonexistent" / "test.db"
            with pytest.raises(DatabasePathError) as exc_info:
                validate_db_path(str(db_path))
            assert "Parent directory" in str(exc_info.value)
            assert "does not exist" in str(exc_info.value)

    def test_file_permission_errors(self):
        """Test file permission validation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "readonly.db"

            # Create a valid database
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    CREATE TABLE instructions (
                        id INTEGER PRIMARY KEY,
                        isa TEXT,
                        mnemonic TEXT,
                        description TEXT
                    )
                """)
                conn.commit()

            # Make file read-only
            os.chmod(db_path, 0o444)

            try:
                with pytest.raises(DatabasePermissionError) as exc_info:
                    validate_db_path(str(db_path))
                assert "Cannot write to database file" in str(exc_info.value)
            finally:
                # Restore permissions for cleanup
                os.chmod(db_path, 0o666)

    def test_directory_instead_of_file(self):
        """Test error when path points to directory instead of file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with pytest.raises(DatabasePathError) as exc_info:
                validate_db_path(tmp_dir)
            assert "is not a file" in str(exc_info.value)

    def test_invalid_database_format(self):
        """Test error when file is not a valid SQLite database."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "invalid.db"

            # Create a non-SQLite file
            db_path.write_text("This is not a database")

            with pytest.raises(DatabaseIntegrityError) as exc_info:
                validate_db_path(str(db_path))
            assert "not a valid SQLite database" in str(exc_info.value)

    def test_missing_required_table(self):
        """Test error when database is missing required table."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "incomplete.db"

            # Create a valid SQLite database but without required table
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("CREATE TABLE other_table (id INTEGER)")
                conn.commit()

            with pytest.raises(DatabaseIntegrityError) as exc_info:
                validate_db_path(str(db_path))
            assert "missing required 'instructions' table" in str(exc_info.value)

    def test_missing_required_columns(self):
        """Test error when table is missing required columns."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "incomplete.db"

            # Create a database with instructions table but missing columns
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("CREATE TABLE instructions (id INTEGER)")
                conn.commit()

            with pytest.raises(DatabaseIntegrityError) as exc_info:
                validate_db_path(str(db_path))
            assert "missing required columns" in str(exc_info.value)

    def test_path_traversal_attempts(self):
        """Test that path traversal attempts are handled safely."""
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\Windows\\System32\\config\\sam",
            "/tmp/../etc/passwd",
            "database/../../etc/passwd",
        ]

        for path in dangerous_paths:
            # Some of these might not trigger errors if they resolve to safe paths
            # But they should not allow access to system files
            try:
                result = validate_db_path(path)
                # If validation succeeds, ensure it's not a system path
                assert not str(result).startswith(("/etc", "/usr", "/bin", "/var"))
            except (DatabasePathError, DatabasePermissionError, DatabaseIntegrityError):
                # These exceptions are expected and acceptable
                pass

    def test_absolute_path_outside_cwd_rejected(self):
        """Test that absolute paths outside CWD are rejected."""
        # Use a path that's outside CWD and not in safe/system directories
        external_path = "/data/external.db"

        with pytest.raises(DatabasePathError) as exc_info:
            validate_db_path(external_path)
        assert "outside the project directory" in str(exc_info.value)

    def test_home_directory_allowed(self):
        """Test that paths in user's home directory are allowed."""
        try:
            home = Path.home()
            # Create a test path in home directory
            test_path = home / "test_isa.db"

            # This should not raise an exception for path validation
            # (though it might fail on file existence or permissions)
            try:
                validate_db_path(str(test_path))
            except (DatabasePermissionError, DatabaseIntegrityError):
                # These are acceptable - testing path validation only
                pass
        except RuntimeError:
            # Skip test if home directory is not accessible
            pytest.skip("Home directory not accessible")
