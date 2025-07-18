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

## Resources

The server provides the following resources:

- `isa://architectures` - List all supported architectures
- `isa://architecture/{name}` - Get details about a specific architecture
- `isa://instructions/{arch}` - List instructions for an architecture
- `isa://instruction/{arch}/{name}` - Get details about a specific instruction

## Tools

- `search_instructions` - Search for instructions by name or description
- `compare_instructions` - Compare instruction implementations across architectures

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

```bash
uv run python -c "from src.isa_mcp_server.server import mcp; print('Server imported successfully')"
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
