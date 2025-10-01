"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from src.isa_mcp_server.isa_database import ISADatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db = ISADatabase(db_path)
        db.initialize_database()
        yield db
    finally:
        # Cleanup
        db_file = Path(db_path)
        if db_file.exists():
            db_file.unlink()


@pytest.fixture
def sample_arm_data_dir():
    """Create a temporary directory with sample ARM data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create minimal Instructions.json
        instructions_data = {
            "_meta": {
                "version": {
                    "architecture": "v9Ap6-A",
                    "build": "83",
                    "ref": "2025-06_rel",
                }
            },
            "_type": "Instruction.Instructions",
            "instructions": [
                {
                    "_type": "Instruction.Instruction",
                    "name": "ADD_immediate",
                    "description": {"after": "Add immediate to register"},
                    "assembly": {
                        "_type": "Instruction.Assembly",
                        "symbols": [
                            {"_type": "Instruction.Symbols.Literal", "value": "ADD"}
                        ],
                    },
                    "encodeset": {
                        "pattern": "sf:1 op:1 S:1 100010 shift:2 imm12:12 Rn:5 Rd:5"
                    },
                }
            ],
        }

        instructions_file = temp_path / "Instructions.json"
        with open(instructions_file, "w") as f:
            import json

            json.dump(instructions_data, f)

        # Create minimal Registers.json
        registers_data = {"_type": "Register.RegisterSet", "registers": {}}

        registers_file = temp_path / "Registers.json"
        with open(registers_file, "w") as f:
            import json

            json.dump(registers_data, f)

        # Create minimal Features.json
        features_data = {
            "_type": "Features",
            "features": {
                "FEAT_BASE": {"description": "Base architecture"},
                "FEAT_FP": {"description": "Floating point"},
            },
        }

        features_file = temp_path / "Features.json"
        with open(features_file, "w") as f:
            import json

            json.dump(features_data, f)

        yield temp_path


@pytest.fixture
def sample_xed_data_dir():
    """Create a temporary directory with sample XED data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        datafiles_dir = temp_path / "datafiles"
        datafiles_dir.mkdir()

        # Create minimal xed-isa.txt
        isa_content = """{
ICLASS    : MOV
CPL       : 3
CATEGORY  : DATAXFER
EXTENSION : BASE
ISA_SET   : I86
PATTERN   : 0x8B MOD[mm] MOD!=3 REG[rrr] RM[nnn] MODRM()
OPERANDS  : REG0=GPRv():w MEM0:r:v
}
"""

        isa_file = datafiles_dir / "xed-isa.txt"
        with open(isa_file, "w") as f:
            f.write(isa_content)

        # Create xed-regs.txt file
        regs_file = datafiles_dir / "xed-regs.txt"
        regs_content = """# Sample XED register file
# Format: name class width maxval enc(hex) regid
# 32-bit GPRs
EAX gpr 32 0 0
EBX gpr 32 0 1
ECX gpr 32 0 2
EDX gpr 32 0 3
# 64-bit GPRs
RAX gpr 64 0 0
RBX gpr 64 0 1
RCX gpr 64 0 2
RDX gpr 64 0 3
"""
        with open(regs_file, "w") as f:
            f.write(regs_content)

        # Create VERSION file
        version_file = temp_path / "VERSION"
        with open(version_file, "w") as f:
            f.write("2025.01.01\n")

        yield temp_path
