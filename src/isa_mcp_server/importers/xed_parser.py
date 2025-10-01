"""XED instruction format parser."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class XEDInstruction:
    """Represents a parsed XED instruction."""

    iclass: str
    uname: Optional[str] = None
    cpl: Optional[int] = None
    category: str = ""
    extension: str = ""
    isa_set: str = ""
    attributes: Optional[List[str]] = None
    pattern: str = ""
    operands: str = ""
    iform: Optional[str] = None
    disasm: Optional[str] = None
    flags: Optional[str] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = []


class XEDParser:
    """Parser for XED instruction format files."""

    def __init__(self):
        self.instruction_pattern = re.compile(r"^\{$")
        self.end_pattern = re.compile(r"^\}$")
        self.field_pattern = re.compile(r"^([A-Z_]+)\s*:\s*(.+)$")
        self.comment_pattern = re.compile(r"^\s*#")
        self.empty_pattern = re.compile(r"^\s*$")

    def parse_file(self, file_path: Path) -> Iterator[XEDInstruction]:
        """Parse XED instruction file and yield instructions."""
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        yield from self._parse_lines(lines)

    def _parse_lines(self, lines: List[str]) -> Iterator[XEDInstruction]:
        """Parse lines and yield instructions."""
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip comments and empty lines
            if self.comment_pattern.match(line) or self.empty_pattern.match(line):
                i += 1
                continue

            # Look for start of instruction block
            if self.instruction_pattern.match(line):
                instruction, next_i = self._parse_instruction_block(lines, i + 1)
                if instruction:
                    yield instruction
                i = next_i
            else:
                i += 1

    def _parse_instruction_block(
        self, lines: List[str], start_idx: int
    ) -> tuple[Optional[XEDInstruction], int]:
        """Parse single instruction block."""
        instruction_data = {}
        i = start_idx

        while i < len(lines):
            line = lines[i].strip()

            # End of instruction block
            if self.end_pattern.match(line):
                break

            # Skip comments and empty lines
            if self.comment_pattern.match(line) or self.empty_pattern.match(line):
                i += 1
                continue

            # Parse field
            match = self.field_pattern.match(line)
            if match:
                field_name = match.group(1)
                field_value = match.group(2).strip()

                # Handle multi-line fields
                if field_name == "PATTERN" and not field_value:
                    # Sometimes PATTERN is on next line
                    i += 1
                    if i < len(lines):
                        field_value = lines[i].strip()

                instruction_data[field_name] = field_value

            i += 1

        # Create instruction object
        if "ICLASS" in instruction_data:
            instruction = XEDInstruction(
                iclass=instruction_data.get("ICLASS", ""),
                uname=instruction_data.get("UNAME"),
                cpl=(
                    int(instruction_data["CPL"])
                    if instruction_data.get("CPL")
                    else None
                ),
                category=instruction_data.get("CATEGORY", ""),
                extension=instruction_data.get("EXTENSION", ""),
                isa_set=instruction_data.get("ISA_SET", ""),
                attributes=self._parse_attributes(
                    instruction_data.get("ATTRIBUTES", "")
                ),
                pattern=instruction_data.get("PATTERN", ""),
                operands=instruction_data.get("OPERANDS", ""),
                iform=instruction_data.get("IFORM"),
                disasm=instruction_data.get("DISASM"),
                flags=instruction_data.get("FLAGS"),
            )
            return instruction, i + 1

        return None, i + 1

    def _parse_attributes(self, attributes_str: str) -> List[str]:
        """Parse attributes string into list."""
        if not attributes_str:
            return []

        # Split by spaces and filter out empty strings
        attributes = [attr.strip() for attr in attributes_str.split() if attr.strip()]
        return attributes

    def _parse_operands(self, operands_str: str) -> List[Dict[str, str]]:
        """Parse operands string into structured format."""
        if not operands_str:
            return []

        operands = []

        # Split operands by spaces, but be careful with colons
        parts = operands_str.split()

        for part in parts:
            if "=" in part and ":" in part:
                # Parse operand like "REG0=GPR8_B():w"
                name_part, rest = part.split("=", 1)
                if ":" in rest:
                    type_part, access_part = rest.rsplit(":", 1)
                    operands.append(
                        {"name": name_part, "type": type_part, "access": access_part}
                    )
                else:
                    operands.append(
                        {
                            "name": name_part,
                            "type": rest,
                            "access": "r",  # default
                        }
                    )
            elif ":" in part:
                # Parse operand like "IMM0:r:b"
                parts_split = part.split(":")
                if len(parts_split) >= 2:
                    operands.append(
                        {
                            "name": parts_split[0],
                            "type": parts_split[2]
                            if len(parts_split) > 2
                            else "unknown",
                            "access": parts_split[1],
                        }
                    )

        return operands

    def _parse_pattern(self, pattern_str: str) -> Dict[str, Any]:
        """Parse pattern string into structured encoding information."""
        if not pattern_str:
            return {}

        encoding = {
            "pattern": pattern_str,
            "opcode": None,
            "modrm": False,
            "sib": False,
            "immediate": False,
            "displacement": False,
        }

        # Extract opcode bytes (hex values at the start)
        hex_pattern = re.compile(r"0x[0-9A-Fa-f]{2}")
        hex_matches = hex_pattern.findall(pattern_str)
        if hex_matches:
            encoding["opcode"] = " ".join(hex_matches)

        # Check for ModR/M byte
        if "MODRM()" in pattern_str or "MOD[" in pattern_str:
            encoding["modrm"] = True

        # Check for SIB byte
        if "SIB()" in pattern_str:
            encoding["sib"] = True

        # Check for immediate values
        imm_types = [
            "UIMM8()",
            "SIMM8()",
            "UIMM16()",
            "SIMM16()",
            "UIMM32()",
            "SIMM32()",
            "SIMMz()",
        ]
        if any(imm in pattern_str for imm in imm_types):
            encoding["immediate"] = True

        # Check for displacement
        if "DISP(" in pattern_str:
            encoding["displacement"] = True

        return encoding

    def _parse_flags(self, flags_str: str) -> List[str]:
        """Parse flags string into list of affected flags."""
        if not flags_str:
            return []

        flags = []

        # XED flags format: MUST [ fc0-u   fc1-mod fc2-u   fc3-u   ]
        # Extract flag conditions
        flag_pattern = re.compile(r"([a-zA-Z]+\d*)-([a-zA-Z]+)")
        matches = flag_pattern.findall(flags_str)

        for flag_name, flag_action in matches:
            if flag_action in ["mod", "w", "set", "clr"]:
                flags.append(flag_name.upper())

        return flags
