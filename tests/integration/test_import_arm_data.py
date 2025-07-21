"""Integration tests for ARM data import."""

import pytest
import tempfile
from pathlib import Path

from src.isa_mcp_server.isa_database import ISADatabase
from src.isa_mcp_server.importers.arm_importer import ARMImporter


class TestARMDataImport:
    """Integration tests for ARM data import process."""

    @pytest.mark.asyncio
    async def test_full_import_process(self, sample_arm_data_dir):
        """Test complete ARM import process end-to-end."""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Create importer
            importer = ARMImporter(db)
            
            # Import data
            result = await importer.import_from_source(sample_arm_data_dir)
            
            # Verify import success
            assert result['success'] == True
            assert result['stats']['instructions_inserted'] > 0
            assert result['stats']['errors'] == 0
            
            # Verify architecture data was imported
            assert 'metadata_imported' in result
            assert result['metadata_imported'] == True
            
            # Verify database contents
            # Check architecture was created
            architectures = db.get_all_architectures()
            aarch64_arch = next((a for a in architectures if a.isa_name == 'aarch64'), None)
            assert aarch64_arch is not None
            assert aarch64_arch.word_size == 64
            assert aarch64_arch.endianness == 'little'
            
            # Check registers were created
            registers = db.get_registers_for_architecture('aarch64')
            assert len(registers) > 0
            register_names = [r.register_name for r in registers]
            assert 'X0' in register_names  # General purpose register
            assert 'V0' in register_names  # Vector register
            assert 'SP' in register_names  # Stack pointer
            
            # Check addressing modes were created
            modes = db.get_addressing_modes_for_architecture('aarch64')
            assert len(modes) > 0
            mode_names = [m.mode_name for m in modes]
            assert 'register_direct' in mode_names
            assert 'immediate' in mode_names
            
            # Check instructions were created
            instructions = db.search_instructions('MOV', architecture='aarch64')
            assert len(instructions) > 0
            # Verify instruction has proper architecture association
            for instr in instructions[:5]:  # Check first 5
                full_instr = db.get_instruction(instr.mnemonic, 'aarch64')
                assert full_instr is not None
                assert full_instr.isa_name == 'aarch64'
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()

    @pytest.mark.asyncio
    async def test_import_with_skip_metadata(self, sample_arm_data_dir):
        """Test ARM import skipping architecture metadata."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Create importer
            importer = ARMImporter(db)
            
            # Import data skipping metadata
            result = await importer.import_from_source(sample_arm_data_dir, skip_metadata=True)
            
            # Verify import success
            assert result['success'] == True
            assert result['stats']['instructions_inserted'] > 0
            
            # Verify metadata was skipped
            assert not result.get('metadata_imported', False)
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()

    @pytest.mark.asyncio
    async def test_import_error_handling(self, tmp_path):
        """Test ARM import error handling."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Create importer
            importer = ARMImporter(db)
            
            # Try to import from empty directory
            result = await importer.import_from_source(tmp_path)
            
            # Should handle error gracefully
            assert result['success'] == True  # Empty import still succeeds
            assert result['stats']['instructions_inserted'] == 0
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()

    @pytest.mark.asyncio
    async def test_version_detection(self, sample_arm_data_dir):
        """Test ARM version detection during import."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Create importer
            importer = ARMImporter(db)
            
            # Import data
            result = await importer.import_from_source(sample_arm_data_dir)
            
            # Verify version was detected
            assert result['success'] == True
            assert 'source_version' in result
            assert result['source_version'] == "v9Ap6-A-2025-06_rel-83"
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()