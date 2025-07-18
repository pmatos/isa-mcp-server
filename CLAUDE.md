# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Package Management
```bash
# Install dependencies
uv sync --dev

# Add new dependencies
uv add <package-name>

# Update dependencies
uv sync
```

### Code Quality
```bash
# Run linting
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/

# Check formatting without changes
uv run ruff format --check src/
```

### Running and Testing
```bash
# Run the MCP server
uv run python main.py

# Test server import (basic validation)
uv run python -c "from src.isa_mcp_server.server import mcp; print('Server imported successfully')"

# Type checking
uv run python -m py_compile src/isa_mcp_server/*.py
```

### Build and Distribution
```bash
# Build package
uv build

# Build artifacts are created in dist/
```

## Architecture Overview

This is an **MCP (Model Context Protocol) server** built with **FastMCP** that provides documentation for Instruction Set Architectures (ISAs). 

### Core Components

**MCP Server Implementation** (`src/isa_mcp_server/server.py`):
- **Resources**: URI-based endpoints following pattern `isa://resource-type/parameters`
  - `isa://architectures` - List all supported architectures
  - `isa://architecture/{name}` - Get architecture details
  - `isa://instructions/{arch}` - List instructions for architecture
  - `isa://instruction/{arch}/{name}` - Get instruction details
- **Tools**: Callable functions for interactive operations
  - `search_instructions` - Search by name/description with optional architecture filter
  - `compare_instructions` - Compare instruction implementations across architectures

**Data Models**:
- `InstructionInfo`: Pydantic model for instruction metadata (name, description, syntax, operands, flags, examples)
- `ArchitectureInfo`: Pydantic model for architecture specs (name, description, word_size, endianness, registers, addressing_modes)

### Data Architecture

All instruction and architecture data is **hard-coded within the server** in nested dictionaries for quick lookup. Currently supports:
- **x86_64**: Intel/AMD 64-bit architecture with comprehensive instruction set
- **x86_32**: Intel/AMD 32-bit architecture (i386) with comprehensive instruction set  
- **AArch64**: ARM 64-bit architecture with comprehensive instruction set

The server is designed to easily support additional architectures in the future.

### Entry Points

- `main.py`: Simple entry point that imports and runs the server
- `src/isa_mcp_server/server.py`: Contains all MCP logic and can be run directly

### Development Workflow

**Code Quality Standards**:
- Line length: 88 characters
- Target Python 3.13
- Ruff linting with Error, Pyflakes, Import, and Warning checks
- Double quotes, space indentation

**Project Structure**:
- `src/isa_mcp_server/`: Main package directory
- Build system: hatchling with uv package management
- CI/CD: GitHub Actions with test and build jobs

## Key Implementation Notes

### Adding New Architectures
Extend the data dictionaries in `server.py`:
1. Add to `arch_data` in `get_architecture_info()`
2. Add to `instruction_sets` in `list_instructions()` 
3. Add to `instructions` in `get_instruction_info()`
4. Add to `all_instructions` in `search_instructions()`

### Adding New Resources/Tools
- Use `@mcp.resource("uri-pattern")` decorator for new resources
- Use `@mcp.tool("function-name")` decorator for new tools
- All functions must be async and return strings

### Testing Strategy
Currently minimal testing - only import validation. The server relies on:
- Linting and formatting checks
- Type checking via py_compile
- Import testing to ensure server initializes correctly

### CI/CD Pipeline
GitHub Actions workflow runs on push to main/develop and PRs to main:
- **Test job**: Python 3.13, dependency installation, linting, format checking, type checking, import testing
- **Build job**: Package building and artifact upload

# ISA information

* The submodule `External/xed` contains information about the Intel x86_32/x86_64 ISA.