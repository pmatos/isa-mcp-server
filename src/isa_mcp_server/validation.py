"""Database path validation and security functions."""

import os
import sqlite3
from pathlib import Path
from typing import Union


class ISADatabaseError(Exception):
    """Base exception for ISA database errors."""

    pass


class DatabasePathError(ISADatabaseError):
    """Raised when database path is invalid or insecure."""

    pass


class DatabasePermissionError(ISADatabaseError):
    """Raised when database file permissions are insufficient."""

    pass


class DatabaseIntegrityError(ISADatabaseError):
    """Raised when database format or integrity is invalid."""

    pass


def validate_db_path(db_path: Union[str, Path]) -> Path:
    """
    Validate database path for security and accessibility.

    Args:
        db_path: Path to the database file

    Returns:
        Path: Validated and normalized path

    Raises:
        DatabasePathError: If path is invalid or insecure
        DatabasePermissionError: If file permissions are insufficient
        DatabaseIntegrityError: If database format is invalid
    """
    path = Path(db_path).resolve()

    # Security check: Ensure path is not trying to access system directories
    if _is_system_path(path):
        raise DatabasePathError(
            f"Database path '{path}' is not allowed. "
            "Please use a path in the project directory or a safe location."
        )

    # If absolute path, verify it's in a safe location
    if path.is_absolute():
        cwd = Path.cwd().resolve()
        try:
            path.relative_to(cwd)
        except ValueError:
            # Path is outside current working directory
            # Allow if it's in user's home directory or designated data directories
            if not _is_safe_absolute_path(path):
                raise DatabasePathError(
                    f"Database path '{path}' is outside the project directory. "
                    "For security reasons, please use a path within the project "
                    "or specify a path in your user directory."
                )

    # Check if file exists and validate permissions
    if path.exists():
        if not path.is_file():
            raise DatabasePathError(
                f"Database path '{path}' exists but is not a file. "
                "Please specify a valid database file path."
            )

        # Check read permissions
        if not os.access(path, os.R_OK):
            raise DatabasePermissionError(
                f"Cannot read database file '{path}'. "
                "Please check file permissions and ensure the file is readable."
            )

        # Check write permissions (needed for database operations)
        if not os.access(path, os.W_OK):
            raise DatabasePermissionError(
                f"Cannot write to database file '{path}'. "
                "Please check file permissions and ensure the file is writable."
            )

        # Validate database integrity
        _validate_database_integrity(path)
    else:
        # File doesn't exist - check if parent directory exists and is writable
        parent = path.parent
        if not parent.exists():
            raise DatabasePathError(
                f"Parent directory '{parent}' does not exist. "
                "Please create the directory first or specify an existing directory."
            )

        if not os.access(parent, os.W_OK):
            raise DatabasePermissionError(
                f"Cannot write to directory '{parent}'. "
                "Please check directory permissions."
            )

    return path


def _is_system_path(path: Path) -> bool:
    """Check if path is in a system directory that should be protected."""
    path_str = str(path).lower()

    # Common system directories to protect
    system_dirs = [
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/var",
        "/tmp",
        "/dev",
        "/proc",
        "/sys",
        "/boot",
        "/lib",
        "/lib64",
        "/opt",
        "/srv",
        "/media",
        "/mnt",
        "/root",
    ]

    # Windows system directories
    windows_dirs = [
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
        "c:\\users\\default",
        "c:\\users\\public",
        "c:\\users\\all users",
    ]

    all_system_dirs = system_dirs + windows_dirs

    return any(path_str.startswith(sys_dir) for sys_dir in all_system_dirs)


def _is_safe_absolute_path(path: Path) -> bool:
    """Check if absolute path is in a safe location."""
    path_str = str(path).lower()

    # Allow paths in user's home directory
    try:
        home = Path.home()
        path.relative_to(home)
        return True
    except (ValueError, RuntimeError):
        pass

    # Allow common data directories
    safe_dirs = [
        "/var/lib",
        "/usr/local/share",
        "/opt/local/share",
        "c:\\programdata",
        "c:\\users\\public\\documents",
    ]

    return any(path_str.startswith(safe_dir) for safe_dir in safe_dirs)


def _validate_database_integrity(db_path: Path) -> None:
    """
    Validate that the database file has correct format and required tables.

    Args:
        db_path: Path to the database file

    Raises:
        DatabaseIntegrityError: If database format is invalid
    """
    try:
        # Try to connect to the database
        with sqlite3.connect(str(db_path)) as conn:
            # Check if it's a valid SQLite database
            conn.execute("SELECT 1")

            # Check for required tables
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='instructions'"
            )
            if not cursor.fetchone():
                raise DatabaseIntegrityError(
                    f"Database file '{db_path}' is missing required 'instructions' table. "
                    "Please ensure this is a valid ISA database file."
                )

            # Check basic table structure
            cursor = conn.execute("PRAGMA table_info(instructions)")
            columns = [row[1] for row in cursor.fetchall()]

            required_columns = ["id", "isa", "mnemonic", "description"]
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                raise DatabaseIntegrityError(
                    f"Database file '{db_path}' is missing required columns: {missing_columns}. "
                    "Please ensure this is a valid ISA database file."
                )

    except sqlite3.DatabaseError as e:
        raise DatabaseIntegrityError(
            f"Database file '{db_path}' is not a valid SQLite database: {e}. "
            "Please ensure this is a valid ISA database file."
        ) from e
    except Exception as e:
        raise DatabaseIntegrityError(
            f"Failed to validate database integrity: {e}"
        ) from e
