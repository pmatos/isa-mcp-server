"""Base importer framework for ISA instruction data."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Dict, Any, Optional
from datetime import datetime
import time

from ..isa_database import ISADatabase, InstructionRecord


class ISAImporter(ABC):
    """Base class for ISA importers."""
    
    def __init__(self, db: ISADatabase):
        self.db = db
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stats = {
            'instructions_processed': 0,
            'instructions_inserted': 0,
            'errors': 0,
            'warnings': 0
        }
    
    @property
    @abstractmethod
    def isa_name(self) -> str:
        """Return the ISA name this importer handles."""
        pass
    
    @property
    @abstractmethod
    def importer_version(self) -> str:
        """Return the version of this importer."""
        pass
    
    @abstractmethod
    async def parse_sources(self, source_dir: Path) -> Iterator[InstructionRecord]:
        """Parse source files and yield instruction records."""
        pass
    
    @abstractmethod
    def get_source_version(self, source_dir: Path) -> Optional[str]:
        """Get version information from source files."""
        pass
    
    async def import_from_source(self, source_dir: Path) -> Dict[str, Any]:
        """Import instructions from source directory."""
        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")
        
        self.logger.info(f"Starting import for {self.isa_name} from {source_dir}")
        start_time = time.time()
        
        # Reset stats
        self.stats = {
            'instructions_processed': 0,
            'instructions_inserted': 0,
            'errors': 0,
            'warnings': 0
        }
        
        try:
            source_version = self.get_source_version(source_dir)
            
            # Parse and insert instructions
            async for instruction in self.parse_sources(source_dir):
                try:
                    self.stats['instructions_processed'] += 1
                    
                    # Validate instruction
                    if not self._validate_instruction(instruction):
                        self.stats['errors'] += 1
                        continue
                    
                    # Insert into database
                    self.db.insert_instruction(instruction)
                    self.stats['instructions_inserted'] += 1
                    
                    # Progress logging
                    if self.stats['instructions_processed'] % 100 == 0:
                        self.logger.info(
                            f"Processed {self.stats['instructions_processed']} instructions "
                            f"({self.stats['instructions_inserted']} inserted, "
                            f"{self.stats['errors']} errors)"
                        )
                
                except Exception as e:
                    self.logger.error(f"Error processing instruction: {e}")
                    self.stats['errors'] += 1
                    continue
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record import metadata
            self.db.record_import_metadata(
                isa=self.isa_name,
                source_path=str(source_dir),
                instruction_count=self.stats['instructions_inserted'],
                source_version=source_version,
                importer_version=self.importer_version,
                duration_seconds=duration,
                success=True
            )
            
            self.logger.info(
                f"Import completed: {self.stats['instructions_inserted']} instructions "
                f"inserted in {duration:.2f} seconds"
            )
            
            return {
                'success': True,
                'duration_seconds': duration,
                'stats': self.stats.copy(),
                'source_version': source_version
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            self.logger.error(f"Import failed: {error_msg}")
            
            # Record failed import
            self.db.record_import_metadata(
                isa=self.isa_name,
                source_path=str(source_dir),
                instruction_count=self.stats['instructions_inserted'],
                source_version=None,
                importer_version=self.importer_version,
                duration_seconds=duration,
                success=False,
                error_message=error_msg
            )
            
            return {
                'success': False,
                'duration_seconds': duration,
                'stats': self.stats.copy(),
                'error': error_msg
            }
    
    def _validate_instruction(self, instruction: InstructionRecord) -> bool:
        """Validate instruction record."""
        if not instruction.isa:
            self.logger.warning("Instruction missing ISA")
            return False
        
        if not instruction.mnemonic:
            self.logger.warning("Instruction missing mnemonic")
            return False
        
        if not instruction.category:
            self.logger.warning(f"Instruction {instruction.mnemonic} missing category")
            return False
        
        if not instruction.extension:
            self.logger.warning(f"Instruction {instruction.mnemonic} missing extension")
            return False
        
        return True
    
    def log_warning(self, message: str):
        """Log warning and increment warning counter."""
        self.logger.warning(message)
        self.stats['warnings'] += 1
    
    def log_error(self, message: str):
        """Log error and increment error counter."""
        self.logger.error(message)
        self.stats['errors'] += 1


class ISAImporterRegistry:
    """Registry for ISA importers."""
    
    def __init__(self):
        self._importers: Dict[str, type] = {}
    
    def register(self, importer_class: type):
        """Register an importer class."""
        # Create temporary instance to get ISA name
        temp_instance = importer_class(db=None)
        isa_name = temp_instance.isa_name
        self._importers[isa_name] = importer_class
        
    def get_importer(self, isa_name: str, db: ISADatabase) -> Optional[ISAImporter]:
        """Get importer instance for ISA."""
        importer_class = self._importers.get(isa_name)
        if importer_class:
            return importer_class(db)
        return None
    
    def list_supported_isas(self) -> list[str]:
        """List supported ISAs."""
        return list(self._importers.keys())


# Global registry instance
importer_registry = ISAImporterRegistry()