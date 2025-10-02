"""ISA MCP Server implementation."""

import json
import logging
from typing import Dict, List, Optional, Set

from fastmcp import FastMCP
from pydantic import BaseModel

from .isa_database import ISADatabase
from .validation import (
    DatabaseIntegrityError,
    DatabasePathError,
    DatabasePermissionError,
    validate_db_path,
)


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


# ISA-agnostic register type mapping
REGISTER_TYPE_MAPPING: Dict[str, str] = {
    # x86/x64 classes
    "gpr": "general-purpose",
    "flags": "flags",
    "segment": "segment",
    "control": "control",
    "debug": "debug",
    "mmx": "multimedia",
    "x87": "floating-point",
    "simd": "vector",
    # AArch64 classes
    "gpr64": "general-purpose",
    "gpr32": "general-purpose",
    "vector": "vector",
    "system": "system",
    # RISC-V classes (future)
    "integer": "general-purpose",
    "float": "floating-point",
    "csr": "control-status",
    # Generic fallback
    "unknown": "special-purpose",
}

# ISA-specific calling conventions
CALLING_CONVENTIONS: Dict[str, Dict[str, Set[str]]] = {
    "x86_64": {
        "preserved": {
            "rbx",
            "rsp",
            "rbp",
            "r12",
            "r13",
            "r14",
            "r15",
            # Sub-registers are also preserved
            "ebx",
            "esp",
            "ebp",
            "r12d",
            "r13d",
            "r14d",
            "r15d",
            "bx",
            "sp",
            "bp",
            "r12w",
            "r13w",
            "r14w",
            "r15w",
            "bl",
            "bh",
            "spl",
            "bpl",
            "r12b",
            "r13b",
            "r14b",
            "r15b",
        },
        "volatile": {
            "rax",
            "rcx",
            "rdx",
            "rsi",
            "rdi",
            "r8",
            "r9",
            "r10",
            "r11",
            # Sub-registers are also volatile
            "eax",
            "ecx",
            "edx",
            "esi",
            "edi",
            "r8d",
            "r9d",
            "r10d",
            "r11d",
            "ax",
            "cx",
            "dx",
            "si",
            "di",
            "r8w",
            "r9w",
            "r10w",
            "r11w",
            "al",
            "ah",
            "cl",
            "ch",
            "dl",
            "dh",
            "sil",
            "dil",
            "r8b",
            "r9b",
            "r10b",
            "r11b",
        },
    },
    "x86_32": {
        "preserved": {
            "ebx",
            "esi",
            "edi",
            "ebp",
            "esp",
            # Sub-registers
            "bx",
            "si",
            "di",
            "bp",
            "sp",
            "bl",
            "bh",
            "sil",
            "dil",
            "bpl",
            "spl",
        },
        "volatile": {
            "eax",
            "ecx",
            "edx",
            # Sub-registers
            "ax",
            "cx",
            "dx",
            "al",
            "ah",
            "cl",
            "ch",
            "dl",
            "dh",
        },
    },
    "aarch64": {
        "preserved": {
            "x19",
            "x20",
            "x21",
            "x22",
            "x23",
            "x24",
            "x25",
            "x26",
            "x27",
            "x28",
            "sp",
            "x29",
            "x30",
            # 32-bit versions
            "w19",
            "w20",
            "w21",
            "w22",
            "w23",
            "w24",
            "w25",
            "w26",
            "w27",
            "w28",
            "w29",
            "w30",
        },
        "volatile": {
            "x0",
            "x1",
            "x2",
            "x3",
            "x4",
            "x5",
            "x6",
            "x7",
            "x8",
            "x9",
            "x10",
            "x11",
            "x12",
            "x13",
            "x14",
            "x15",
            "x16",
            "x17",
            "x18",
            # 32-bit versions
            "w0",
            "w1",
            "w2",
            "w3",
            "w4",
            "w5",
            "w6",
            "w7",
            "w8",
            "w9",
            "w10",
            "w11",
            "w12",
            "w13",
            "w14",
            "w15",
            "w16",
            "w17",
            "w18",
        },
    },
}


