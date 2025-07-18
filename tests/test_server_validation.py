"""Tests for server database validation integration."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.isa_mcp_server.server import create_mcp_server


class TestServerValidation:
    """Test server creation with database validation."""

    def test_server_creation_with_valid_database(self):
        """Test successful server creation with valid database."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"

            # Create a valid database with proper schema
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    CREATE TABLE instructions (
                        id INTEGER PRIMARY KEY,
                        isa TEXT NOT NULL,
                        mnemonic TEXT NOT NULL,
                        description TEXT,
                        category TEXT NOT NULL,
                        extension TEXT NOT NULL,
                        isa_set TEXT NOT NULL,
                        syntax TEXT,
                        operands_json TEXT,
                        encoding_json TEXT,
                        flags_affected_json TEXT,
                        cpuid_features_json TEXT,
                        attributes_json TEXT,
                        cpl INTEGER,
                        added_version TEXT,
                        deprecated BOOLEAN DEFAULT FALSE,
                        variant TEXT,
                        UNIQUE(isa, mnemonic, variant)
                    )
                """)
                conn.commit()

            # Server creation should succeed
            mcp = create_mcp_server(str(db_path))
            assert mcp is not None
            assert hasattr(mcp, "_db")

    def test_server_creation_with_invalid_path(self):
        """Test server creation failure with invalid database path."""
        with pytest.raises(RuntimeError) as exc_info:
            create_mcp_server("/etc/passwd")
        assert "Database path validation failed" in str(exc_info.value)

    def test_server_creation_with_permission_error(self):
        """Test server creation failure with permission error."""
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
            import os

            os.chmod(db_path, 0o444)

            try:
                with pytest.raises(RuntimeError) as exc_info:
                    create_mcp_server(str(db_path))
                assert "Database permission error" in str(exc_info.value)
            finally:
                # Restore permissions for cleanup
                os.chmod(db_path, 0o666)

    def test_server_creation_with_invalid_database(self):
        """Test server creation failure with invalid database format."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "invalid.db"

            # Create a non-SQLite file
            db_path.write_text("This is not a database")

            with pytest.raises(RuntimeError) as exc_info:
                create_mcp_server(str(db_path))
            assert "Database integrity error" in str(exc_info.value)

    def test_server_creation_with_missing_table(self):
        """Test server creation failure with missing required table."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "incomplete.db"

            # Create a valid SQLite database but without required table
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("CREATE TABLE other_table (id INTEGER)")
                conn.commit()

            with pytest.raises(RuntimeError) as exc_info:
                create_mcp_server(str(db_path))
            assert "Database integrity error" in str(exc_info.value)

    def test_server_creation_with_nonexistent_file(self):
        """Test server creation with nonexistent database file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "nonexistent.db"

            # Server creation should succeed (database will be created)
            mcp = create_mcp_server(str(db_path))
            assert mcp is not None
            assert hasattr(mcp, "_db")

            # Verify the database file was created
            assert db_path.exists()

    def test_server_creation_with_default_path(self):
        """Test server creation with default database path."""
        # Clean up any existing default database
        default_db = Path("isa_docs.db")
        if default_db.exists():
            default_db.unlink()

        try:
            # Server creation should succeed with default path
            mcp = create_mcp_server()
            assert mcp is not None
            assert hasattr(mcp, "_db")

            # Verify the database file was created
            assert default_db.exists()
        finally:
            # Clean up
            if default_db.exists():
                default_db.unlink()
