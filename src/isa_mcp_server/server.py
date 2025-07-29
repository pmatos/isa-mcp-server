"""ISA MCP Server implementation."""

import logging
from typing import List, Optional

from fastmcp import FastMCP
from pydantic import BaseModel

from .isa_database import ISADatabase


class InstructionInfo(BaseModel):
    """Information about a specific instruction."""

    name: str
    description: str
    syntax: str
    operands: List[str]
    flags_affected: List[str]
    examples: List[str]


class ArchitectureInfo(BaseModel):
    """Information about an instruction set architecture."""

    name: str
    description: str
    word_size: int
    endianness: str
    registers: List[str]
    addressing_modes: List[str]


def create_mcp_server(db_path: str = "isa_docs.db") -> FastMCP:
    """Create and configure MCP server with database."""
    server = FastMCP("ISA MCP Server")

    # Initialize database
    db = ISADatabase(db_path)
    try:
        db.initialize_database()
    except Exception as e:
        logging.error(f"Failed to initialize database at {db_path}: {e}")
        raise RuntimeError(f"Cannot start server without database at {db_path}")

    # Store database reference for use in handlers
    server._db = db

    # Register resources and tools
    _register_handlers(server)

    return server


def _register_handlers(server: FastMCP):
    """Register all handlers (resources and tools) on the given server."""

    @server.resource("isa://architectures")
    async def list_architectures() -> str:
        """List all supported instruction set architectures."""
        import json

        try:
            architectures = server._db.get_supported_isas()
            if architectures:
                result = {"architectures": sorted(architectures)}
                return json.dumps(result)
            else:
                result = {"architectures": []}
                return json.dumps(result)
        except Exception as e:
            logging.error(f"Failed to get architectures from database: {e}")
            error_result = {"error": f"Error accessing database: {e}"}
            return json.dumps(error_result)

    @server.resource("isa://architecture/{name}")
    async def get_architecture_info(name: str) -> str:
        """Get detailed information about a specific architecture."""
        try:
            # Check if architecture exists in database
            supported_isas = server._db.get_supported_isas()
            if name not in supported_isas:
                return f"Architecture '{name}' not found in database"

            # Get instruction count for this architecture
            instruction_count = server._db.get_instruction_count(name)

            # Get architecture metadata from database
            architecture = server._db.get_architecture(name)
            if not architecture:
                return f"Architecture '{name}' metadata not found in database"

            # Get registers and addressing modes
            registers = server._db.get_architecture_registers(name)
            addressing_modes = server._db.get_architecture_addressing_modes(name)

            # Format register information
            main_gprs = [
                r for r in registers if r.is_main_register and r.register_class == "gpr"
            ]
            main_gpr_names = [r.register_name for r in main_gprs]

            # Get other register classes
            other_regs = {}
            for reg in registers:
                if reg.register_class not in other_regs:
                    other_regs[reg.register_class] = []
                other_regs[reg.register_class].append(reg.register_name)

            # Format addressing modes
            mode_descriptions = []
            for mode in addressing_modes:
                if mode.example_syntax:
                    mode_descriptions.append(
                        f"{mode.mode_name} ({mode.example_syntax})"
                    )
                else:
                    mode_descriptions.append(mode.mode_name)

            # Build comprehensive architecture info
            result = f"""Architecture: {name}
Description: {architecture.description}
Word Size: {architecture.word_size} bits
Endianness: {architecture.endianness}
Machine Mode: {architecture.machine_mode}
"""

            if main_gpr_names:
                result += f"General Purpose Registers: {', '.join(main_gpr_names)}\n"

            # Add other register classes
            for reg_class, reg_names in other_regs.items():
                if reg_class != "gpr" and reg_names:
                    class_name = reg_class.upper()
                    if len(reg_names) > 8:  # Limit display for large register sets
                        truncated = ", ".join(reg_names[:8])
                        total_count = len(reg_names)
                        result += (
                            f"{class_name} Registers: {truncated} "
                            f"... ({total_count} total)\n"
                        )
                    else:
                        result += f"{class_name} Registers: {', '.join(reg_names)}\n"

            if mode_descriptions:
                result += f"Addressing Modes: {', '.join(mode_descriptions)}\n"

            result += f"Instructions Available: {instruction_count}"

            return result
        except Exception as e:
            logging.error(f"Failed to get architecture info: {e}")
            return f"Error accessing architecture information: {e}"

    @server.resource("isa://instructions/{arch}")
    async def list_instructions(arch: str) -> str:
        """List instructions for a specific architecture."""
        try:
            instructions = server._db.list_instructions(arch, limit=100)

            if instructions:
                # Get unique mnemonics
                mnemonics = list(set(instr.mnemonic for instr in instructions))
                mnemonics.sort()
                return "\n".join(f"- {instr}" for instr in mnemonics)
            else:
                return f"No instructions found for architecture '{arch}'"
        except Exception as e:
            logging.error(f"Failed to get instructions from database: {e}")
            return f"Error accessing instructions for '{arch}': {e}"

    @server.resource("isa://instruction/{arch}/{name}")
    async def get_instruction_info(arch: str, name: str) -> str:
        """Get detailed information about a specific instruction."""
        try:
            instruction = server._db.get_instruction(arch, name.upper())

            if instruction:
                # Convert operands to string list
                operand_types = [op.type for op in instruction.operands]

                # Generate basic examples from syntax
                examples = [f"{instruction.syntax}"]

                flags_affected = (
                    ", ".join(instruction.flags_affected)
                    if instruction.flags_affected
                    else "None"
                )

                return f"""Instruction: {instruction.mnemonic}
Description: {instruction.description}
Syntax: {instruction.syntax}
Operands: {", ".join(operand_types)}
Flags Affected: {flags_affected}
Category: {instruction.category}
Extension: {instruction.extension}
Examples:
{chr(10).join(f"  {ex}" for ex in examples)}"""
            else:
                return f"Instruction '{name}' not found for architecture '{arch}'"
        except Exception as e:
            logging.error(f"Failed to get instruction from database: {e}")
            return f"Error accessing instruction '{name}' for '{arch}': {e}"

    @server.tool("search_instructions")
    async def search_instructions(
        query: str, architecture: Optional[str] = None
    ) -> str:
        """Search for instructions by name or description."""
        try:
            instructions = server._db.search_instructions(query, architecture)

            if instructions:
                results = []
                for instr in instructions:
                    results.append(
                        f"{instr.isa}: {instr.mnemonic} - {instr.description}"
                    )
                return "\n".join(results)
            else:
                return f"No instructions found matching '{query}'"
        except Exception as e:
            logging.error(f"Failed to search instructions in database: {e}")
            return f"Error searching instructions: {e}"


# Default server instance for backward compatibility
mcp = create_mcp_server()


if __name__ == "__main__":
    mcp.run()
