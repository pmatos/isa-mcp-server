#!/bin/bash

set -e

# Check dependencies
if ! command -v npx &> /dev/null; then
    echo "Error: npx not found. Please install Node.js"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "Error: uv not found. Please install uv"
    exit 1
fi

# Run MCP Inspector with the ISA MCP server
npx @modelcontextprotocol/inspector uv run python main.py
