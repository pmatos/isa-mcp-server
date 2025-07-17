"""ISA MCP Server implementation."""

import logging
from pathlib import Path
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


mcp = FastMCP("ISA MCP Server")

# Initialize database
db = ISADatabase("isa_docs.db")
try:
    db.initialize_database()
except Exception as e:
    logging.warning(f"Failed to initialize database: {e}")
    db = None


@mcp.resource("isa://architectures")
async def list_architectures() -> str:
    """List all supported instruction set architectures."""
    if db:
        try:
            architectures = db.get_supported_isas()
            if architectures:
                return "\n".join(f"- {arch}" for arch in architectures)
        except Exception as e:
            logging.warning(f"Failed to get architectures from database: {e}")
    
    # Fallback to hardcoded data
    architectures = ["x86_64", "x86_32", "AArch64"]
    return "\n".join(f"- {arch}" for arch in architectures)


@mcp.resource("isa://architecture/{name}")
async def get_architecture_info(name: str) -> str:
    """Get detailed information about a specific architecture."""
    arch_data = {
        "x86_64": ArchitectureInfo(
            name="x86_64",
            description="64-bit x86 instruction set architecture",
            word_size=64,
            endianness="little",
            registers=[
                "RAX",
                "RBX",
                "RCX",
                "RDX",
                "RSI",
                "RDI",
                "RBP",
                "RSP",
                "R8-R15",
            ],
            addressing_modes=[
                "immediate",
                "register",
                "memory",
                "indexed",
                "rip-relative",
            ],
        ),
        "x86_32": ArchitectureInfo(
            name="x86_32",
            description="32-bit x86 instruction set architecture (i386)",
            word_size=32,
            endianness="little",
            registers=["EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP"],
            addressing_modes=["immediate", "register", "memory", "indexed"],
        ),
        "AArch64": ArchitectureInfo(
            name="AArch64",
            description="64-bit ARM architecture (ARM64)",
            word_size=64,
            endianness="little",
            registers=["X0-X30", "SP", "PC", "PSTATE", "V0-V31"],
            addressing_modes=[
                "immediate",
                "register",
                "memory",
                "pre-indexed",
                "post-indexed",
                "literal",
            ],
        ),
    }

    if name not in arch_data:
        return f"Architecture '{name}' not found"

    arch = arch_data[name]
    return f"""Architecture: {arch.name}
Description: {arch.description}
Word Size: {arch.word_size} bits
Endianness: {arch.endianness}
Registers: {", ".join(arch.registers)}
Addressing Modes: {", ".join(arch.addressing_modes)}"""


@mcp.resource("isa://instructions/{arch}")
async def list_instructions(arch: str) -> str:
    """List instructions for a specific architecture."""
    if db:
        try:
            # Map common architecture names
            arch_mapping = {
                "x86_64": "x86",
                "x86_32": "x86",
                "AArch64": "aarch64"
            }
            
            db_arch = arch_mapping.get(arch, arch)
            instructions = db.list_instructions(db_arch, limit=100)
            
            if instructions:
                # Get unique mnemonics
                mnemonics = list(set(instr.mnemonic for instr in instructions))
                mnemonics.sort()
                return "\n".join(f"- {instr}" for instr in mnemonics)
        except Exception as e:
            logging.warning(f"Failed to get instructions from database: {e}")
    
    # Fallback to hardcoded data
    instruction_sets = {
        "x86_64": [
            "MOV", "ADD", "SUB", "MUL", "DIV", "JMP", "CMP", "PUSH", "POP", 
            "CALL", "RET", "LEA", "XOR", "AND", "OR"
        ],
        "x86_32": [
            "MOV", "ADD", "SUB", "MUL", "DIV", "JMP", "CMP", "PUSH", "POP", 
            "CALL", "RET", "LEA", "XOR", "AND", "OR"
        ],
        "AArch64": [
            "MOV", "ADD", "SUB", "MUL", "LDR", "STR", "B", "CMP", "BL", 
            "RET", "CBZ", "CBNZ", "AND", "ORR", "EOR"
        ],
    }

    if arch not in instruction_sets:
        return f"Architecture '{arch}' not supported"

    instructions = instruction_sets[arch]
    return "\n".join(f"- {instr}" for instr in instructions)


