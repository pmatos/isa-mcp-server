"""Unit tests for XED metadata parser error handling."""

import tempfile
from pathlib import Path

import pytest

from src.isa_mcp_server.xed_metadata_parser import XEDMetadataParser


class TestXEDMetadataParserErrorHandling:
    """Test error handling in XED metadata parser."""

    def test_missing_register_file(self, tmp_path):
        """Test handling when register file doesn't exist."""
        # Create parser with non-existent directory
        parser = XEDMetadataParser(tmp_path / "nonexistent")
        
        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Register file not found"):
            parser.parse_registers()

    def test_empty_register_file(self, tmp_path):
        """Test handling empty register file."""
        # Create empty register file
        reg_file = tmp_path / "xed-regs.txt"
        reg_file.write_text("")
        
        parser = XEDMetadataParser(tmp_path)
        
        # Should return empty lists without error
        x86_32_regs, x86_64_regs = parser.parse_registers()
        assert x86_32_regs == []
        assert x86_64_regs == []

    def test_malformed_register_lines(self, tmp_path):
        """Test handling malformed register definition lines."""
        # Create register file with malformed lines
        reg_file = tmp_path / "xed-regs.txt"
        reg_file.write_text("""# Valid header
# This is a comment
EAX gpr 32 0 0
# Malformed lines that should be skipped
INVALID_REG
SHORT gpr
# Line with invalid width
BAD_WIDTH gpr invalid_width 0 0
# Line with invalid register name
123invalid gpr 32 0 0
# Line with special characters in name
reg@name gpr 32 0 0
# Valid line at end
EBX gpr 32 0 1
""")
        
        parser = XEDMetadataParser(tmp_path)
        x86_32_regs, x86_64_regs = parser.parse_registers()
        
        # Should parse valid registers and skip invalid ones
        assert len(x86_32_regs) >= 2  # At least EAX and EBX
        reg_names = [r.register_name for r in x86_32_regs]
        assert "EAX" in reg_names
        assert "EBX" in reg_names
        
        # Invalid registers should not appear
        assert "INVALID_REG" not in reg_names
        assert "SHORT" not in reg_names
        assert "BAD_WIDTH" not in reg_names
        assert "123invalid" not in reg_names
        assert "reg@name" not in reg_names

    def test_corrupted_register_file(self, tmp_path):
        """Test handling corrupted register file."""
        # Create register file that can't be read properly
        reg_file = tmp_path / "xed-regs.txt" 
        reg_file.write_bytes(b'\x00\x01\x02invalid\xff\xfe')  # Binary data
        
        parser = XEDMetadataParser(tmp_path)
        
        # Should handle decoding errors gracefully
        try:
            x86_32_regs, x86_64_regs = parser.parse_registers()
            # Should return empty or partial results, not crash
            assert isinstance(x86_32_regs, list)
            assert isinstance(x86_64_regs, list)
        except RuntimeError as e:
            # Or raise a clean error message
            assert "Failed to read register file" in str(e)

    def test_register_width_validation(self, tmp_path):
        """Test validation of register widths."""
        # Create register file with invalid widths
        reg_file = tmp_path / "xed-regs.txt"
        reg_file.write_text("""# Test width validation
# Valid registers
EAX gpr 32 0 0
EBX gpr 32 0 1
# Invalid widths - should be skipped
ZERO_WIDTH gpr 0 0 2
NEGATIVE_WIDTH gpr -8 0 3
TOO_LARGE gpr 1024 0 4
# Complex width format
ECX gpr 32/16 0 5
""")
        
        parser = XEDMetadataParser(tmp_path)
        x86_32_regs, x86_64_regs = parser.parse_registers()
        
        # Should parse valid registers
        reg_names = [r.register_name for r in x86_32_regs]
        assert "EAX" in reg_names
        assert "EBX" in reg_names
        assert "ECX" in reg_names  # Complex width should work
        
        # Invalid width registers should be skipped
        assert "ZERO_WIDTH" not in reg_names
        assert "NEGATIVE_WIDTH" not in reg_names
        assert "TOO_LARGE" not in reg_names

    def test_encoding_id_validation(self, tmp_path):
        """Test handling of invalid encoding IDs."""
        reg_file = tmp_path / "xed-regs.txt"
        reg_file.write_text("""# Test encoding ID handling
# Valid encoding IDs
EAX gpr 32 0 0
EBX gpr 32 0 1
# Invalid encoding IDs - should default to None
ECX gpr 32 0 invalid_id
EDX gpr 32 0 not_a_number
# Missing encoding ID
ESI gpr 32 0
""")
        
        parser = XEDMetadataParser(tmp_path)
        x86_32_regs, x86_64_regs = parser.parse_registers()
        
        # Should parse all valid registers
        reg_dict = {r.register_name: r for r in x86_32_regs}
        
        assert "EAX" in reg_dict
        assert reg_dict["EAX"].encoding_id == 0
        
        assert "EBX" in reg_dict  
        assert reg_dict["EBX"].encoding_id == 1
        
        # Invalid encoding IDs should be None
        assert "ECX" in reg_dict
        assert reg_dict["ECX"].encoding_id is None
        
        assert "EDX" in reg_dict
        assert reg_dict["EDX"].encoding_id is None
        
        assert "ESI" in reg_dict
        assert reg_dict["ESI"].encoding_id is None

    def test_machine_modes_file_missing(self, tmp_path):
        """Test handling when machine modes file is missing."""
        parser = XEDMetadataParser(tmp_path)
        
        # Should return default modes
        modes = parser.get_machine_modes()
        assert modes == {"x86_32": "LEGACY_32", "x86_64": "LONG_64"}

    def test_machine_modes_file_empty(self, tmp_path):
        """Test handling empty machine modes file."""
        modes_file = tmp_path / "xed-machine-modes-enum.txt"
        modes_file.write_text("")
        
        parser = XEDMetadataParser(tmp_path)
        modes = parser.get_machine_modes()
        
        # Should return empty dict or defaults
        assert isinstance(modes, dict)

    def test_permission_denied_error(self, tmp_path):
        """Test handling permission denied errors."""
        # Create a directory instead of file (will cause permission issues)
        reg_dir = tmp_path / "xed-regs.txt"
        reg_dir.mkdir()
        
        parser = XEDMetadataParser(tmp_path)
        
        # Should handle permission/IO errors gracefully
        with pytest.raises(RuntimeError, match="Failed to read register file"):
            parser.parse_registers()