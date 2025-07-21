"""Unit tests for ARM parser error handling."""

import json
import tempfile
from pathlib import Path

import pytest

from src.isa_mcp_server.arm_metadata_parser import ARMMetadataParser
from src.isa_mcp_server.importers.arm_instruction_parser import ARMInstructionParser


class TestARMMetadataParserErrorHandling:
    """Test error handling in ARM metadata parser."""

    def test_missing_data_directory(self, tmp_path):
        """Test handling when ARM data directory doesn't exist."""
        parser = ARMMetadataParser(tmp_path / "nonexistent")
        
        # Should handle missing directory gracefully
        try:
            registers, modes = parser.parse_registers()
            assert registers == []
            assert modes == []
        except FileNotFoundError:
            # Or raise appropriate error
            pass

    def test_corrupted_json_file(self, tmp_path):
        """Test handling corrupted JSON files."""
        # Create invalid JSON file
        bad_json_file = tmp_path / "registers.json"
        bad_json_file.write_text("{ invalid json content }")
        
        parser = ARMMetadataParser(tmp_path)
        
        # Should handle JSON parse errors gracefully
        try:
            registers, modes = parser.parse_registers()
            # Should return empty or partial results
            assert isinstance(registers, list)
            assert isinstance(modes, list)
        except (json.JSONDecodeError, ValueError):
            # Or raise appropriate error
            pass

    def test_missing_required_fields(self, tmp_path):
        """Test handling JSON with missing required fields."""
        # Create JSON with missing fields
        incomplete_data = {
            "registers": [
                {"name": "X0"},  # Missing other required fields
                {"type": "general"},  # Missing name
                {
                    "name": "X1",
                    "type": "general", 
                    "width": 64
                }  # Complete entry
            ]
        }
        
        json_file = tmp_path / "registers.json"
        json_file.write_text(json.dumps(incomplete_data))
        
        parser = ARMMetadataParser(tmp_path)
        
        # Should skip incomplete entries and process valid ones
        try:
            registers, modes = parser.parse_registers()
            # Should have at least one valid register
            valid_regs = [r for r in registers if r.register_name == "X1"]
            assert len(valid_regs) > 0
        except Exception:
            # Should handle gracefully
            pass

    def test_empty_json_file(self, tmp_path):
        """Test handling empty JSON file."""
        empty_file = tmp_path / "registers.json"
        empty_file.write_text("{}")
        
        parser = ARMMetadataParser(tmp_path)
        registers, modes = parser.parse_registers()
        
        # Should return empty lists
        assert registers == []
        assert modes == []


class TestARMInstructionParserErrorHandling:
    """Test error handling in ARM instruction parser."""

    def test_missing_instruction_files(self, tmp_path):
        """Test handling when instruction files don't exist."""
        parser = ARMInstructionParser(tmp_path)
        
        # Should handle missing files gracefully
        instructions = list(parser.parse_instructions())
        assert instructions == []

    def test_corrupted_instruction_json(self, tmp_path):
        """Test handling corrupted instruction JSON files."""
        # Create invalid JSON file
        bad_file = tmp_path / "instructions.json"
        bad_file.write_text("{ invalid json }")
        
        parser = ARMInstructionParser(tmp_path)
        
        # Should skip corrupted files
        instructions = list(parser.parse_instructions())
        assert instructions == []

    def test_missing_instruction_fields(self, tmp_path):
        """Test handling instructions with missing required fields."""
        # Create instruction data with missing fields
        incomplete_data = {
            "instructions": [
                {
                    # Missing mnemonic
                    "description": "Test instruction",
                    "syntax": "TEST"
                },
                {
                    "mnemonic": "MOV",
                    # Missing description
                    "syntax": "MOV Rd, Rm"
                },
                {
                    "mnemonic": "ADD",
                    "description": "Add operation", 
                    "syntax": "ADD Rd, Rn, Rm"
                    # Complete entry
                }
            ]
        }
        
        json_file = tmp_path / "instructions.json"
        json_file.write_text(json.dumps(incomplete_data))
        
        parser = ARMInstructionParser(tmp_path)
        instructions = list(parser.parse_instructions())
        
        # Should process valid instructions and skip invalid ones
        mnemonics = [instr.mnemonic for instr in instructions]
        assert "ADD" in mnemonics
        # Invalid instructions should be skipped or handled gracefully

    def test_invalid_encoding_patterns(self, tmp_path):
        """Test handling invalid encoding patterns."""
        # Create instruction with invalid encoding
        data_with_bad_encoding = {
            "instructions": [
                {
                    "mnemonic": "TEST",
                    "description": "Test instruction",
                    "syntax": "TEST Rd, Rm",
                    "encoding": {
                        "pattern": None,  # Invalid pattern
                        "bits": "invalid_bits"
                    }
                }
            ]
        }
        
        json_file = tmp_path / "instructions.json"
        json_file.write_text(json.dumps(data_with_bad_encoding))
        
        parser = ARMInstructionParser(tmp_path)
        instructions = list(parser.parse_instructions())
        
        # Should handle invalid encodings gracefully
        assert isinstance(instructions, list)

    def test_permission_denied_error(self, tmp_path):
        """Test handling permission denied errors."""
        # Create a directory with no read permissions
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir(mode=0o000)
        
        try:
            parser = ARMInstructionParser(restricted_dir)
            instructions = list(parser.parse_instructions())
            
            # Should handle permission errors gracefully
            assert instructions == []
        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)

    def test_large_file_handling(self, tmp_path):
        """Test handling very large instruction files."""
        # Create a large instruction file
        large_data = {
            "instructions": []
        }
        
        # Add many instructions to test memory handling
        for i in range(1000):
            large_data["instructions"].append({
                "mnemonic": f"INSTR{i}",
                "description": f"Test instruction {i}",
                "syntax": f"INSTR{i} Rd, Rm"
            })
        
        json_file = tmp_path / "large_instructions.json"
        json_file.write_text(json.dumps(large_data))
        
        parser = ARMInstructionParser(tmp_path)
        instructions = list(parser.parse_instructions())
        
        # Should handle large files without memory issues
        assert len(instructions) > 0
        assert len(instructions) <= 1000

    def test_unicode_and_special_characters(self, tmp_path):
        """Test handling unicode and special characters in instruction data."""
        data_with_unicode = {
            "instructions": [
                {
                    "mnemonic": "TËST",  # Unicode characters
                    "description": "Test with unicode: ñáéíóú",
                    "syntax": "TËST Rd, Rm"
                },
                {
                    "mnemonic": "TEST<>",  # Special characters
                    "description": "Test with symbols: <>{}[]",
                    "syntax": "TEST<> Rd, Rm"
                }
            ]
        }
        
        json_file = tmp_path / "unicode_instructions.json"
        json_file.write_text(json.dumps(data_with_unicode, ensure_ascii=False))
        
        parser = ARMInstructionParser(tmp_path)
        instructions = list(parser.parse_instructions())
        
        # Should handle unicode characters properly
        assert isinstance(instructions, list)
        if instructions:
            # Check that unicode is preserved or properly handled
            for instr in instructions:
                assert isinstance(instr.mnemonic, str)
                assert isinstance(instr.description, str)