@mcp.resource("isa://instruction/{arch}/{name}")
async def get_instruction_info(arch: str, name: str) -> str:
    """Get detailed information about a specific instruction."""
    if db:
        try:
            # Map common architecture names
            arch_mapping = {
                "x86_64": "x86",
                "x86_32": "x86",
                "AArch64": "aarch64"
            }
            
            db_arch = arch_mapping.get(arch, arch)
            instruction = db.get_instruction(db_arch, name.upper())
            
            if instruction:
                # Convert operands to string list
                operand_types = [op.type for op in instruction.operands]
                
                # Generate examples (placeholder)
                examples = [f"{name} example1", f"{name} example2"]
                
                return f"""Instruction: {instruction.mnemonic}
Description: {instruction.description}
Syntax: {instruction.syntax}
Operands: {", ".join(operand_types)}
Flags Affected: {", ".join(instruction.flags_affected) if instruction.flags_affected else "None"}
Examples:
{chr(10).join(f"  {ex}" for ex in examples)}"""
        except Exception as e:
            logging.warning(f"Failed to get instruction from database: {e}")
    
    # Fallback to hardcoded data
    instructions = {
        "x86_64": {
            "MOV": InstructionInfo(
                name="MOV",
                description="Move data between registers, memory, and immediate values",
                syntax="MOV destination, source",
                operands=["register", "memory", "immediate"],
                flags_affected=[],
                examples=["MOV RAX, 42", "MOV [RBX], RAX", "MOV RCX, [RDX+8]"],
            ),
            "ADD": InstructionInfo(
                name="ADD",
                description="Add two operands and store result in destination",
                syntax="ADD destination, source",
                operands=["register", "memory", "immediate"],
                flags_affected=["CF", "OF", "SF", "ZF", "AF", "PF"],
                examples=["ADD RAX, RBX", "ADD [RCX], 10", "ADD RSI, [RDI+4]"],
            ),
            "LEA": InstructionInfo(
                name="LEA",
                description="Load effective address",
                syntax="LEA destination, source",
                operands=["register", "memory"],
                flags_affected=[],
                examples=["LEA RAX, [RBX+RCX*2+8]", "LEA RSI, [RDI+16]"],
            ),
        },
        "x86_32": {
            "MOV": InstructionInfo(
                name="MOV",
                description="Move data between registers, memory, and immediate values",
                syntax="MOV destination, source",
                operands=["register", "memory", "immediate"],
                flags_affected=[],
                examples=["MOV EAX, 42", "MOV [EBX], EAX", "MOV ECX, [EDX+8]"],
            ),
            "ADD": InstructionInfo(
                name="ADD",
                description="Add two operands and store result in destination",
                syntax="ADD destination, source",
                operands=["register", "memory", "immediate"],
                flags_affected=["CF", "OF", "SF", "ZF", "AF", "PF"],
                examples=["ADD EAX, EBX", "ADD [ECX], 10", "ADD ESI, [EDI+4]"],
            ),
            "LEA": InstructionInfo(
                name="LEA",
                description="Load effective address",
                syntax="LEA destination, source",
                operands=["register", "memory"],
                flags_affected=[],
                examples=["LEA EAX, [EBX+ECX*2+8]", "LEA ESI, [EDI+16]"],
            ),
        },
        "AArch64": {
            "MOV": InstructionInfo(
                name="MOV",
                description="Move immediate value or register to register",
                syntax="MOV Xd, #imm or MOV Xd, Xm",
                operands=["register", "immediate"],
                flags_affected=[],
                examples=["MOV X0, #42", "MOV X1, X0"],
            ),
            "ADD": InstructionInfo(
                name="ADD",
                description="Add two registers or register and immediate",
                syntax="ADD Xd, Xn, Xm or ADD Xd, Xn, #imm",
                operands=["register", "immediate"],
                flags_affected=["N", "Z", "C", "V"],
                examples=["ADD X0, X1, X2", "ADD X0, X1, #10"],
            ),
            "LDR": InstructionInfo(
                name="LDR",
                description="Load register from memory",
                syntax="LDR Xt, [Xn, #offset] or LDR Xt, [Xn, Xm]",
                operands=["register", "memory"],
                flags_affected=[],
                examples=["LDR X0, [X1, #8]", "LDR X0, [X1, X2]"],
            ),
        },
    }

    if arch not in instructions:
        return f"Architecture '{arch}' not supported"

    if name not in instructions[arch]:
        return f"Instruction '{name}' not found for architecture '{arch}'"

    instr = instructions[arch][name]
    return f"""Instruction: {instr.name}
Description: {instr.description}
Syntax: {instr.syntax}
Operands: {", ".join(instr.operands)}
Flags Affected: {", ".join(instr.flags_affected) if instr.flags_affected else "None"}
Examples:
{chr(10).join(f"  {ex}" for ex in instr.examples)}"""


