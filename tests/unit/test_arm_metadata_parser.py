"""Unit tests for ARMMetadataParser."""

import pytest
from pathlib import Path

from src.isa_mcp_server.arm_metadata_parser import ARMMetadataParser


class TestARMMetadataParser:
    """Test cases for ARMMetadataParser."""

    def test_init(self, sample_arm_data_dir):
        """Test parser initialization."""
        parser = ARMMetadataParser(sample_arm_data_dir)
        assert parser.arm_dir == sample_arm_data_dir
        assert parser.instructions_file == sample_arm_data_dir / "Instructions.json"
        assert parser.registers_file == sample_arm_data_dir / "Registers.json"
        assert parser.features_file == sample_arm_data_dir / "Features.json"

    def test_get_version_info(self, sample_arm_data_dir):
        """Test version information extraction."""
        parser = ARMMetadataParser(sample_arm_data_dir)
        version = parser.get_version_info()
        assert version == "v9Ap6-A-2025-06_rel-83"

    def test_get_version_info_missing_file(self, tmp_path):
        """Test version info when file is missing."""
        parser = ARMMetadataParser(tmp_path)
        version = parser.get_version_info()
        assert version is None

    def test_parse_architectures(self, sample_arm_data_dir):
        """Test architecture parsing."""
        parser = ARMMetadataParser(sample_arm_data_dir)
        architectures = parser.parse_architectures()
        
        assert len(architectures) == 1
        arch = architectures[0]
        assert arch.isa_name == "aarch64"
        assert arch.word_size == 64
        assert arch.endianness == "little"
        assert arch.machine_mode == "AARCH64"
        assert "ARM AArch64" in arch.description

    def test_parse_registers_default(self, sample_arm_data_dir):
        """Test default register parsing."""
        parser = ARMMetadataParser(sample_arm_data_dir)
        aarch64_registers = parser.parse_registers()[0]
        
        # Should have general purpose registers
        register_names = [reg.register_name for reg in aarch64_registers]
        
        # Check for X0-X30
        for i in range(31):
            assert f"X{i}" in register_names
            assert f"W{i}" in register_names
        
        # Check for special registers
        assert "SP" in register_names
        assert "XZR" in register_names
        assert "WZR" in register_names
        assert "PC" in register_names
        assert "PSTATE" in register_names
        
        # Check for SIMD registers
        for i in range(32):
            assert f"V{i}" in register_names
            assert f"D{i}" in register_names
            assert f"S{i}" in register_names
            assert f"H{i}" in register_names
            assert f"B{i}" in register_names

    def test_parse_addressing_modes(self, sample_arm_data_dir):
        """Test addressing mode parsing."""
        parser = ARMMetadataParser(sample_arm_data_dir)
        aarch64_modes = parser.parse_addressing_modes()[0]
        
        mode_names = [mode.mode_name for mode in aarch64_modes]
        
        expected_modes = [
            "register_direct",
            "immediate", 
            "base_register",
            "base_offset",
            "pre_indexed",
            "post_indexed",
            "register_offset",
            "scaled_register_offset",
            "pc_relative",
            "literal"
        ]
        
        for expected_mode in expected_modes:
            assert expected_mode in mode_names

    def test_get_cpu_features_default(self, sample_arm_data_dir):
        """Test CPU features extraction."""
        parser = ARMMetadataParser(sample_arm_data_dir)
        features = parser.get_cpu_features()
        
        assert "aarch64" in features
        aarch64_features = features["aarch64"]
        assert "FEAT_BASE" in aarch64_features
        assert "FEAT_FP" in aarch64_features

    def test_get_cpu_features_missing_file(self, tmp_path):
        """Test CPU features when file is missing."""
        parser = ARMMetadataParser(tmp_path)
        features = parser.get_cpu_features()
        
        assert features == {"aarch64": ["BASE"]}