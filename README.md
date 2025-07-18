# ISA MCP Server

An MCP (Model Context Protocol) server providing documentation and information about Instruction Set Architectures (ISAs).

## Features

- **Architecture Information**: Get detailed information about different ISAs including x86-64, ARM64, and RISC-V
- **Instruction Documentation**: Look up specific instructions with syntax, operands, and examples
- **Instruction Search**: Search for instructions by name or description

## Supported Architectures

- x86_64 (Intel/AMD 64-bit)
- x86_32 (Intel/AMD 32-bit, i386)
- AArch64 (ARM 64-bit)

The server is designed to easily support additional architectures in the future.

## Installation

```bash
git clone https://github.com/yourusername/isa-mcp-server.git
cd isa-mcp-server
git submodule update --init --recursive
uv sync
```

## Initial Setup - Importing ISA Data

The server requires ISA instruction and architecture data to be imported into the database. This is now done in a single step:

### Import x86_32 and x86_64 Data

Import both instruction and architecture data from Intel's XED library (included as a submodule):

```bash
# Import Intel x86_32 and x86_64 instructions and metadata from XED
python scripts/import_isa_data.py --intel --source-dir External/xed

# Or import all available ISAs
python scripts/import_isa_data.py --all
```

This will:
- Parse ~11,000+ instruction definitions from XED datafiles for Intel architectures
- Import ~1,000+ instruction definitions from ARM machine-readable data for AArch64
- Extract register definitions for all architectures
- Define addressing modes with examples
- Set architecture specifications (word size, endianness, machine modes)
- Populate the database with x86_32, x86_64, and aarch64 instructions and metadata
- Create the initial `isa_docs.db` database file

### Import AArch64 Data

Import ARM AArch64 instruction and architecture data from ARM's machine-readable data (included as a submodule):

```bash
# Import ARM AArch64 instructions and metadata
python scripts/import_isa_data.py --arm --source-dir External/arm-machine-readable

# Or import with custom database path
python scripts/import_isa_data.py --arm --source-dir External/arm-machine-readable --db-path custom.db
```

### Import Both Intel and ARM

```bash
# Import all available architectures
python scripts/import_isa_data.py --all

# Or import both explicitly
python scripts/import_isa_data.py --intel --arm
```

### Import Instructions Only (Optional)

If you only want to import instructions without architecture metadata:

```bash
# Import only Intel instructions, skip metadata
python scripts/import_isa_data.py --intel --skip-metadata --source-dir External/xed

# Import only ARM instructions, skip metadata
python scripts/import_isa_data.py --arm --skip-metadata --source-dir External/arm-machine-readable
```

### Verification

To verify the import was successful, the script will display a summary:

```
============================================================
IMPORT SUMMARY
============================================================
✓ INTEL   : 9,865 instructions in 12.3s (including architecture metadata)
✓ ARM     : 1,247 instructions in 8.7s (including architecture metadata)
------------------------------------------------------------
Total: 11,112 instructions in 21.0s
Database: isa_docs.db

🎉 Import completed successfully!
```

If you need to verify the architecture metadata separately:

```bash
# Check architecture metadata details
python scripts/populate_architecture_metadata.py --db-path isa_docs.db

# You should see output like:
# X86_32:
#   Description: Intel x86 32-bit instruction set architecture
#   Word Size: 32 bits
#   Registers: 63
#   Addressing Modes: 9
#   Main GPRs: EAX, EBP, EBX, ECX, EDI, EDX, ESI, ESP
#
# X86_64:
#   Description: Intel x86 64-bit instruction set architecture
#   Word Size: 64 bits
#   Registers: 179
#   Addressing Modes: 10
#   Main GPRs: RAX, RBP, RBX, RCX, RDI, RDX, RSI, RSP, R8-R15
```

### Custom Database Location

To use a custom database location:

```bash
# Import with custom database path
python scripts/import_isa_data.py --intel --db-path /path/to/custom.db

# Then run the server with the same path
uv run python main.py --db-path /path/to/custom.db
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

## Database Schema

The server uses a SQLite database to store ISA instruction data and architecture metadata. The schema includes:

### Main Tables

#### `architectures`
Stores architecture metadata:
- `id` (INTEGER PRIMARY KEY) - Unique identifier
- `isa_name` (TEXT) - Architecture name (e.g., "x86_32", "x86_64")
- `word_size` (INTEGER) - Word size in bits (32 or 64)
- `endianness` (TEXT) - Byte order ("little" or "big")
- `description` (TEXT) - Human-readable description
- `machine_mode` (TEXT) - Machine mode (e.g., "LEGACY_32", "LONG_64")

#### `architecture_registers`
Stores register definitions for each architecture:
- `id` (INTEGER PRIMARY KEY) - Unique identifier
- `architecture_id` (INTEGER) - Foreign key to architectures table
- `register_name` (TEXT) - Register name (e.g., "RAX", "EAX")
- `register_class` (TEXT) - Register type (e.g., "gpr", "xmm", "flags")
- `width_bits` (INTEGER) - Register width in bits
- `encoding_id` (INTEGER) - Hardware encoding identifier
- `is_main_register` (BOOLEAN) - Whether this is a primary register

#### `architecture_addressing_modes`
Stores addressing modes for each architecture:
- `id` (INTEGER PRIMARY KEY) - Unique identifier
- `architecture_id` (INTEGER) - Foreign key to architectures table
- `mode_name` (TEXT) - Addressing mode name
- `description` (TEXT) - Mode description
- `example_syntax` (TEXT) - Example assembly syntax

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
- `idx_architectures_isa_name` - For architecture lookups
- `idx_registers_architecture_id` - For register queries by architecture
- `idx_addressing_modes_architecture_id` - For addressing mode queries

### Current Data

The database currently contains:
- **x86_32 Architecture**: 4,314 instruction variants, 63 registers, 9 addressing modes
- **x86_64 Architecture**: 5,551 instruction variants, 179 registers, 10 addressing modes
- **AArch64 Architecture**: 1,247+ instruction variants, 259 registers, 10 addressing modes
- Full-text search capability across all instruction data
- Comprehensive operand, encoding, and flag information
- Complete register specifications including GPRs, SIMD, control, and debug registers
- Detailed addressing mode definitions with example syntax
- Cross-architecture instruction comparison support

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

Run the full test suite:

```bash
# Run all tests
uv run python -m pytest

# Run only unit tests
uv run python -m pytest tests/unit/

# Run only integration tests
uv run python -m pytest tests/integration/

# Run with verbose output
uv run python -m pytest -v
```

Test server creation and database connectivity:

```bash
uv run python -c "from src.isa_mcp_server.server import create_mcp_server; mcp = create_mcp_server(); print('Server created successfully')"
```

Test ARM importer functionality:

```bash
uv run python -c "from src.isa_mcp_server.importers.arm_importer import ARMImporter; from src.isa_mcp_server.isa_database import ISADatabase; db = ISADatabase(':memory:'); importer = ARMImporter(db); print('ARM importer created successfully')"
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
- Call tools like `search_instructions`
- See the server's responses in real-time

## License

This project is licensed under the MIT License.