@mcp.tool("search_instructions")
async def search_instructions(query: str, architecture: Optional[str] = None) -> str:
    """Search for instructions by name or description."""
    if db:
        try:
            # Map common architecture names
            arch_mapping = {
                "x86_64": "x86",
                "x86_32": "x86",
                "AArch64": "aarch64"
            }
            
            db_arch = arch_mapping.get(architecture, architecture) if architecture else None
            instructions = db.search_instructions(query, db_arch)
            
            if instructions:
                results = []
                for instr in instructions:
                    # Map back to user-friendly arch names
                    user_arch = "x86_64" if instr.isa == "x86" else instr.isa
                    results.append(f"{user_arch}: {instr.mnemonic} - {instr.description}")
                return "\n".join(results)
        except Exception as e:
            logging.warning(f"Failed to search instructions in database: {e}")
    
    # Fallback to hardcoded data
    all_instructions = {
        "x86_64": {
            "MOV": "Move data between registers, memory, and immediate values",
            "ADD": "Add two operands and store result in destination",
            "SUB": "Subtract source from destination",
            "MUL": "Multiply operands",
            "DIV": "Divide operands",
            "JMP": "Jump to address",
            "CMP": "Compare operands",
            "PUSH": "Push operand onto stack",
            "POP": "Pop operand from stack",
            "CALL": "Call subroutine",
            "RET": "Return from subroutine",
            "LEA": "Load effective address",
            "XOR": "Exclusive OR operation",
            "AND": "Logical AND operation",
            "OR": "Logical OR operation",
        },
        "x86_32": {
            "MOV": "Move data between registers, memory, and immediate values",
            "ADD": "Add two operands and store result in destination",
            "SUB": "Subtract source from destination",
            "MUL": "Multiply operands",
            "DIV": "Divide operands",
            "JMP": "Jump to address",
            "CMP": "Compare operands",
            "PUSH": "Push operand onto stack",
            "POP": "Pop operand from stack",
            "CALL": "Call subroutine",
            "RET": "Return from subroutine",
            "LEA": "Load effective address",
            "XOR": "Exclusive OR operation",
            "AND": "Logical AND operation",
            "OR": "Logical OR operation",
        },
        "AArch64": {
            "MOV": "Move immediate value or register to register",
            "ADD": "Add two registers or register and immediate",
            "SUB": "Subtract operands",
            "MUL": "Multiply operands",
            "LDR": "Load register from memory",
            "STR": "Store register to memory",
            "B": "Branch to address",
            "CMP": "Compare operands",
            "BL": "Branch with link",
            "RET": "Return from subroutine",
            "CBZ": "Compare and branch if zero",
            "CBNZ": "Compare and branch if not zero",
            "AND": "Logical AND operation",
            "ORR": "Logical OR operation",
            "EOR": "Exclusive OR operation",
        },
    }

    results = []
    search_term = query.lower()

    architectures_to_search = (
        [architecture] if architecture else all_instructions.keys()
    )

    for arch in architectures_to_search:
        if arch not in all_instructions:
            continue

        for instr_name, description in all_instructions[arch].items():
            if search_term in instr_name.lower() or search_term in description.lower():
                results.append(f"{arch}: {instr_name} - {description}")

    if not results:
        return f"No instructions found matching '{query}'"

    return "\n".join(results)


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
        return f"Error comparing instructions: {str(e)}"


if __name__ == "__main__":
    mcp.run()
