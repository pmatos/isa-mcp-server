# ISA MCP Server

An MCP (Model Context Protocol) server providing documentation and information about Instruction Set Architectures (ISAs).

## Features

- **Architecture Information**: Get detailed information about different ISAs including x86-64, ARM64, and RISC-V
- **Instruction Documentation**: Look up specific instructions with syntax, operands, and examples
- **Instruction Search**: Search for instructions by name or description
- **Cross-Architecture Comparison**: Compare how instructions are implemented across different architectures

## Supported Architectures

- x86_64 (Intel/AMD 64-bit)
- x86_32 (Intel/AMD 32-bit, i386)
- AArch64 (ARM 64-bit)

The server is designed to easily support additional architectures in the future.

## Installation

```bash
git clone https://github.com/yourusername/isa-mcp-server.git
cd isa-mcp-server
uv sync
```

## Usage

Run the MCP server:

```bash
uv run python main.py
```

### Database Path Configuration

You can specify a custom database path:

```bash
uv run python main.py --db-path /path/to/your/database.db
```

Default database path is `isa_docs.db` in the current directory.

## Resources

The server provides the following resources:

- `isa://architectures` - List all supported architectures
- `isa://architecture/{name}` - Get details about a specific architecture
- `isa://instructions/{arch}` - List instructions for an architecture
- `isa://instruction/{arch}/{name}` - Get details about a specific instruction

## Tools

- `search_instructions` - Search for instructions by name or description
- `compare_instructions` - Compare instruction implementations across architectures

## Database Schema

The server uses a SQLite database to store ISA instruction data. The schema includes:

### Main Tables

#### `instructions`
Stores instruction information with the following fields:
- `id` (INTEGER PRIMARY KEY) - Unique identifier
- `isa` (TEXT) - Instruction set architecture (e.g., "x86")
- `mnemonic` (TEXT) - Instruction mnemonic (e.g., "MOV", "ADD")
- `variant` (TEXT) - Instruction variant (optional)
- `category` (TEXT) - Instruction category (e.g., "DATAXFER", "BINARY")
- `extension` (TEXT) - CPU extension (e.g., "BASE", "SSE", "AVX")
- `isa_set` (TEXT) - ISA subset
- `description` (TEXT) - Human-readable description
- `syntax` (TEXT) - Assembly syntax
- `operands_json` (TEXT) - JSON array of operand information
- `encoding_json` (TEXT) - JSON object with encoding details
- `flags_affected_json` (TEXT) - JSON array of affected CPU flags
- `cpuid_features_json` (TEXT) - JSON array of required CPUID features
- `attributes_json` (TEXT) - JSON array of instruction attributes
- `cpl` (INTEGER) - Required privilege level
- `added_version` (TEXT) - Version when instruction was added
- `deprecated` (BOOLEAN) - Whether instruction is deprecated

#### `instruction_search`
FTS5 full-text search table for fast instruction searching:
- `isa` - Architecture name
- `mnemonic` - Instruction mnemonic
- `description` - Description text
- `category` - Instruction category
- `extension` - CPU extension

#### `import_metadata`
Tracks import operations:
- `id` (INTEGER PRIMARY KEY) - Unique identifier
- `isa` (TEXT) - Architecture imported
- `source_path` (TEXT) - Path to source data
- `import_date` (TIMESTAMP) - When import occurred
- `instruction_count` (INTEGER) - Number of instructions imported
- `source_version` (TEXT) - Version of source data
- `importer_version` (TEXT) - Version of import tool
- `import_duration_seconds` (REAL) - How long import took
- `success` (BOOLEAN) - Whether import succeeded
- `error_message` (TEXT) - Error details if import failed

### JSON Field Formats

#### `operands_json`
Array of operand objects:
```json
[
  {
    "name": "operand_name",
    "type": "register|memory|immediate",
    "access": "r|w|rw",
    "size": "8|16|32|64",
    "visibility": "EXPLICIT|IMPLICIT|SUPPRESSED"
  }
]
```

#### `encoding_json`
Encoding information object:
```json
{
  "pattern": "XED_PATTERN_STRING",
  "opcode": "base_opcode_bytes",
  "prefix": "required_prefixes",
  "modrm": true,
  "sib": false,
  "displacement": "displacement_info",
  "immediate": "immediate_info"
}
```

#### `flags_affected_json`
Array of CPU flags:
```json
["CF", "OF", "SF", "ZF", "AF", "PF"]
```

### Indexes

The database includes indexes for optimal query performance:
- `idx_instructions_isa` - For architecture-specific queries
- `idx_instructions_mnemonic` - For instruction name lookups
- `idx_instructions_category` - For category-based filtering
- `idx_instructions_extension` - For extension-based filtering

### Current Data

The database currently contains:
- **x86 Architecture**: 5,649+ instruction variants covering the complete x86 instruction set
- Full-text search capability across all instruction data
- Comprehensive operand, encoding, and flag information

## Development

### Requirements

- Python 3.13+
- uv (for dependency management)

### Setup

```bash
uv sync --dev
```

### Linting and Formatting

```bash
uv run ruff check src/
uv run ruff format src/
```

### Testing

Test server creation and database connectivity:

```bash
uv run python -c "from src.isa_mcp_server.server import create_mcp_server; mcp = create_mcp_server(); print('Server created successfully')"
```

Test with custom database path:

```bash
uv run python -c "from src.isa_mcp_server.server import create_mcp_server; mcp = create_mcp_server('isa_docs.db'); print('Server created successfully')"
```

### Testing with MCP Inspector

To test the MCP server interactively, you can use the MCP Inspector:

```bash
# Install dependencies (if not already done)
npm install

# Run the inspector
./run-inspector.sh
```

This will open a web interface where you can:
- Test resources like `isa://architectures` and `isa://instructions/x86_64`
- Call tools like `search_instructions` and `compare_instructions`
- See the server's responses in real-time

## License

This project is licensed under the MIT License.
