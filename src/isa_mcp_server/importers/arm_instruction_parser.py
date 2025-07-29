"""ARM instruction parser for processing machine-readable instruction data."""

import json
import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from ..isa_database import EncodingRecord, InstructionRecord, OperandRecord


class ARMInstructionParser:
    """Parser for ARM machine-readable instruction data."""

    def __init__(self):
        self.instruction_cache = {}
        self.feature_mapping = self._build_feature_mapping()

    def _build_feature_mapping(self) -> Dict[str, str]:
        """Build mapping from ARM feature names to simplified categories."""
        return {
            "FEAT_FP": "FP",
            "FEAT_ASIMD": "NEON",
            "FEAT_AES": "AES",
            "FEAT_SHA1": "SHA1",
            "FEAT_SHA256": "SHA256",
            "FEAT_CRC32": "CRC32",
            "FEAT_LSE": "LSE",
            "FEAT_FP16": "FP16",
            "FEAT_DPB": "DPB",
            "FEAT_SVE": "SVE",
            "FEAT_SVE2": "SVE2",
            "FEAT_TME": "TME",
            "FEAT_BF16": "BF16",
            "FEAT_I8MM": "I8MM",
            "FEAT_MTE": "MTE",
            "FEAT_PAUTH": "PAUTH",
            "FEAT_FCMA": "FCMA",
            "FEAT_JSCVT": "JSCVT",
            "FEAT_LRCPC": "LRCPC",
            "FEAT_LRCPC2": "LRCPC2",
            "FEAT_FRINTTS": "FRINTTS",
            "FEAT_DGH": "DGH",
            "FEAT_RNG": "RNG",
            "FEAT_FLAGM": "FLAGM",
            "FEAT_FLAGM2": "FLAGM2",
            "FEAT_FHML": "FHML",
            "FEAT_ECV": "ECV",
            "FEAT_AFP": "AFP",
        }

    def parse_instructions_file(
        self, instructions_file: Path
    ) -> Iterator[InstructionRecord]:
        """Parse the Instructions.json file and yield instruction records."""
        if not instructions_file.exists():
            return

        try:
            with open(instructions_file, "r") as f:
                data = json.load(f)

            # Handle the new array-based structure
            instructions = data.get("instructions", [])
            for instruction_obj in instructions:
                try:
                    # Recursively process instruction hierarchies
                    for record in self._process_instruction_hierarchy(instruction_obj):
                        yield record
                except Exception:
                    # Log error but continue processing
                    continue

        except Exception:
            # Handle file reading errors
            return

    def _process_instruction_hierarchy(self, obj: Dict) -> Iterator[InstructionRecord]:
        """Recursively process instruction hierarchy to find actual instructions."""
        if not isinstance(obj, dict):
            return

        obj_type = obj.get("_type", "")

        if obj_type == "Instruction.Instruction":
            # This is an actual instruction - parse it
            name = obj.get("name", "UNKNOWN")
            try:
                records = self._parse_instruction(name, obj)
                for record in records:
                    yield record
            except Exception:
                # Continue processing other instructions
                pass

        elif obj_type in ["Instruction.InstructionSet", "Instruction.InstructionGroup"]:
            # This is a container - recurse into children
            children = obj.get("children", [])
            for child in children:
                for record in self._process_instruction_hierarchy(child):
                    yield record

    def _parse_instruction(
        self, name: str, instruction_data: Dict
    ) -> List[InstructionRecord]:
        """Parse a single instruction definition."""
        records = []

        # Handle different instruction types
        instruction_type = instruction_data.get("_type", "")

        if instruction_type == "Instruction.Instruction":
            records.extend(self._parse_base_instruction(name, instruction_data))
        elif instruction_type == "Instruction.InstructionGroup":
            records.extend(self._parse_instruction_group(name, instruction_data))
        elif instruction_type == "Instruction.InstructionAlias":
            records.extend(self._parse_instruction_alias(name, instruction_data))

        return records

    def _parse_base_instruction(
        self, name: str, instruction_data: Dict
    ) -> List[InstructionRecord]:
        """Parse a base instruction definition."""
        records = []

        # Extract basic information
        mnemonic = self._extract_mnemonic(name, instruction_data)
        if not mnemonic:
            return records

        description = self._extract_description(instruction_data)
        category = self._extract_category(instruction_data)

        # New structure: use the instruction data directly
        # No more "instances" - the instruction itself is the instance
        try:
            record = self._create_instruction_record(
                name, mnemonic, description, category, "default", instruction_data
            )
            if record:
                records.append(record)
        except Exception:
            pass

        return records

    def _parse_instruction_group(
        self, name: str, group_data: Dict
    ) -> List[InstructionRecord]:
        """Parse an instruction group (contains multiple related instructions)."""
        records = []

        instructions = group_data.get("instructions", {})
        for instruction_name, instruction_data in instructions.items():
            try:
                sub_records = self._parse_instruction(
                    instruction_name, instruction_data
                )
                records.extend(sub_records)
            except Exception:
                continue

        return records

    def _parse_instruction_alias(
        self, name: str, alias_data: Dict
    ) -> List[InstructionRecord]:
        """Parse an instruction alias."""
        # For aliases, create a simplified record
        mnemonic = self._extract_mnemonic(name, alias_data)
        if not mnemonic:
            return []

        description = self._extract_description(alias_data)
        if not description:
            description = f"{mnemonic} - Instruction alias"

        record = InstructionRecord(
            isa="aarch64",
            mnemonic=mnemonic,
            variant=name,
            category="ALIAS",
            extension="BASE",
            isa_set="A64",
            description=description,
            syntax=self._generate_basic_syntax(mnemonic),
            operands=[],
            encoding=None,
            flags_affected=[],
            cpuid_features=["BASE"],
            cpl=0,
            attributes=["ALIAS"],
            added_version=None,
            deprecated=False,
        )

        return [record]

    def _extract_mnemonic(self, name: str, instruction_data: Dict) -> Optional[str]:
        """Extract instruction mnemonic from name and data."""
        # Try to extract from assembly field first
        assembly = instruction_data.get("assembly", {})
        if (
            isinstance(assembly, dict)
            and assembly.get("_type") == "Instruction.Assembly"
        ):
            symbols = assembly.get("symbols", [])
            if symbols and isinstance(symbols[0], dict):
                first_symbol = symbols[0]
                if first_symbol.get("_type") == "Instruction.Symbols.Literal":
                    return first_symbol.get("value", "").upper()

        # Fallback: extract from instruction name
        mnemonic = re.sub(r"_[A-Za-z0-9]+$", "", name)  # Remove suffix like _A1
        mnemonic = re.sub(r"[^A-Za-z0-9]", "", mnemonic)  # Remove special characters
        return mnemonic.upper() if mnemonic else None

    def _extract_description(self, instruction_data: Dict) -> str:
        """Extract instruction description."""
        # Try to get title first (more descriptive)
        title = instruction_data.get("title", "")
        if title and isinstance(title, str):
            return title.strip()

        # Try description object
        description_obj = instruction_data.get("description", {})
        if isinstance(description_obj, dict):
            # Try to extract text from description object
            after_text = description_obj.get("after", "")
            before_text = description_obj.get("before", "")
            text = after_text or before_text
            if text:
                return text.strip()

        # Fallback to basic description
        return "ARM AArch64 instruction"

    def _extract_category(self, instruction_data: Dict) -> str:
        """Extract instruction category."""
        # ARM doesn't have direct categories like Intel, so we'll derive them
        operation = instruction_data.get("operation", {})
        if operation:
            # Try to categorize based on operation type or features
            return "GENERAL"

        return "UNKNOWN"

    def _create_instruction_record(
        self,
        name: str,
        mnemonic: str,
        description: str,
        category: str,
        instance_name: str,
        instance_data: Dict,
    ) -> Optional[InstructionRecord]:
        """Create an InstructionRecord from parsed data."""

        # Parse operands
        operands = self._parse_operands(instance_data)

        # Parse encoding
        encoding = self._parse_encoding(instance_data)

        # Extract features/extensions
        cpuid_features = self._extract_features(instance_data)
        extension = cpuid_features[0] if cpuid_features else "BASE"

        # Generate syntax
        syntax = self._generate_syntax(mnemonic, operands)

        # Create variant name
        variant = f"{name}_{instance_name}" if instance_name != "default" else name

        record = InstructionRecord(
            isa="aarch64",
            mnemonic=mnemonic,
            variant=variant,
            category=category,
            extension=extension,
            isa_set="A64",
            description=description,
            syntax=syntax,
            operands=operands,
            encoding=encoding,
            flags_affected=self._extract_flags_affected(instance_data),
            cpuid_features=cpuid_features,
            cpl=0,  # AArch64 doesn't have privilege levels like x86
            attributes=[],
            added_version=None,
            deprecated=False,
        )

        return record

    def _parse_operands(self, instance_data: Dict) -> List[OperandRecord]:
        """Parse operands from instance data."""
        operands = []

        # This is a simplified operand parsing - the ARM data structure is very complex
        # For now, create basic operand structure
        # encodeset = instance_data.get('encodeset', {})

        # Try to extract operand information from encoding
        # This would need much more sophisticated parsing in practice

        return operands

    def _parse_encoding(self, instance_data: Dict) -> Optional[EncodingRecord]:
        """Parse encoding information from instance data."""
        encoding = instance_data.get("encoding", {})

        if not encoding:
            return None

        # Extract basic encoding pattern
        pattern = str(encoding.get("pattern", ""))
        if not pattern:
            # Try to extract from name or other fields
            name = instance_data.get("name", "")
            pattern = name if name else "UNKNOWN"

        return EncodingRecord(
            pattern=pattern,
            opcode=None,  # Would need detailed parsing
            modrm=False,  # ARM doesn't use ModR/M
            sib=False,  # ARM doesn't use SIB
            displacement=False,
            immediate=False,
        )

    def _extract_features(self, instance_data: Dict) -> List[str]:
        """Extract CPU features required for instruction."""
        features = ["BASE"]

        # Look for feature requirements in the data
        # This would need more sophisticated parsing

        return features

    def _extract_flags_affected(self, instance_data: Dict) -> List[str]:
        """Extract flags affected by instruction."""
        # ARM has different flag structure than x86
        # Would need to parse condition code effects
        return []

    def _generate_syntax(self, mnemonic: str, operands: List[OperandRecord]) -> str:
        """Generate assembly syntax string."""
        if not operands:
            return mnemonic

        operand_strings = []
        for operand in operands:
            if operand.type == "register":
                operand_strings.append("reg")
            elif operand.type == "memory":
                operand_strings.append("mem")
            elif operand.type == "immediate":
                operand_strings.append("imm")
            else:
                operand_strings.append(operand.type)

        return f"{mnemonic} {', '.join(operand_strings)}"

    def _generate_basic_syntax(self, mnemonic: str) -> str:
        """Generate basic syntax for aliases."""
        return mnemonic
