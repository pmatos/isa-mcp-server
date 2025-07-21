"""Integration tests for cross-ISA import functionality."""

import pytest
import tempfile
from pathlib import Path

from src.isa_mcp_server.isa_database import ISADatabase
from src.isa_mcp_server.importers.arm_importer import ARMImporter
from src.isa_mcp_server.importers.xed_importer import XEDImporter


class TestCrossISAImports:
    """Integration tests for importing multiple ISAs together."""

    @pytest.mark.asyncio
    async def test_arm_and_intel_import(self, sample_arm_data_dir, sample_xed_data_dir):
        """Test importing both ARM and Intel data into same database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Import Intel data first
            intel_importer = XEDImporter(db)
            intel_result = await intel_importer.import_from_source(sample_xed_data_dir)
            
            assert intel_result['success'] == True
            intel_count = intel_result['stats']['instructions_inserted']
            
            # Import ARM data
            arm_importer = ARMImporter(db)
            arm_result = await arm_importer.import_from_source(sample_arm_data_dir)
            
            assert arm_result['success'] == True
            arm_count = arm_result['stats']['instructions_inserted']
            
            # Verify both imports worked
            assert intel_count > 0
            assert arm_count > 0
            
            # Verify both architectures exist
            architectures = db.get_all_architectures()
            arch_names = [a.isa_name for a in architectures]
            assert 'x86_32' in arch_names
            assert 'x86_64' in arch_names
            assert 'aarch64' in arch_names
            
            # Verify instruction counts match import results
            intel_instructions = db.search_instructions('', architecture='x86_64')
            arm_instructions = db.search_instructions('', architecture='aarch64')
            # Count should be > 0 but we can't match exact import count due to search limits
            assert len(intel_instructions) > 0
            assert len(arm_instructions) > 0
            
            # Verify no cross-contamination - check a few specific instructions
            # MOV exists in both but should be separate
            intel_mov = db.get_instruction('MOV', 'x86_64')
            arm_mov = db.get_instruction('MOV', 'aarch64')
            assert intel_mov is not None
            assert arm_mov is not None
            assert intel_mov.isa_name == 'x86_64'
            assert arm_mov.isa_name == 'aarch64'
            
            # Verify architecture metadata is separate
            intel_regs = db.get_registers_for_architecture('x86_64')
            arm_regs = db.get_registers_for_architecture('aarch64')
            intel_reg_names = [r.register_name for r in intel_regs]
            arm_reg_names = [r.register_name for r in arm_regs]
            # Check for architecture-specific registers
            assert 'RAX' in intel_reg_names  # x86_64 specific
            assert 'X0' in arm_reg_names     # ARM specific
            assert 'RAX' not in arm_reg_names
            assert 'X0' not in intel_reg_names
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()

    @pytest.mark.asyncio
    async def test_import_order_independence(self, sample_arm_data_dir, sample_xed_data_dir):
        """Test that import order doesn't affect results."""
        # First database: ARM then Intel
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db1_path = f.name
        
        # Second database: Intel then ARM  
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db2_path = f.name
        
        try:
            # Database 1: ARM first
            db1 = ISADatabase(db1_path)
            db1.initialize_database()
            
            arm_importer1 = ARMImporter(db1)
            arm_result1 = await arm_importer1.import_from_source(sample_arm_data_dir)
            
            intel_importer1 = XEDImporter(db1)
            intel_result1 = await intel_importer1.import_from_source(sample_xed_data_dir)
            
            # Database 2: Intel first
            db2 = ISADatabase(db2_path)
            db2.initialize_database()
            
            intel_importer2 = XEDImporter(db2)
            intel_result2 = await intel_importer2.import_from_source(sample_xed_data_dir)
            
            arm_importer2 = ARMImporter(db2)
            arm_result2 = await arm_importer2.import_from_source(sample_arm_data_dir)
            
            # Verify results are the same regardless of order
            assert arm_result1['success'] == arm_result2['success']
            assert intel_result1['success'] == intel_result2['success']
            assert arm_result1['stats']['instructions_inserted'] == arm_result2['stats']['instructions_inserted']
            assert intel_result1['stats']['instructions_inserted'] == intel_result2['stats']['instructions_inserted']
            
        finally:
            # Cleanup
            for db_path in [db1_path, db2_path]:
                db_file = Path(db_path)
                if db_file.exists():
                    db_file.unlink()

    @pytest.mark.asyncio
    async def test_architecture_separation(self, sample_arm_data_dir, sample_xed_data_dir):
        """Test that different architectures remain properly separated."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Import both architectures
            arm_importer = ARMImporter(db)
            await arm_importer.import_from_source(sample_arm_data_dir)
            
            intel_importer = XEDImporter(db)  
            await intel_importer.import_from_source(sample_xed_data_dir)
            
            # Verify ARM instructions have correct ISA
            arm_instructions = db.search_instructions('ADD', architecture='aarch64')
            assert len(arm_instructions) > 0
            for instr in arm_instructions[:10]:  # Check first 10
                full_instr = db.get_instruction(instr.mnemonic, 'aarch64')
                assert full_instr.isa_name == 'aarch64'
            
            # Verify Intel instructions have correct ISA
            intel64_instructions = db.search_instructions('ADD', architecture='x86_64')
            assert len(intel64_instructions) > 0
            for instr in intel64_instructions[:10]:  # Check first 10
                full_instr = db.get_instruction(instr.mnemonic, 'x86_64')
                assert full_instr.isa_name == 'x86_64'
            
            # Verify no mixing - try to get ARM instruction with Intel ISA
            arm_as_intel = db.get_instruction('LDR', 'x86_64')  # LDR is ARM-specific
            assert arm_as_intel is None
            
            intel_as_arm = db.get_instruction('MOVSX', 'aarch64')  # MOVSX is x86-specific
            assert intel_as_arm is None
            
            # Verify separate architecture metadata
            architectures = db.get_all_architectures()
            arch_dict = {a.isa_name: a for a in architectures}
            
            # Check each architecture has proper metadata
            assert 'aarch64' in arch_dict
            assert arch_dict['aarch64'].word_size == 64
            assert arch_dict['aarch64'].endianness == 'little'
            
            assert 'x86_64' in arch_dict
            assert arch_dict['x86_64'].word_size == 64
            assert arch_dict['x86_64'].endianness == 'little'
            
            # Verify registers belong to correct architectures
            arm_regs = db.get_registers_for_architecture('aarch64')
            for reg in arm_regs[:5]:  # Check first 5
                # Registers should be ARM-specific
                assert reg.register_name.startswith(('X', 'W', 'V', 'S', 'D', 'H', 'B')) or \
                       reg.register_name in ['SP', 'PC', 'XZR', 'WZR', 'PSTATE']
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()

    @pytest.mark.asyncio  
    async def test_metadata_isolation(self, sample_arm_data_dir, sample_xed_data_dir):
        """Test that architecture metadata remains isolated between ISAs."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Initialize database
            db = ISADatabase(db_path)
            db.initialize_database()
            
            # Import both with metadata
            arm_importer = ARMImporter(db)
            arm_result = await arm_importer.import_from_source(sample_arm_data_dir)
            
            intel_importer = XEDImporter(db)
            intel_result = await intel_importer.import_from_source(sample_xed_data_dir)
            
            # Both should have imported metadata
            assert arm_result.get('metadata_imported', False) == True
            assert intel_result.get('metadata_imported', False) == True
            
            # Verify ARM registers don't mix with Intel registers
            arm_registers = db.get_architecture_registers('aarch64')
            intel_registers = db.get_architecture_registers('x86_64')
            
            # Get register names
            arm_reg_names = {r.register_name for r in arm_registers}
            intel_reg_names = {r.register_name for r in intel_registers}
            
            # Check for no overlap in register names (some common names like SP exist in both)
            # But architecture-specific registers should not cross over
            assert 'X0' in arm_reg_names  # ARM specific
            assert 'X0' not in intel_reg_names
            assert 'RAX' in intel_reg_names  # Intel specific
            assert 'RAX' not in arm_reg_names
            
            # Verify ARM addressing modes are separate from Intel
            arm_modes = db.get_architecture_addressing_modes('aarch64')
            intel_modes = db.get_architecture_addressing_modes('x86_64')
            
            # Each should have their own addressing modes
            assert len(arm_modes) > 0
            assert len(intel_modes) > 0
            
            # Check architecture IDs are different
            arm_arch = db.get_architecture('aarch64')
            intel_arch = db.get_architecture('x86_64')
            assert arm_arch.id != intel_arch.id
            
            # Verify registers have correct architecture IDs
            for reg in arm_registers[:5]:
                assert reg.architecture_id == arm_arch.id
            for reg in intel_registers[:5]:
                assert reg.architecture_id == intel_arch.id
                
            # Verify addressing modes have correct architecture IDs
            for mode in arm_modes[:5]:
                assert mode.architecture_id == arm_arch.id
            for mode in intel_modes[:5]:
                assert mode.architecture_id == intel_arch.id
            
        finally:
            # Cleanup
            db_file = Path(db_path)
            if db_file.exists():
                db_file.unlink()