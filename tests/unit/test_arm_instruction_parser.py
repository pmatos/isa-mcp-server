"""Unit tests for ARM instruction parser."""

from src.isa_mcp_server.importers.arm_instruction_parser import ARMInstructionParser


class TestARMInstructionParser:
    """Test cases for ARMInstructionParser."""

    def test_init(self):
        """Test parser initialization."""
        parser = ARMInstructionParser()
        assert hasattr(parser, "instruction_cache")
        assert hasattr(parser, "feature_mapping")
        assert isinstance(parser.feature_mapping, dict)
        assert "FEAT_FP" in parser.feature_mapping

    def test_build_feature_mapping(self):
        """Test feature mapping construction."""
        parser = ARMInstructionParser()
        mapping = parser.feature_mapping

        assert mapping["FEAT_FP"] == "FP"
        assert mapping["FEAT_ASIMD"] == "NEON"
        assert mapping["FEAT_AES"] == "AES"
        assert mapping["FEAT_SVE"] == "SVE"

    def test_parse_instructions_file_missing(self, tmp_path):
        """Test parsing non-existent file."""
        parser = ARMInstructionParser()
        missing_file = tmp_path / "missing.json"

        instructions = list(parser.parse_instructions_file(missing_file))
        assert len(instructions) == 0

    def test_parse_instructions_file_valid(self, sample_arm_data_dir):
        """Test parsing valid instructions file."""
        parser = ARMInstructionParser()
        instructions_file = sample_arm_data_dir / "Instructions.json"

        instructions = list(parser.parse_instructions_file(instructions_file))

        # Should get at least one instruction from sample data
        assert len(instructions) > 0

        # Check first instruction
        instruction = instructions[0]
        assert instruction.isa == "aarch64"
        assert instruction.mnemonic == "ADD"
        assert instruction.isa_set == "A64"
        assert "Add immediate" in instruction.description

    def test_extract_mnemonic_from_name(self):
        """Test mnemonic extraction from instruction name."""
        parser = ARMInstructionParser()

        # Test with assembly rules
        instruction_data = {
            "assembly_rules": {
                "main": {
                    "_type": "Instruction.Rules.Rule",
                    "symbols": {
                        "_type": "Instruction.Assembly",
                        "symbols": [
                            {"_type": "Instruction.Symbols.Literal", "value": "MOV"}
                        ],
                    },
                }
            }
        }

        mnemonic = parser._extract_mnemonic("MOV_reg", instruction_data)
        assert mnemonic == "MOV"

    def test_extract_mnemonic_fallback(self):
        """Test mnemonic extraction fallback."""
        parser = ARMInstructionParser()

        # Test fallback when no assembly rules
        instruction_data = {}
        mnemonic = parser._extract_mnemonic("ADD_immediate_123", instruction_data)
        assert mnemonic == "ADDIMMEDIATE"

    def test_extract_description(self):
        """Test description extraction."""
        parser = ARMInstructionParser()

        # Test with description object
        instruction_data = {"description": {"after": "Test instruction description"}}

        description = parser._extract_description(instruction_data)
        assert description == "Test instruction description"

    def test_extract_description_fallback(self):
        """Test description extraction fallback."""
        parser = ARMInstructionParser()

        # Test fallback
        instruction_data = {}
        description = parser._extract_description(instruction_data)
        assert description == "ARM AArch64 instruction"

    def test_generate_syntax_no_operands(self):
        """Test syntax generation without operands."""
        parser = ARMInstructionParser()

        syntax = parser._generate_syntax("NOP", [])
        assert syntax == "NOP"

    def test_generate_basic_syntax(self):
        """Test basic syntax generation."""
        parser = ARMInstructionParser()

        syntax = parser._generate_basic_syntax("RET")
        assert syntax == "RET"
