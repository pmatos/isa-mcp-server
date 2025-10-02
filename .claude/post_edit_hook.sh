#!/bin/bash

# Post-edit hook wrapper for Claude Code
# This script runs ruff linting and formatting and always returns exit code 0
# to prevent Claude Code from hanging on unexpected exit codes

set +e  # Don't exit on command failures

echo "Running ruff check and format..."

# Change to project directory
cd "$CLAUDE_PROJECT_DIR" || {
    echo "Warning: Could not change to project directory $CLAUDE_PROJECT_DIR"
    exit 0
}

# Run ruff check with auto-fix on the entire project
echo "Running ruff check --fix..."
uv run ruff check --fix . 2>&1 || echo "Ruff check completed with warnings/errors"

# Run ruff format on the entire project
echo "Running ruff format..."
uv run ruff format . 2>&1 || echo "Ruff format completed with warnings/errors"

echo "Post-edit hook completed successfully"

# Always return 0 to prevent Claude Code from hanging
exit 0
