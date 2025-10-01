"""ARM metadata parser for extracting architecture information."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .isa_database import AddressingModeRecord, ArchitectureRecord, RegisterRecord


class ARMMetadataParser:
    """Parser for ARM machine-readable JSON files to extract architecture metadata."""

    def __init__(self, arm_data_dir: Path):
        self.arm_dir = arm_data_dir
        self.instructions_file = self.arm_dir / "Instructions.json"
        self.registers_file = self.arm_dir / "Registers.json"
        self.features_file = self.arm_dir / "Features.json"

    def get_version_info(self) -> Optional[str]:
        """Get ARM architecture version from metadata."""
        try:
            if self.instructions_file.exists():
                with open(self.instructions_file, "r") as f:
                    # Only read the first part of the file to get metadata
                    data = json.load(f)
                    meta = data.get("_meta", {})
                    version = meta.get("version", {})
                    arch_version = version.get("architecture", "")
                    build = version.get("build", "")
                    ref = version.get("ref", "")
                    return f"{arch_version}-{ref}-{build}" if arch_version else None
        except Exception:
            pass
        return None

    def parse_architectures(self) -> List[ArchitectureRecord]:
        """Parse architecture metadata for AArch64."""
        architectures = []

        # AArch64 Architecture
        aarch64 = ArchitectureRecord(
            isa_name="aarch64",
            word_size=64,
            endianness="little",
            description="ARM AArch64 (A64) instruction set architecture",
            machine_mode="AARCH64",
        )
        architectures.append(aarch64)

        return architectures

    def parse_registers(self) -> List[RegisterRecord]:
        """Parse registers from Registers.json for AArch64."""
        aarch64_registers = []

        if not self.registers_file.exists():
            # Fallback to predefined register list
            return self._get_default_aarch64_registers()

        try:
            with open(self.registers_file, "r") as f:
                json.load(f)

            # The registers file contains system registers, but we need GPRs
            # for now, use predefined list and extract system registers if needed
            aarch64_registers = self._get_default_aarch64_registers()

            # TODO: Extract system registers from JSON data
            # This would require parsing the complex register structure

        except Exception:
            # Fall back to predefined registers
            aarch64_registers = self._get_default_aarch64_registers()

        return aarch64_registers

    def _get_default_aarch64_registers(self) -> List[RegisterRecord]:
        """Get default AArch64 register definitions."""
        registers = []
        register_id = 1

        # General Purpose Registers X0-X30
        for i in range(31):
            registers.append(
                RegisterRecord(
                    architecture_id=1,  # Will be set properly when inserting
                    register_name=f"X{i}",
                    register_class="gpr",
                    width_bits=64,
                    encoding_id=i,
                    is_main_register=True,
                )
            )
            register_id += 1

        # 32-bit variants W0-W30
        for i in range(31):
            registers.append(
                RegisterRecord(
                    architecture_id=1,
                    register_name=f"W{i}",
                    register_class="gpr",
                    width_bits=32,
                    encoding_id=i,
                    is_main_register=False,
                )
            )
            register_id += 1

        # Stack Pointer
        registers.append(
            RegisterRecord(
                architecture_id=1,
                register_name="SP",
                register_class="gpr",
                width_bits=64,
                encoding_id=31,
                is_main_register=True,
            )
        )

        # Zero Register
        registers.append(
            RegisterRecord(
                architecture_id=1,
                register_name="XZR",
                register_class="gpr",
                width_bits=64,
                encoding_id=31,
                is_main_register=True,
            )
        )

        registers.append(
            RegisterRecord(
                architecture_id=1,
                register_name="WZR",
                register_class="gpr",
                width_bits=32,
                encoding_id=31,
                is_main_register=False,
            )
        )

        # Vector Registers V0-V31
        for i in range(32):
            registers.append(
                RegisterRecord(
                    architecture_id=1,
                    register_name=f"V{i}",
                    register_class="simd",
                    width_bits=128,
                    encoding_id=i,
                    is_main_register=True,
                )
            )

        # Scalar floating-point variants
        for i in range(32):
            # 64-bit double precision
            registers.append(
                RegisterRecord(
                    architecture_id=1,
                    register_name=f"D{i}",
                    register_class="simd",
                    width_bits=64,
                    encoding_id=i,
                    is_main_register=False,
                )
            )
            # 32-bit single precision
            registers.append(
                RegisterRecord(
                    architecture_id=1,
                    register_name=f"S{i}",
                    register_class="simd",
                    width_bits=32,
                    encoding_id=i,
                    is_main_register=False,
                )
            )
            # 16-bit half precision
            registers.append(
                RegisterRecord(
                    architecture_id=1,
                    register_name=f"H{i}",
                    register_class="simd",
                    width_bits=16,
                    encoding_id=i,
                    is_main_register=False,
                )
            )
            # 8-bit byte
            registers.append(
                RegisterRecord(
                    architecture_id=1,
                    register_name=f"B{i}",
                    register_class="simd",
                    width_bits=8,
                    encoding_id=i,
                    is_main_register=False,
                )
            )

        # Program Counter
        registers.append(
            RegisterRecord(
                architecture_id=1,
                register_name="PC",
                register_class="control",
                width_bits=64,
                encoding_id=None,
                is_main_register=True,
            )
        )

        # Processor State Register
        registers.append(
            RegisterRecord(
                architecture_id=1,
                register_name="PSTATE",
                register_class="flags",
                width_bits=32,
                encoding_id=None,
                is_main_register=True,
            )
        )

        return registers

    def parse_addressing_modes(self) -> List[AddressingModeRecord]:
        """Parse addressing modes for AArch64."""
        # AArch64 addressing modes
        aarch64_modes = [
            AddressingModeRecord(
                architecture_id=1,
                mode_name="register_direct",
                description="Direct register addressing",
                example_syntax="MOV X0, X1",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="immediate",
                description="Immediate addressing",
                example_syntax="MOV X0, #42",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="base_register",
                description="Base register addressing",
                example_syntax="LDR X0, [X1]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="base_offset",
                description="Base plus offset addressing",
                example_syntax="LDR X0, [X1, #8]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="pre_indexed",
                description="Pre-indexed addressing",
                example_syntax="LDR X0, [X1, #8]!",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="post_indexed",
                description="Post-indexed addressing",
                example_syntax="LDR X0, [X1], #8",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="register_offset",
                description="Base plus register offset",
                example_syntax="LDR X0, [X1, X2]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="scaled_register_offset",
                description="Base plus scaled register offset",
                example_syntax="LDR X0, [X1, X2, LSL #3]",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="pc_relative",
                description="PC-relative addressing",
                example_syntax="ADR X0, label",
            ),
            AddressingModeRecord(
                architecture_id=1,
                mode_name="literal",
                description="Literal pool addressing",
                example_syntax="LDR X0, =value",
            ),
        ]

        return aarch64_modes

    def get_cpu_features(self) -> Dict[str, List[str]]:
        """Parse CPU features from Features.json."""
        features = {}

        if not self.features_file.exists():
            return {"aarch64": ["BASE"]}

        try:
            with open(self.features_file, "r") as f:
                data = json.load(f)

            # Extract feature names
            feature_list = []
            if "features" in data:
                for feature_name in data["features"].keys():
                    feature_list.append(feature_name.upper())

            features["aarch64"] = feature_list if feature_list else ["BASE"]

        except Exception:
            features["aarch64"] = ["BASE"]

        return features