class PaginationMetadata(BaseModel):
    """Pagination metadata for paginated responses."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResult(BaseModel):
    """Generic paginated result with metadata."""

    data: List[str]
    pagination: PaginationMetadata


def create_mcp_server(db_path: str = "isa_docs.db") -> FastMCP:
    """Create and configure MCP server with database."""
    server = FastMCP("ISA MCP Server")

    # Validate database path for security and accessibility
    try:
        validated_path = validate_db_path(db_path)
    except DatabasePathError as e:
        logging.error(f"Invalid database path: {e}")
        raise RuntimeError(f"Database path validation failed: {e}") from e
    except DatabasePermissionError as e:
        logging.error(f"Database permission error: {e}")
        raise RuntimeError(f"Database permission error: {e}") from e
    except DatabaseIntegrityError as e:
        logging.error(f"Database integrity error: {e}")
        raise RuntimeError(f"Database integrity error: {e}") from e

    # Initialize database with validated path
    db = ISADatabase(str(validated_path))
    try:
        db.initialize_database()
    except Exception as e:
        logging.error(f"Failed to initialize database at {validated_path}: {e}")
        raise RuntimeError(
            f"Cannot start server: Database initialization failed at {validated_path}. "
            f"Error: {e}"
        ) from e

    # Store database reference for use in handlers
    server._db = db  # type: ignore[attr-defined]

    # Register resources and tools
    _register_handlers(server)

    return server


def _register_handlers(server: FastMCP):
    """Register all handlers (resources and tools) on the given server."""

    @server.resource("isa://architectures")
    async def list_architectures() -> str:
        """List all supported instruction set architectures."""

        try:
            architectures = server._db.get_supported_isas()  # type: ignore[attr-defined]
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
            supported_isas = server._db.get_supported_isas()  # type: ignore[attr-defined]
            if name not in supported_isas:
                return f"Architecture '{name}' not found in database"

            # Get instruction count for this architecture
            instruction_count = server._db.get_instruction_count(name)  # type: ignore[attr-defined]

            # Get architecture metadata from database
            architecture = server._db.get_architecture(name)  # type: ignore[attr-defined]
            if not architecture:
                return f"Architecture '{name}' metadata not found in database"

            # Get registers and addressing modes
            registers = server._db.get_architecture_registers(name)  # type: ignore[attr-defined]
            addressing_modes = server._db.get_architecture_addressing_modes(name)  # type: ignore[attr-defined]

            # Format register information
            main_gprs = [
                r for r in registers if r.is_main_register and r.register_class == "gpr"
            ]
            main_gpr_names = [r.register_name for r in main_gprs]

            # Get other register classes
            other_regs: dict[str, list[str]] = {}
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
            instructions = server._db.list_instructions(arch, limit=100)  # type: ignore[attr-defined]

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
            instruction = server._db.get_instruction(arch, name.upper())  # type: ignore[attr-defined]

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

    @server.resource("isa://architectures/{arch}/instruction-groups")
    async def get_instruction_groups(arch: str) -> str:
        """Get instructions grouped by functional category for an architecture."""

        try:
            # Check if architecture exists
            supported_isas = server._db.get_supported_isas()  # type: ignore[attr-defined]
            if arch not in supported_isas:
                error_result = {"error": f"Architecture '{arch}' not found"}
                return json.dumps(error_result)

            # Get all instructions for this architecture
            instructions = server._db.list_instructions(arch)  # type: ignore[attr-defined]

            if not instructions:
                result: dict[str, dict[str, list[str]]] = {"groups": {}}
                return json.dumps(result)

            # Group instructions by category
            groups: dict[str, list[str]] = {}
            for instruction in instructions:
                category = instruction.category.lower()
                if category not in groups:
                    groups[category] = []

                # Only add if not already present (for unique mnemonics)
                if instruction.mnemonic not in groups[category]:
                    groups[category].append(instruction.mnemonic)

            # Sort instructions within each group
            for category in groups:
                groups[category].sort()

            result = {"groups": groups}
            return json.dumps(result)

        except Exception as e:
            logging.error(f"Failed to get instruction groups from database: {e}")
            error_result = {
                "error": f"Error accessing instruction groups for '{arch}': {e}"
            }
            return json.dumps(error_result)

    @server.resource("isa://architectures/{arch}/registers")
    async def get_architecture_registers(arch: str) -> str:
        """Get complete register definitions with aliases for an architecture."""

        try:
            # Check if architecture exists
            supported_isas = server._db.get_supported_isas()  # type: ignore[attr-defined]
            if arch not in supported_isas:
                error_result = {"error": f"Architecture '{arch}' not found"}
                return json.dumps(error_result)

            # Get all registers with alias information for this architecture
            registers = server._db.get_architecture_registers_with_aliases(arch)  # type: ignore[attr-defined]

            if not registers:
                result: dict[str, list[dict[str, str]]] = {"registers": []}
                return json.dumps(result)

            # Build register definitions with ISA-agnostic information
            register_definitions = []

            for register in registers:
                # Parse aliases from JSON
                aliases = []
                try:
                    if register.aliases_json:
                        aliases = json.loads(register.aliases_json)
                except (json.JSONDecodeError, TypeError):
                    aliases = []

                # Map register class to user-friendly type
                register_type = REGISTER_TYPE_MAPPING.get(
                    register.register_class, "special-purpose"
                )

                # Determine calling convention preservation
                preservation_status = None
                calling_convention = CALLING_CONVENTIONS.get(arch, {})
                preserved_regs = calling_convention.get("preserved", set())
                volatile_regs = calling_convention.get("volatile", set())
                if register.register_name.lower() in preserved_regs:
                    preservation_status = "preserved"
                elif register.register_name.lower() in volatile_regs:
                    preservation_status = "volatile"

                # Override with database value if explicitly set
                if register.calling_convention_preserved is not None:
                    preservation_status = (
                        "preserved"
                        if register.calling_convention_preserved
                        else "volatile"
                    )

                # Build register definition
                reg_def = {
                    "name": register.register_name,
                    "type": register_type,
                    "width_bits": register.width_bits,
                    "is_main_register": register.is_main_register,
                    "aliases": aliases,
                    "calling_convention": preservation_status,
                    "purpose": register.register_purpose,
                }

                # Add encoding information if available
                if register.encoding_id is not None:
                    reg_def["encoding_id"] = register.encoding_id

                # Add parent register reference if this is a sub-register
                if register.parent_register_id is not None:
                    # Find parent register name
                    parent_reg = next(
                        (r for r in registers if r.id == register.parent_register_id),
                        None,
                    )
                    if parent_reg:
                        reg_def["parent_register"] = parent_reg.register_name

                register_definitions.append(reg_def)

            # Sort registers by type, then by name
            register_definitions.sort(key=lambda r: (r["type"], r["name"]))

            result = {"registers": register_definitions}
            return json.dumps(result)

        except Exception as e:
            logging.error(f"Failed to get registers from database: {e}")
            error_result = {"error": f"Error accessing registers for '{arch}': {e}"}
            return json.dumps(error_result)

    @server.tool("search_instructions")
    async def search_instructions(
        query: str, architecture: Optional[str] = None
    ) -> str:
        """Search for instructions by name or description."""
        try:
            instructions = server._db.search_instructions(query, architecture)  # type: ignore[attr-defined]

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

    @server.tool("list_instructions_paginated")
    async def list_instructions_paginated(
        arch: str,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "mnemonic",
        sort_direction: str = "asc",
    ) -> str:
        """List instructions with pagination support."""
        try:
            # Validate inputs
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 500:
                page_size = min(max(page_size, 1), 500)

            # Map common architecture names
            arch_mapping = {"x86_64": "x86", "x86_32": "x86"}
            db_arch = arch_mapping.get(arch, arch)

            # Calculate offset
            offset = (page - 1) * page_size

            # Get total count
            total_items = server._db.get_instruction_count(db_arch)  # type: ignore[attr-defined]

            # Get page of results
            instructions = server._db.list_instructions(  # type: ignore[attr-defined]
                db_arch,
                limit=page_size,
                offset=offset,
                order_by=sort_by,
                order_direction=sort_direction.upper(),
            )

            # Calculate pagination metadata
            total_pages = (total_items + page_size - 1) // page_size
            has_next = page * page_size < total_items
            has_prev = page > 1

            # Format instruction data
            if instructions:
                mnemonics = list(set(instr.mnemonic for instr in instructions))
                mnemonics.sort()
                data = mnemonics
            else:
                data = []

            # Create paginated result
            result = PaginatedResult(
                data=data,
                pagination=PaginationMetadata(
                    page=page,
                    page_size=page_size,
                    total_items=total_items,
                    total_pages=total_pages,
                    has_next=has_next,
                    has_prev=has_prev,
                ),
            )

            return json.dumps(result.model_dump(), indent=2)
        except Exception as e:
            logging.error(f"Failed to get paginated instructions: {e}")
            return f"Error getting paginated instructions for '{arch}': {e}"

    @server.tool("search_instructions_paginated")
    async def search_instructions_paginated(
        query: str,
        architecture: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> str:
        """Search for instructions with pagination support."""
        try:
            # Validate inputs
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 500:
                page_size = min(max(page_size, 1), 500)

            # Map common architecture names
            arch_mapping = {"x86_64": "x86", "x86_32": "x86"}
            db_arch = (
                arch_mapping.get(architecture, architecture) if architecture else None
            )

            # Calculate offset
            offset = (page - 1) * page_size

            # Get total count
            total_items = server._db.get_search_count(query, db_arch)  # type: ignore[attr-defined]

            # Get page of results
            instructions = server._db.search_instructions(  # type: ignore[attr-defined]
                query, db_arch, limit=page_size, offset=offset
            )

            # Calculate pagination metadata
            total_pages = (total_items + page_size - 1) // page_size
            has_next = page * page_size < total_items
            has_prev = page > 1

            # Format instruction data
            if instructions:
                results = []
                for instr in instructions:
                    # Map back to user-friendly arch names
                    user_arch = "x86_64" if instr.isa == "x86" else instr.isa
                    results.append(
                        f"{user_arch}: {instr.mnemonic} - {instr.description}"
                    )
                data = results
            else:
                data = []

            # Create paginated result
            result = PaginatedResult(
                data=data,
                pagination=PaginationMetadata(
                    page=page,
                    page_size=page_size,
                    total_items=total_items,
                    total_pages=total_pages,
                    has_next=has_next,
                    has_prev=has_prev,
                ),
            )

            return json.dumps(result.model_dump(), indent=2)
        except Exception as e:
            logging.error(f"Failed to search instructions with pagination: {e}")
            return f"Error searching instructions with pagination: {e}"


# Default server instance for backward compatibility
mcp = create_mcp_server()


if __name__ == "__main__":
    mcp.run()
