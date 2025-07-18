"""XED importer for Intel x86 instruction data."""

import re
from pathlib import Path
from typing import Iterator, List, Optional

from ..isa_database import EncodingRecord, InstructionRecord, OperandRecord
from .base import ISAImporter
from .xed_parser import XEDInstruction, XEDParser


class XEDImporter(ISAImporter):
    """Importer for XED instruction data."""

    def __init__(self, db):
        super().__init__(db)
        self.parser = XEDParser()
        self._version = "1.0.0"

    @property
    def isa_name(self) -> str:
        return "x86_32,x86_64"  # This importer handles both architectures

    @property
    def importer_version(self) -> str:
        return self._version

    def get_source_version(self, source_dir: Path) -> Optional[str]:
        """Get XED version from source directory."""
        version_file = source_dir.parent / "VERSION"
        if version_file.exists():
            try:
                with open(version_file, "r") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    async def parse_sources(self, source_dir: Path) -> Iterator[InstructionRecord]:
        """Parse XED source files and yield instruction records."""
        datafiles_dir = source_dir / "datafiles"
        if not datafiles_dir.exists():
            datafiles_dir = source_dir

        # Process main instruction file
        main_file = datafiles_dir / "xed-isa.txt"
        if main_file.exists():
            self.logger.info(f"Processing main instruction file: {main_file}")
            async for instruction in self._process_file(main_file):
                yield instruction

        # Process extension files
        extension_dirs = [
            "avx",
            "avx512f",
            "avx512cd",
            "avx512ifma",
            "avx512vbmi",
            "avx512-bf16",
            "avx512-fp16",
            "avx512-skx",
            "avx-vnni",
            "hsw",
            "hswavx",
            "hswbmi",
            "bdw",
            "skl",
            "knl",
            "knm",
            "cet",
            "sha",
            "gfni-vaes-vpcl",
            "clwb",
            "clflushopt",
            "movdir",
            "enqcmd",
            "serialize",
            "tsxldtrk",
            "amx-spr",
            "amx-bf16",
            "amx-int8",
            "amx-fp16",
            "amx-complex",
            "amx-tf32",
            "apx-f",
        ]

        for ext_dir in extension_dirs:
            ext_path = datafiles_dir / ext_dir
            if ext_path.exists():
                # Look for .xed.txt files in extension directory
                for isa_file in ext_path.glob("*.xed.txt"):
                    self.logger.info(f"Processing extension file: {isa_file}")
                    async for instruction in self._process_file(isa_file):
                        yield instruction

    async def _process_file(self, file_path: Path) -> Iterator[InstructionRecord]:
        """Process a single XED instruction file."""
        try:
            for xed_instruction in self.parser.parse_file(file_path):
                try:
                    instruction_records = self._convert_to_instruction_record(
                        xed_instruction
                    )
                    for record in instruction_records:
                        yield record
                except Exception as e:
                    self.log_error(
                        f"Error converting instruction {xed_instruction.iclass}: {e}"
                    )
        except Exception as e:
            self.log_error(f"Error processing file {file_path}: {e}")

    def _convert_to_instruction_record(
        self, xed_instr: XEDInstruction
    ) -> List[InstructionRecord]:
        """Convert XED instruction to InstructionRecord(s) for appropriate archs."""
        if not xed_instr.iclass:
            return []

        # Determine which architectures this instruction belongs to
        target_isas = self._determine_target_architectures(xed_instr)

        if not target_isas:
            return []

        # Parse operands
        operands = self._parse_operands(xed_instr.operands)

        # Parse encoding
        encoding = self._parse_encoding(xed_instr.pattern)

        # Parse flags
        flags_affected = self._parse_flags(xed_instr.flags) if xed_instr.flags else []

        # Generate description
        description = self._generate_description(xed_instr)

        # Generate syntax
        syntax = self._generate_syntax(xed_instr, operands)

        # Determine variant (for instructions with multiple forms)
        variant = self._determine_variant(xed_instr)

        # Create instruction record for each target architecture
        records = []
        for isa in target_isas:
            record = InstructionRecord(
                isa=isa,
                mnemonic=xed_instr.iclass,
                variant=variant,
                category=xed_instr.category,
                extension=xed_instr.extension,
                isa_set=xed_instr.isa_set,
                description=description,
                syntax=syntax,
                operands=operands,
                encoding=encoding,
                flags_affected=flags_affected,
                cpuid_features=self._get_cpuid_features(xed_instr),
                cpl=xed_instr.cpl,
                attributes=xed_instr.attributes,
                added_version=None,
                deprecated=False,
            )
            records.append(record)

        return records

    def _determine_target_architectures(self, xed_instr: XEDInstruction) -> List[str]:
        """Determine which architectures this instruction belongs to based on XED."""
        isas = []

        # Check pattern for mode indicators
        pattern = xed_instr.pattern.lower() if xed_instr.pattern else ""

        # Check for explicit mode restrictions
        if "mode64" in pattern:
            isas.append("x86_64")
        if "mode32" in pattern:
            isas.append("x86_32")
        if "not64" in pattern:
            # Instruction not available in 64-bit mode, only 32-bit
            return ["x86_32"]

        # Check attributes for mode restrictions
        attributes = []
        if xed_instr.attributes:
            attributes = [attr.upper() for attr in xed_instr.attributes]

        # LONGMODE extension indicates 64-bit specific instruction
        if xed_instr.extension == "LONGMODE" or "LONGMODE" in attributes:
            isas.append("x86_64")

        # Check for 64-bit specific ISA sets
        if xed_instr.isa_set in ["LONGMODE"]:
            isas.append("x86_64")

        # Check for REX prefix requirements (64-bit specific)
        if "rexw_prefix" in pattern or "rex_prefix" in pattern:
            if "x86_64" not in isas:
                isas.append("x86_64")

        # Check for 32-bit specific attributes
        if any(attr in attributes for attr in ["PROTECTED_MODE"]) and not isas:
            # Instructions that require protected mode but don't specify 64-bit
            # are typically available in both modes
            isas.extend(["x86_32", "x86_64"])

        # Handle special cases for specific instructions
        iclass = xed_instr.iclass.upper()
        if iclass in ["SYSCALL", "SYSRET"]:
            # These are primarily 64-bit instructions
            isas.append("x86_64")
        elif iclass in ["SYSENTER", "SYSEXIT"]:
            # These work in both modes but are more commonly used in 32-bit
            if not isas:
                isas.extend(["x86_32", "x86_64"])

        # Default: if no specific mode restrictions found, available in both
        if not isas:
            isas = ["x86_32", "x86_64"]

        # Remove duplicates and sort
        return sorted(list(set(isas)))

    def _parse_operands(self, operands_str: str) -> List[OperandRecord]:
        """Parse XED operands string into OperandRecord list."""
        if not operands_str:
            return []

        operands = []

        # Split operands by spaces
        parts = operands_str.split()

        for part in parts:
            if "=" in part and ":" in part:
                # Parse operand like "REG0=GPR8_B():w"
                name_part, rest = part.split("=", 1)
                if ":" in rest:
                    type_parts = rest.split(":")
                    operand_type = type_parts[0]
                    access = type_parts[1] if len(type_parts) > 1 else "r"
                    size = type_parts[2] if len(type_parts) > 2 else None

                    operands.append(
                        OperandRecord(
                            name=name_part,
                            type=self._normalize_operand_type(operand_type),
                            access=access,
                            size=size,
                            visibility="EXPLICIT",
                        )
                    )
            elif ":" in part:
                # Parse operand like "IMM0:r:b"
                parts_split = part.split(":")
                if len(parts_split) >= 2:
                    operands.append(
                        OperandRecord(
                            name=parts_split[0],
                            type=self._normalize_operand_type(
                                parts_split[2] if len(parts_split) > 2 else "unknown"
                            ),
                            access=parts_split[1],
                            size=None,
                            visibility="EXPLICIT",
                        )
                    )

        return operands

    def _normalize_operand_type(self, xed_type: str) -> str:
        """Normalize XED operand type to our format."""
        if not xed_type:
            return "unknown"

        # Remove function call syntax
        xed_type = re.sub(r"\(\)", "", xed_type)

        # Map common XED types to our format
        type_mapping = {
            "GPR8_B": "register",
            "GPR8_SB": "register",
            "GPR16_B": "register",
            "GPR32_B": "register",
            "GPR64_B": "register",
            "GPRv_B": "register",
            "GPRz_B": "register",
            "GPRy_B": "register",
            "XMM_B": "register",
            "XMM_R": "register",
            "YMM_B": "register",
            "YMM_R": "register",
            "ZMM_B": "register",
            "ZMM_R": "register",
            "MEM0": "memory",
            "MEM1": "memory",
            "AGEN": "memory",
            "IMM0": "immediate",
            "IMM1": "immediate",
            "UIMM8": "immediate",
            "SIMM8": "immediate",
            "UIMM16": "immediate",
            "SIMM16": "immediate",
            "UIMM32": "immediate",
            "SIMM32": "immediate",
            "SIMMz": "immediate",
            "b": "immediate",
            "d": "immediate",
            "w": "immediate",
            "z": "immediate",
            "mem8": "memory",
            "mem16": "memory",
            "mem32": "memory",
            "mem64": "memory",
            "mem128": "memory",
            "mem256": "memory",
            "mem512": "memory",
            "mem32real": "memory",
            "mem64real": "memory",
            "mem80real": "memory",
        }

        return type_mapping.get(xed_type, xed_type.lower())

    def _parse_encoding(self, pattern_str: str) -> Optional[EncodingRecord]:
        """Parse XED pattern into EncodingRecord."""
        if not pattern_str:
            return None

        # Extract opcode bytes
        hex_pattern = re.compile(r"0x[0-9A-Fa-f]{2}")
        hex_matches = hex_pattern.findall(pattern_str)
        opcode = " ".join(hex_matches) if hex_matches else None

        # Check for ModR/M byte
        modrm = "MODRM()" in pattern_str or "MOD[" in pattern_str

        # Check for SIB byte
        sib = "SIB()" in pattern_str

        # Check for immediate values
        immediate = any(
            imm in pattern_str
            for imm in [
                "UIMM8()",
                "SIMM8()",
                "UIMM16()",
                "SIMM16()",
                "UIMM32()",
                "SIMM32()",
                "SIMMz()",
            ]
        )

        # Check for displacement
        displacement = "DISP(" in pattern_str

        return EncodingRecord(
            pattern=pattern_str,
            opcode=opcode,
            modrm=modrm,
            sib=sib,
            displacement=displacement,
            immediate=immediate,
        )

    def _parse_flags(self, flags_str: str) -> List[str]:
        """Parse XED flags string into list of affected flags."""
        if not flags_str:
            return []

        flags = []

        # XED flags format: MUST [ fc0-u   fc1-mod fc2-u   fc3-u   ]
        # Map XED flag names to x86 flag names
        flag_mapping = {
            "fc0": "CF",
            "fc1": "PF",
            "fc2": "AF",
            "fc3": "ZF",
            "fc4": "SF",
            "fc5": "TF",
            "fc6": "IF",
            "fc7": "DF",
            "fc8": "OF",
            "fc9": "IOPL",
            "fc10": "NT",
            "fc11": "RF",
            "fc12": "VM",
            "fc13": "AC",
            "fc14": "VIF",
            "fc15": "VIP",
            "fc16": "ID",
            "of": "OF",
            "sf": "SF",
            "zf": "ZF",
            "af": "AF",
            "pf": "PF",
            "cf": "CF",
        }

        # Extract flag conditions
        flag_pattern = re.compile(r"([a-zA-Z]+\d*)-([a-zA-Z]+)")
        matches = flag_pattern.findall(flags_str)

        for flag_name, flag_action in matches:
            if flag_action in ["mod", "w", "set", "clr"]:
                mapped_flag = flag_mapping.get(flag_name.lower(), flag_name.upper())
                if mapped_flag not in flags:
                    flags.append(mapped_flag)

        return flags

    def _generate_description(self, xed_instr: XEDInstruction) -> str:
        """Generate human-readable description."""
        # Use disasm name if available, otherwise use iclass
        base_name = xed_instr.disasm or xed_instr.iclass

        # Basic descriptions for common instruction categories
        category_descriptions = {
            "DATAXFER": f"{base_name} - Data transfer operation",
            "BINARY": f"{base_name} - Binary arithmetic operation",
            "LOGICAL": f"{base_name} - Logical operation",
            "SHIFT": f"{base_name} - Shift operation",
            "ROTATE": f"{base_name} - Rotate operation",
            "BITBYTE": f"{base_name} - Bit manipulation operation",
            "FLAGOP": f"{base_name} - Flag operation",
            "COND_BR": f"{base_name} - Conditional branch",
            "UNCOND_BR": f"{base_name} - Unconditional branch",
            "CALL": f"{base_name} - Subroutine call",
            "RET": f"{base_name} - Return from subroutine",
            "PUSH": f"{base_name} - Push to stack",
            "POP": f"{base_name} - Pop from stack",
            "STRINGOP": f"{base_name} - String operation",
            "CONVERT": f"{base_name} - Data conversion",
            "COMIS": f"{base_name} - Compare and set flags",
            "FCMOV": f"{base_name} - Floating-point conditional move",
            "X87_ALU": f"{base_name} - x87 floating-point arithmetic",
            "MMX": f"{base_name} - MMX operation",
            "SSE": f"{base_name} - SSE operation",
            "AVX": f"{base_name} - AVX operation",
            "AVX2": f"{base_name} - AVX2 operation",
            "AVX512": f"{base_name} - AVX512 operation",
        }

        return category_descriptions.get(
            xed_instr.category, f"{base_name} - {xed_instr.category} operation"
        )

    def _generate_syntax(
        self, xed_instr: XEDInstruction, operands: List[OperandRecord]
    ) -> str:
        """Generate assembly syntax string."""
        mnemonic = xed_instr.disasm or xed_instr.iclass

        # Filter explicit operands
        explicit_operands = [op for op in operands if op.visibility == "EXPLICIT"]

        if not explicit_operands:
            return mnemonic

        # Generate operand strings
        operand_strings = []
        for op in explicit_operands:
            if op.type == "register":
                operand_strings.append("reg")
            elif op.type == "memory":
                operand_strings.append("mem")
            elif op.type == "immediate":
                operand_strings.append("imm")
            else:
                operand_strings.append(op.type)

        return f"{mnemonic} {', '.join(operand_strings)}"

    def _determine_variant(self, xed_instr: XEDInstruction) -> Optional[str]:
        """Determine instruction variant based on operands/encoding."""
        # Use UNAME if available
        if xed_instr.uname:
            return xed_instr.uname

        # Use IFORM if available
        if xed_instr.iform:
            return xed_instr.iform

        # Generate variant based on operands
        if xed_instr.operands:
            # Create a hash of operands to differentiate variants
            operand_hash = hash(xed_instr.operands)
            return f"var_{abs(operand_hash) % 10000:04d}"

        return None

    def _get_cpuid_features(self, xed_instr: XEDInstruction) -> List[str]:
        """Get CPUID features for instruction."""
        features = []

        # Map ISA_SET to CPUID features
        isa_set_mapping = {
            "I86": [],
            "I186": [],
            "I286": [],
            "I386": [],
            "I486": [],
            "PENTIUM": [],
            "PPRO": [],
            "MMX": ["MMX"],
            "SSE": ["SSE"],
            "SSE2": ["SSE2"],
            "SSE3": ["SSE3"],
            "SSSE3": ["SSSE3"],
            "SSE4": ["SSE4.1"],
            "SSE42": ["SSE4.2"],
            "AVX": ["AVX"],
            "AVX2": ["AVX2"],
            "AVX512F": ["AVX512F"],
            "AVX512CD": ["AVX512CD"],
            "AVX512ER": ["AVX512ER"],
            "AVX512PF": ["AVX512PF"],
            "AVX512DQ": ["AVX512DQ"],
            "AVX512BW": ["AVX512BW"],
            "AVX512VL": ["AVX512VL"],
            "AVX512IFMA": ["AVX512IFMA"],
            "AVX512VBMI": ["AVX512VBMI"],
            "AVX512VBMI2": ["AVX512VBMI2"],
            "AVX512VNNI": ["AVX512VNNI"],
            "AVX512BF16": ["AVX512_BF16"],
            "AVX512VP2INTERSECT": ["AVX512_VP2INTERSECT"],
            "AVX512FP16": ["AVX512_FP16"],
            "BMI1": ["BMI1"],
            "BMI2": ["BMI2"],
            "ADX": ["ADX"],
            "SHA": ["SHA"],
            "AES": ["AES"],
            "PCLMULQDQ": ["PCLMULQDQ"],
            "RDRAND": ["RDRAND"],
            "RDSEED": ["RDSEED"],
            "F16C": ["F16C"],
            "FMA": ["FMA"],
            "MOVBE": ["MOVBE"],
            "POPCNT": ["POPCNT"],
            "LZCNT": ["LZCNT"],
            "TBM": ["TBM"],
            "PREFETCHW": ["PREFETCHW"],
            "CLFLUSHOPT": ["CLFLUSHOPT"],
            "CLWB": ["CLWB"],
            "FSGSBASE": ["FSGSBASE"],
            "INVPCID": ["INVPCID"],
            "RTM": ["RTM"],
            "HLE": ["HLE"],
            "MPX": ["MPX"],
            "XSAVE": ["XSAVE"],
            "XSAVEOPT": ["XSAVEOPT"],
            "XSAVEC": ["XSAVEC"],
            "XSAVES": ["XSAVES"],
            "CET": ["CET_IBT", "CET_SS"],
            "ENQCMD": ["ENQCMD"],
            "SERIALIZE": ["SERIALIZE"],
            "TSXLDTRK": ["TSXLDTRK"],
            "AMX_BF16": ["AMX_BF16"],
            "AMX_INT8": ["AMX_INT8"],
            "AMX_TILE": ["AMX_TILE"],
        }

        if xed_instr.isa_set in isa_set_mapping:
            features.extend(isa_set_mapping[xed_instr.isa_set])

        return features
