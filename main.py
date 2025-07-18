"""Main entry point for the ISA MCP Server."""

import argparse
import sys

from src.isa_mcp_server.server import create_mcp_server
from src.isa_mcp_server.validation import (
    DatabaseIntegrityError,
    DatabasePathError,
    DatabasePermissionError,
    validate_db_path,
)


def main():
    parser = argparse.ArgumentParser(description="ISA MCP Server")
    parser.add_argument(
        "--db-path",
        type=str,
        default="isa_docs.db",
        help="Path to the ISA database file (default: isa_docs.db)",
    )
    args = parser.parse_args()

    # Validate database path before server creation
    try:
        validate_db_path(args.db_path)
    except DatabasePathError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DatabasePermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DatabaseIntegrityError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create and run server
    try:
        mcp = create_mcp_server(args.db_path)
        mcp.run()
    except RuntimeError as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
