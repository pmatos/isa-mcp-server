#!/usr/bin/env python3
"""
Basic test script to validate the ISA importer system.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from isa_mcp_server.importers.xed_importer import XEDImporter
from isa_mcp_server.isa_database import ISADatabase


@pytest.mark.asyncio
async def test_xed_parser():
    """Test XED parser with a small sample."""
    print("Testing XED parser...")

    # Create a temporary file with sample XED instruction
    sample_xed = """
{
ICLASS    : MOV
CPL       : 3
CATEGORY  : DATAXFER
EXTENSION : BASE
ISA_SET   : I86
ATTRIBUTES : BYTEOP
PATTERN   : 0xB0 UIMM8()
OPERANDS  : REG0=AL:w IMM0:r:b
IFORM     : MOV_AL_IMMb_B0
}
{
ICLASS    : ADD
CPL       : 3
CATEGORY  : BINARY
EXTENSION : BASE
ISA_SET   : I86
FLAGS     : MUST [ of-mod sf-mod zf-mod af-mod pf-mod cf-mod ]
PATTERN   : 0x00 MOD[mm] MOD!=3 REG[nnn] RM[nnn] MODRM()
OPERANDS  : MEM0:rw:b REG0=GPR8_B():r
IFORM     : ADD_MEMb_GPR8_00
}
"""

    # Test parser
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(sample_xed)
        f.flush()

        try:
            from isa_mcp_server.importers.xed_parser import XEDParser

            parser = XEDParser()

            instructions = list(parser.parse_file(Path(f.name)))

            print(f"Parsed {len(instructions)} instructions:")
            for instr in instructions:
                print(f"  - {instr.iclass}: {instr.category}")

            if len(instructions) == 2:
                print("✓ XED parser test passed")
                return True
            else:
                print("✗ XED parser test failed")
                return False

        finally:
            Path(f.name).unlink()


@pytest.mark.asyncio
async def test_database():
    """Test database operations."""
    print("\nTesting database operations...")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db = ISADatabase(db_path)
        db.initialize_database()

        # Test instruction insertion
        from isa_mcp_server.isa_database import InstructionRecord, OperandRecord

        instruction = InstructionRecord(
            isa="x86",
            mnemonic="MOV",
            category="DATAXFER",
            extension="BASE",
            isa_set="I86",
            description="Move data between registers, memory, and immediate values",
            syntax="MOV destination, source",
            operands=[
                OperandRecord(name="dest", type="register", access="w"),
                OperandRecord(name="src", type="immediate", access="r"),
            ],
        )

        instr_id = db.insert_instruction(instruction)
        print(f"Inserted instruction with ID: {instr_id}")

        # Test retrieval
        retrieved = db.get_instruction("x86", "MOV")
        if retrieved and retrieved.mnemonic == "MOV":
            print("✓ Database test passed")
            return True
        else:
            print("✗ Database test failed")
            return False

    finally:
        Path(db_path).unlink()


@pytest.mark.asyncio
async def test_full_import():
    """Test full import process with XED data."""
    print("\nTesting full import process...")

    xed_path = Path("External/xed")
    if not xed_path.exists():
        print("⚠ Skipping full import test - XED data not found")
        return True

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db = ISADatabase(db_path)
        db.initialize_database()

        importer = XEDImporter(db)

        # Import small subset
        count = 0
        async for instruction in importer.parse_sources(xed_path):
            db.insert_instruction(instruction)
            count += 1
            if count >= 10:  # Test with just 10 instructions
                break

        print(f"Imported {count} instructions")

        # Test search
        search_results = db.search_instructions("MOV")
        print(f"Found {len(search_results)} MOV instructions")

        if count > 0 and len(search_results) > 0:
            print("✓ Full import test passed")
            return True
        else:
            print("✗ Full import test failed")
            return False

    except Exception as e:
        print(f"✗ Full import test failed: {e}")
        return False

    finally:
        Path(db_path).unlink()


async def main():
    """Run all tests."""
    print("ISA Importer System Tests")
    print("=" * 50)

    tests = [test_xed_parser, test_database, test_full_import]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
