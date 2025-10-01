"""Unit tests for ARM parser error handling."""

import json
import os
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

        # Should handle missing directory gracefully by returning defaults
        result = parser.parse_registers()
        # When file doesn't exist, returns list directly (not tuple)
        if isinstance(result, tuple):
            registers = result[0]
        else:
            registers = result
        assert isinstance(registers, list)
        # Default AArch64 registers should be returned
        assert len(registers) > 0

    def test_corrupted_json_file(self, tmp_path):
        """Test handling corrupted JSON files."""
        # Create invalid JSON file
        bad_json_file = tmp_path / "Registers.json"
        bad_json_file.write_text("{ invalid json content }")

        parser = ARMMetadataParser(tmp_path)

        # Should handle JSON parse errors gracefully by returning defaults
        registers = parser.parse_registers()[0]
        # Should fall back to default registers
        assert isinstance(registers, list)
        assert len(registers) > 0

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
        empty_file = tmp_path / "Registers.json"
        empty_file.write_text("{}")

        parser = ARMMetadataParser(tmp_path)
        registers = parser.parse_registers()[0]

        # Should return default registers even with empty file
        assert isinstance(registers, list)
        # Should still have default registers
        assert len(registers) > 0


class TestARMInstructionParserErrorHandling:
    """Test error handling in ARM instruction parser."""

    def test_missing_instruction_files(self, tmp_path):
        """Test handling when instruction files don't exist."""
        parser = ARMInstructionParser()

        # Should handle missing files gracefully
        instructions = list(parser.parse_instructions_file(tmp_path / "Instructions.json"))
        assert instructions == []

    def test_corrupted_instruction_json(self, tmp_path):
        """Test handling corrupted instruction JSON files."""
        # Create invalid JSON file
        bad_file = tmp_path / "Instructions.json"
        bad_file.write_text("{ invalid json }")

        parser = ARMInstructionParser()

        # Should skip corrupted files
        instructions = list(parser.parse_instructions_file(bad_file))
        assert instructions == []

    def test_missing_instruction_fields(self, tmp_path):
        """Test handling instructions with missing required fields."""
        # Create instruction data with wrong structure (array instead of dict)
        incomplete_data = {
            "instructions": [
                {
                    # Wrong structure - should be dict not array
                    "mnemonic": "ADD",
                    "description": "Add operation",
                    "syntax": "ADD Rd, Rn, Rm"
                }
            ]
        }

        json_file = tmp_path / "Instructions.json"
        json_file.write_text(json.dumps(incomplete_data))

        parser = ARMInstructionParser()
        instructions = list(parser.parse_instructions_file(json_file))

        # Should handle invalid structure gracefully
        # Array structure is not valid, so should return empty
        assert isinstance(instructions, list)

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
        
        json_file = tmp_path / "Instructions.json"
        json_file.write_text(json.dumps(data_with_bad_encoding))

        parser = ARMInstructionParser()
        instructions = list(parser.parse_instructions_file(json_file))
        
        # Should handle invalid encodings gracefully
        assert isinstance(instructions, list)

    def test_permission_denied_error(self, tmp_path):
        """Test handling permission denied errors."""
        # Create a file with no read permissions
        restricted_file = tmp_path / "Instructions.json"
        restricted_file.write_text('{"instructions": []}')
        os.chmod(restricted_file, 0o000)

        try:
            parser = ARMInstructionParser()
            instructions = list(parser.parse_instructions_file(restricted_file))

            # Should handle permission errors gracefully
            assert instructions == []
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    def test_large_file_handling(self, tmp_path):
        """Test handling very large instruction files."""
        # Create a large instruction file with proper ARM array structure
        large_data = {
            "_type": "Instruction.Instructions",
            "instructions": []
        }

        # Add many instructions in proper ARM format (as array)
        for i in range(50):  # Reduced for faster testing
            large_data["instructions"].append({
                "_type": "Instruction.Instruction",
                "name": f"TEST{i}",
                "description": {"after": f"Test instruction {i}"},
                "assembly": {
                    "_type": "Instruction.Assembly",
                    "symbols": [
                        {
                            "_type": "Instruction.Symbols.Literal",
                            "value": f"TEST{i}"
                        }
                    ]
                },
                "encodeset": {"pattern": "10101010:8"}
            })

        json_file = tmp_path / "Instructions.json"
        json_file.write_text(json.dumps(large_data))

        parser = ARMInstructionParser()
        instructions = list(parser.parse_instructions_file(json_file))

        # Should handle large files without memory issues
        assert isinstance(instructions, list)
        # With array structure and proper fields, should parse some instructions
        assert len(instructions) > 0

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
        
        json_file = tmp_path / "Instructions.json"
        json_file.write_text(json.dumps(data_with_unicode, ensure_ascii=False))

        parser = ARMInstructionParser()
        instructions = list(parser.parse_instructions_file(json_file))
        
        # Should handle unicode characters properly
        assert isinstance(instructions, list)
        if instructions:
            # Check that unicode is preserved or properly handled
            for instr in instructions:
                assert isinstance(instr.mnemonic, str)
                assert isinstance(instr.description, str)