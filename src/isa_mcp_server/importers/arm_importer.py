"""ARM importer for AArch64 instruction data."""

from pathlib import Path
from typing import AsyncGenerator, AsyncIterator, Iterator, Optional

from ..arm_metadata_parser import ARMMetadataParser
from ..isa_database import InstructionRecord
from .arm_instruction_parser import ARMInstructionParser
from .base import ISAImporter


class ARMImporter(ISAImporter):
    """Importer for ARM AArch64 instruction data."""

    def __init__(self, db):
        super().__init__(db)
        self.parser = ARMInstructionParser()
        self._version = "1.0.0"
        self._arch_metadata_populated = False

    @property
    def isa_name(self) -> str:
        return "aarch64"

    @property
    def importer_version(self) -> str:
        return self._version

    def get_source_version(self, source_dir: Path) -> Optional[str]:
        """Get ARM documentation version from source directory."""
        try:
            metadata_parser = ARMMetadataParser(source_dir)
            return metadata_parser.get_version_info()
        except Exception:
            return None

    async def parse_sources(self, source_dir: Path) -> AsyncGenerator[InstructionRecord, None]:
        """Parse ARM source files and yield instruction records."""
        instructions_file = source_dir / "Instructions.json"
        if not instructions_file.exists():
            self.log_error(f"ARM instructions file not found: {instructions_file}")
            return

        self.logger.info(f"Processing ARM instructions file: {instructions_file}")
        try:
            async for instruction in self._process_instructions_file(instructions_file):
                yield instruction
        except Exception as e:
            self.log_error(f"Error processing ARM instructions file: {e}")

    async def _process_instructions_file(
        self, file_path: Path
    ) -> AsyncGenerator[InstructionRecord, None]:
        """Process the ARM Instructions.json file."""
        try:
            for instruction_record in self.parser.parse_instructions_file(file_path):
                try:
                    yield instruction_record
                except Exception as e:
                    self.log_error(f"Error processing instruction: {e}")
        except Exception as e:
            self.log_error(f"Error parsing instructions file {file_path}: {e}")

    async def populate_architecture_metadata(self, source_dir: Path) -> bool:
        """Populate architecture metadata from ARM data files."""
        try:
            self.logger.info("Populating ARM architecture metadata...")

            # Create ARMMetadataParser instance
            parser = ARMMetadataParser(source_dir)

            # Parse architecture specifications
            architectures = parser.parse_architectures()

            # Parse registers
            aarch64_registers = parser.parse_registers()

            # Parse addressing modes
            aarch64_modes = parser.parse_addressing_modes()

            # Insert architectures
            arch_ids = {}
            for arch in architectures:
                arch_id = self.db.insert_architecture(arch)
                arch_ids[arch.isa_name] = arch_id
                self.logger.info(
                    f"Inserted architecture: {arch.isa_name} (ID: {arch_id})"
                )

            # Insert registers
            for reg in aarch64_registers:
                reg.architecture_id = arch_ids["aarch64"]
                self.db.insert_register(reg)

            self.logger.info(f"Inserted {len(aarch64_registers)} aarch64 registers")

            # Insert addressing modes
            for mode in aarch64_modes:
                mode.architecture_id = arch_ids["aarch64"]
                self.db.insert_addressing_mode(mode)

            self.logger.info(f"Inserted {len(aarch64_modes)} aarch64 addressing modes")

            self._arch_metadata_populated = True
            return True

        except Exception as e:
            self.logger.error(f"Error populating ARM architecture metadata: {e}")
            return False
