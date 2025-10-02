"""Main entry point for the ISA MCP Server."""

import argparse

from src.isa_mcp_server.server import create_mcp_server


def main():
    parser = argparse.ArgumentParser(description="ISA MCP Server")
    parser.add_argument(
        "--db-path",
        type=str,
        default="isa_docs.db",
        help="Path to the ISA database file (default: isa_docs.db)",
    )
    args = parser.parse_args()

    mcp = create_mcp_server(args.db_path)
    mcp.run()


if __name__ == "__main__":
    main()
