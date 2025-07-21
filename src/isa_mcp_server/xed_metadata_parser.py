"""XED metadata parser for extracting architecture information."""

from pathlib import Path
from typing import Dict, List, Tuple

from .isa_database import AddressingModeRecord, ArchitectureRecord, RegisterRecord


class XEDMetadataParser:
    """Parser for XED datafiles to extract architecture metadata."""

    def __init__(self, xed_datafiles_dir: Path):
        self.xed_dir = xed_datafiles_dir
        self.registers_file = self.xed_dir / "xed-regs.txt"
        self.machine_modes_file = self.xed_dir / "xed-machine-modes-enum.txt"
        self.operand_width_file = self.xed_dir / "xed-operand-width.txt"
        self.pointer_width_file = self.xed_dir / "xed-pointer-width.txt"

    def parse_architectures(self) -> List[ArchitectureRecord]:
        """Parse architecture metadata for x86_32 and x86_64."""
        architectures = []

        # x86_32 Architecture
        x86_32 = ArchitectureRecord(
            isa_name="x86_32",
            word_size=32,
            endianness="little",
            description="Intel x86 32-bit instruction set architecture",
            machine_mode="LEGACY_32",
        )
        architectures.append(x86_32)

        # x86_64 Architecture
        x86_64 = ArchitectureRecord(
            isa_name="x86_64",
            word_size=64,
            endianness="little",
            description="Intel x86 64-bit instruction set architecture",
            machine_mode="LONG_64",
        )
        architectures.append(x86_64)

        return architectures

    def parse_registers(self) -> Tuple[List[RegisterRecord], List[RegisterRecord]]:
        """Parse registers from xed-regs.txt and categorize by architecture."""
        if not self.registers_file.exists():
            raise FileNotFoundError(f"Register file not found: {self.registers_file}")

        x86_32_registers = []
        x86_64_registers = []

        with open(self.registers_file, "r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse register definition
            # Format: name class width max-enclosing-reg-64b/32b-mode regid [h]
            parts = line.split()
            if len(parts) < 4:
                continue

            reg_name = parts[0]
            reg_class = parts[1]
            width_str = parts[2]
            encoding_id = (
                int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
            )

            # Skip invalid registers
            if reg_class == "INVALID":
                continue

            # Parse width
            try:
                if "/" in width_str:
                    width = int(width_str.split("/")[0])
                else:
                    width = int(width_str)
            except ValueError:
                continue

            # Determine architecture availability
            is_64bit_reg = self._is_64bit_register(reg_name, reg_class, width)
            is_32bit_reg = self._is_32bit_register(reg_name, reg_class, width)
            is_main_reg = self._is_main_register(reg_name, reg_class, width)

            # Add to x86_32 if applicable
            if is_32bit_reg:
                x86_32_registers.append(
                    RegisterRecord(
                        architecture_id=1,  # Will be set properly when inserting
                        register_name=reg_name,
                        register_class=reg_class,
                        width_bits=width,
                        encoding_id=encoding_id,
                        is_main_register=is_main_reg,
                    )
                )

            # Add to x86_64 if applicable
            if is_64bit_reg:
                x86_64_registers.append(
                    RegisterRecord(
                        architecture_id=2,  # Will be set properly when inserting
                        register_name=reg_name,
                        register_class=reg_class,
                        width_bits=width,
                        encoding_id=encoding_id,
                        is_main_register=is_main_reg,
                    )
                )

        return x86_32_registers, x86_64_registers

    def _is_64bit_register(self, reg_name: str, reg_class: str, width: int) -> bool:
        """Determine if register is available in 64-bit mode."""
        # All 64-bit registers
        if width == 64 and reg_class == "gpr":
            return True

        # 64-bit flags register
        if reg_name == "RFLAGS":
            return True

        # All segment, control, debug, MMX, x87, XMM, YMM, ZMM registers
        if reg_class in ["sr", "cr", "dr", "mmx", "x87", "xmm", "ymm", "zmm"]:
            return True

        # 32-bit versions of 64-bit registers (EAX, EBX, etc.)
        if reg_class == "gpr" and width == 32:
            if reg_name.startswith(("E", "R")) and reg_name[1:] in [
                "AX",
                "BX",
                "CX",
                "DX",
                "SP",
                "BP",
                "SI",
                "DI",
            ]:
                return True
            # R8D, R9D, etc.
            if reg_name.startswith("R") and reg_name[1:].replace("D", "").isdigit():
                return True

        # 16-bit versions
        if reg_class == "gpr" and width == 16:
            if reg_name in ["AX", "BX", "CX", "DX", "SP", "BP", "SI", "DI"]:
                return True
            # R8W, R9W, etc.
            if reg_name.startswith("R") and reg_name[1:].replace("W", "").isdigit():
                return True

        # 8-bit versions
        if reg_class == "gpr" and width == 8:
            if reg_name in [
                "AL",
                "BL",
                "CL",
                "DL",
                "AH",
                "BH",
                "CH",
                "DH",
                "SPL",
                "BPL",
                "SIL",
                "DIL",
            ]:
                return True
            # R8B, R9B, etc.
            if reg_name.startswith("R") and reg_name[1:].replace("B", "").isdigit():
                return True

        return False

    def _is_32bit_register(self, reg_name: str, reg_class: str, width: int) -> bool:
        """Determine if register is available in 32-bit mode."""
        # No 64-bit registers in 32-bit mode
        if width == 64:
            return False

        # No R8-R15 registers in 32-bit mode
        if reg_name.startswith("R") and len(reg_name) > 2:
            reg_num = reg_name[1:].replace("D", "").replace("W", "").replace("B", "")
            if reg_num.isdigit() and int(reg_num) >= 8:
                return False

        # 32-bit flags register
        if reg_name == "EFLAGS":
            return True

        # All segment, control, debug, MMX, x87, XMM registers
        if reg_class in ["sr", "cr", "dr", "mmx", "x87", "xmm"]:
            return True

        # 32-bit general purpose registers
        if reg_class == "gpr" and width == 32:
            if reg_name.startswith("E") and reg_name[1:] in [
                "AX",
                "BX",
                "CX",
                "DX",
                "SP",
                "BP",
                "SI",
                "DI",
            ]:
                return True

        # 16-bit versions
        if reg_class == "gpr" and width == 16:
            if reg_name in ["AX", "BX", "CX", "DX", "SP", "BP", "SI", "DI"]:
                return True

        # 8-bit versions (but not REX-only ones)
        if reg_class == "gpr" and width == 8:
            if reg_name in ["AL", "BL", "CL", "DL", "AH", "BH", "CH", "DH"]:
                return True

        return False

    def _is_main_register(self, reg_name: str, reg_class: str, width: int) -> bool:
        """Determine if this is a main register (not a sub-register)."""
        # For GPRs, be more selective about what we consider "main"
        if reg_class == "gpr":
            # 64-bit registers are main in 64-bit mode, but only the basic ones
            if width == 64:
                # Only RAX, RBX, RCX, RDX, RSP, RBP, RSI, RDI, R8-R15
                if reg_name in ["RAX", "RBX", "RCX", "RDX", "RSP", "RBP", "RSI", "RDI"]:
                    return True
                if reg_name.startswith("R") and len(reg_name) <= 3:
                    reg_num = reg_name[1:]
                    if reg_num.isdigit() and 8 <= int(reg_num) <= 15:
                        return True
                return False

            # 32-bit registers are main in 32-bit mode for basic registers only
            if width == 32:
                if reg_name in ["EAX", "EBX", "ECX", "EDX", "ESP", "EBP", "ESI", "EDI"]:
                    return True
                return False

        # For flags registers, only the main ones
        if reg_class == "flags":
            if reg_name in ["EFLAGS", "RFLAGS"]:
                return True

        # For segment registers, all are considered main
        if reg_class == "sr":
            return True

        # For control and debug registers, only a few main ones
        if reg_class in ["cr", "dr"]:
            control_debug_regs = [
                "CR0",
                "CR2",
                "CR3",
                "CR4",
                "DR0",
                "DR1",
                "DR2",
                "DR3",
                "DR6",
                "DR7",
            ]
            if reg_name in control_debug_regs:
                return True

        # For SIMD registers, consider the main ones
        if reg_class == "xmm":
            if reg_name.startswith("XMM") and len(reg_name) <= 5:  # XMM0-XMM15
                return True

        return False

    def parse_addressing_modes(
        self,
    ) -> Tuple[List[AddressingModeRecord], List[AddressingModeRecord]]:
        """Parse addressing modes for x86_32 and x86_64."""
        # x86_32 addressing modes
        x86_32_modes = [
            AddressingModeRecord(
                architecture_id=1,
                mode_name="register_direct",
                description="Direct register addressing",
                example_syntax="MOV EAX, EBX",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="immediate",
                description="Immediate addressing",
                example_syntax="MOV EAX, 42",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="memory_direct",
                description="Direct memory addressing",
                example_syntax="MOV EAX, [0x12345678]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="register_indirect",
                description="Register indirect addressing",
                example_syntax="MOV EAX, [EBX]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="base_displacement",
                description="Base plus displacement addressing",
                example_syntax="MOV EAX, [EBX+8]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="index_scale",
                description="Index with scale addressing",
                example_syntax="MOV EAX, [ESI*2]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="base_index",
                description="Base plus index addressing",
                example_syntax="MOV EAX, [EBX+ESI]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="base_index_displacement",
                description="Base plus index plus displacement addressing",
                example_syntax="MOV EAX, [EBX+ESI+8]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="base_index_scale_displacement",
                description="Base plus scaled index plus displacement addressing",
                example_syntax="MOV EAX, [EBX+ESI*2+8]",
            ),
        ]

        # x86_64 addressing modes (includes all x86_32 modes plus RIP-relative)
        x86_64_modes = [
            AddressingModeRecord(
                architecture_id=2,
                mode_name="register_direct",
                description="Direct register addressing",
                example_syntax="MOV RAX, RBX",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="immediate",
                description="Immediate addressing",
                example_syntax="MOV RAX, 42",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="memory_direct",
                description="Direct memory addressing",
                example_syntax="MOV RAX, [0x12345678]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="register_indirect",
                description="Register indirect addressing",
                example_syntax="MOV RAX, [RBX]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="base_displacement",
                description="Base plus displacement addressing",
                example_syntax="MOV RAX, [RBX+8]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="index_scale",
                description="Index with scale addressing",
                example_syntax="MOV RAX, [RSI*2]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="base_index",
                description="Base plus index addressing",
                example_syntax="MOV RAX, [RBX+RSI]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="base_index_displacement",
                description="Base plus index plus displacement addressing",
                example_syntax="MOV RAX, [RBX+RSI+8]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="base_index_scale_displacement",
                description="Base plus scaled index plus displacement addressing",
                example_syntax="MOV RAX, [RBX+RSI*2+8]",
            ),
            AddressingModeRecord(
                architecture_id=2,
                mode_name="rip_relative",
                description="RIP-relative addressing (64-bit only)",
                example_syntax="MOV RAX, [RIP+0x12345678]",
            ),
        ]

        return x86_32_modes, x86_64_modes

    def get_machine_modes(self) -> Dict[str, str]:
        """Parse machine modes from xed-machine-modes-enum.txt."""
        if not self.machine_modes_file.exists():
            return {"x86_32": "LEGACY_32", "x86_64": "LONG_64"}

        modes = {}
        with open(self.machine_modes_file, "r") as f:
            content = f.read()

        # Look for LONG_64 and LEGACY_32 definitions
        if "LONG_64" in content:
            modes["x86_64"] = "LONG_64"
        if "LEGACY_32" in content:
            modes["x86_32"] = "LEGACY_32"

        return modes
