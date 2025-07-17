"""ARM importer for AArch64 instruction data (future implementation)."""

from pathlib import Path
from typing import Iterator, Optional

from .base import ISAImporter
from ..isa_database import InstructionRecord


class ARMImporter(ISAImporter):
    """Importer for ARM AArch64 instruction data."""
    
    def __init__(self, db):
        super().__init__(db)
        self._version = "1.0.0"
    
    @property
    def isa_name(self) -> str:
        return "aarch64"
    
    @property
    def importer_version(self) -> str:
        return self._version
    
    def get_source_version(self, source_dir: Path) -> Optional[str]:
        """Get ARM documentation version from source directory."""
        # TODO: Implement version detection for ARM documentation
        return None
    
    async def parse_sources(self, source_dir: Path) -> Iterator[InstructionRecord]:
        """Parse ARM source files and yield instruction records."""
        # TODO: Implement ARM instruction parser
        # This will need to handle ARM's XML-based instruction documentation
        # or other formats provided by ARM
        
        self.log_error("ARM importer not yet implemented")
        return
        yield  # Make this a generator function