"""RISC-V importer for instruction data (future implementation)."""

from pathlib import Path
from typing import Iterator, Optional

from .base import ISAImporter
from ..isa_database import InstructionRecord


class RISCVImporter(ISAImporter):
    """Importer for RISC-V instruction data."""
    
    def __init__(self, db):
        super().__init__(db)
        self._version = "1.0.0"
    
    @property
    def isa_name(self) -> str:
        return "riscv"
    
    @property
    def importer_version(self) -> str:
        return self._version
    
    def get_source_version(self, source_dir: Path) -> Optional[str]:
        """Get RISC-V specification version from source directory."""
        # TODO: Implement version detection for RISC-V specification
        return None
    
    async def parse_sources(self, source_dir: Path) -> Iterator[InstructionRecord]:
        """Parse RISC-V source files and yield instruction records."""
        # TODO: Implement RISC-V instruction parser
        # This will need to handle RISC-V specification formats
        # (possibly LaTeX, markdown, or other documentation formats)
        
        self.log_error("RISC-V importer not yet implemented")
        return
        yield  # Make this a generator function