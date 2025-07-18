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
    mcp = FastMCP("ISA MCP Server")

    # Initialize database
    db = ISADatabase(db_path)
    try:
        db.initialize_database()
    except Exception as e:
        logging.error(f"Failed to initialize database at {db_path}: {e}")
        raise RuntimeError(f"Cannot start server without database at {db_path}")

    # Store database reference for use in handlers
    mcp._db = db

    return mcp


# Default server instance for backward compatibility
mcp = create_mcp_server()


@mcp.resource("isa://architectures")
async def list_architectures() -> str:
    """List all supported instruction set architectures."""
    try:
        architectures = mcp._db.get_supported_isas()
        if architectures:
            return "\n".join(f"- {arch}" for arch in sorted(architectures))
        else:
            return "No architectures found in database"
    except Exception as e:
        logging.error(f"Failed to get architectures from database: {e}")
        return f"Error accessing database: {e}"


@mcp.resource("isa://architecture/{name}")
async def get_architecture_info(name: str) -> str:
    """Get detailed information about a specific architecture."""
    try:
        # Check if architecture exists in database
        supported_isas = mcp._db.get_supported_isas()
        if name not in supported_isas:
            return f"Architecture '{name}' not found in database"

        # Get instruction count for this architecture
        instruction_count = mcp._db.get_instruction_count(name)

        # Generate basic architecture info from database
        arch_info = {
            "x86_32": {
                "description": "x86 32-bit instruction set architecture",
                "word_size": "32",
                "endianness": "little",
                "registers": "General purpose: EAX, EBX, ECX, EDX, ESI, EDI, EBP, ESP",
                "addressing_modes": "immediate, register, memory, indexed",
            },
            "x86_64": {
                "description": "x86 64-bit instruction set architecture",
                "word_size": "64",
                "endianness": "little",
                "registers": "General: RAX, RBX, RCX, RDX, RSI, RDI, RBP, RSP, R8-R15",
                "addressing_modes": "immediate, register, memory, indexed, rip-rel",
            },
        }

        info = arch_info.get(
            name,
            {
                "description": f"Architecture {name}",
                "word_size": "Unknown",
                "endianness": "Unknown",
                "registers": "Unknown",
                "addressing_modes": "Unknown",
            },
        )

        return f"""Architecture: {name}
Description: {info["description"]}
Word Size: {info["word_size"]} bits
Endianness: {info["endianness"]}
Registers: {info["registers"]}
Addressing Modes: {info["addressing_modes"]}
Instructions Available: {instruction_count}"""
    except Exception as e:
        logging.error(f"Failed to get architecture info: {e}")
        return f"Error accessing architecture information: {e}"


@mcp.resource("isa://instructions/{arch}")
async def list_instructions(arch: str) -> str:
    """List instructions for a specific architecture."""
    try:
        instructions = mcp._db.list_instructions(arch, limit=100)

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


@mcp.resource("isa://instruction/{arch}/{name}")
async def get_instruction_info(arch: str, name: str) -> str:
    """Get detailed information about a specific instruction."""
    try:
        instruction = mcp._db.get_instruction(arch, name.upper())

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


@mcp.tool("search_instructions")
async def search_instructions(query: str, architecture: Optional[str] = None) -> str:
    """Search for instructions by name or description."""
    try:
        instructions = mcp._db.search_instructions(query, architecture)

        if instructions:
            results = []
            for instr in instructions:
                results.append(f"{instr.isa}: {instr.mnemonic} - {instr.description}")
            return "\n".join(results)
        else:
            return f"No instructions found matching '{query}'"
    except Exception as e:
        logging.error(f"Failed to search instructions in database: {e}")
        return f"Error searching instructions: {e}"


@mcp.tool("compare_instructions")
async def compare_instructions(instruction: str, arch1: str, arch2: str) -> str:
    """Compare how an instruction is implemented across different architectures."""
    try:
        info1 = await get_instruction_info(arch1, instruction)
        info2 = await get_instruction_info(arch2, instruction)

        return (
            f"Comparison of '{instruction}' instruction:\n\n"
            f"{arch1}:\n{info1}\n\n{arch2}:\n{info2}"
        )
    except Exception as e:
        logging.error(f"Error comparing instructions: {e}")
        return f"Error comparing instructions: {str(e)}"


if __name__ == "__main__":
    mcp.run()
