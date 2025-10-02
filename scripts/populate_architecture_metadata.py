#!/usr/bin/env python3
"""
Architecture Metadata Population Script

This script populates the database with architecture metadata extracted
from XED datafiles. It should be run after the initial instruction import
to add architecture specifications.

Usage:
    python populate_architecture_metadata.py [--db-path isa_docs.db]
        [--xed-dir External/xed]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from isa_mcp_server.isa_database import ISADatabase
from isa_mcp_server.xed_metadata_parser import XEDMetadataParser


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("populate_architecture_metadata.log"),
        ],
    )


def populate_architecture_metadata(db: ISADatabase, xed_dir: Path) -> bool:
    """Populate architecture metadata from XED datafiles."""
    try:
        logging.info(f"Starting architecture metadata population from {xed_dir}")

        # Initialize XED parser
        parser = XEDMetadataParser(xed_dir / "datafiles")

        # Parse architecture specifications
        logging.info("Parsing architecture specifications...")
        architectures = parser.parse_architectures()

        # Parse registers
        logging.info("Parsing register definitions...")
        x86_32_registers, x86_64_registers = parser.parse_registers()

        # Parse addressing modes
        logging.info("Parsing addressing modes...")
        x86_32_modes, x86_64_modes = parser.parse_addressing_modes()

        # Insert architectures
        logging.info("Inserting architecture specifications...")
        arch_ids = {}
        for arch in architectures:
            arch_id = db.insert_architecture(arch)
            arch_ids[arch.isa_name] = arch_id
            logging.info(f"Inserted architecture: {arch.isa_name} (ID: {arch_id})")

        # Insert registers
        logging.info("Inserting register definitions...")

        # Update architecture IDs for registers
        for reg in x86_32_registers:
            reg.architecture_id = arch_ids["x86_32"]
            db.insert_register(reg)

        for reg in x86_64_registers:
            reg.architecture_id = arch_ids["x86_64"]
            db.insert_register(reg)

        logging.info(f"Inserted {len(x86_32_registers)} x86_32 registers")
        logging.info(f"Inserted {len(x86_64_registers)} x86_64 registers")

        # Insert addressing modes
        logging.info("Inserting addressing modes...")

        # Update architecture IDs for addressing modes
        for mode in x86_32_modes:
            mode.architecture_id = arch_ids["x86_32"]
            db.insert_addressing_mode(mode)

        for mode in x86_64_modes:
            mode.architecture_id = arch_ids["x86_64"]
            db.insert_addressing_mode(mode)

        logging.info(f"Inserted {len(x86_32_modes)} x86_32 addressing modes")
        logging.info(f"Inserted {len(x86_64_modes)} x86_64 addressing modes")

        # Validation
        logging.info("Validating populated data...")

        # Check that architectures were inserted
        for isa_name in ["x86_32", "x86_64"]:
            arch = db.get_architecture(isa_name)
            if not arch:
                logging.error(f"Architecture {isa_name} not found after insertion")
                return False

            registers = db.get_architecture_registers(isa_name)
            modes = db.get_architecture_addressing_modes(isa_name)

            logging.info(
                f"Architecture {isa_name}: {len(registers)} registers, "
                f"{len(modes)} addressing modes"
            )

        logging.info("Architecture metadata population completed successfully!")
        return True

    except Exception as e:
        logging.error(f"Error during architecture metadata population: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Populate architecture metadata from XED datafiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                              # Use default paths
  %(prog)s --db-path custom.db --xed-dir External/xed  # Custom paths
  %(prog)s --verbose                                    # Enable verbose logging
        """,
    )

    parser.add_argument(
        "--db-path",
        default="isa_docs.db",
        help="Path to SQLite database file (default: isa_docs.db)",
    )

    parser.add_argument(
        "--xed-dir",
        type=Path,
        default=Path("External/xed"),
        help="Path to XED directory (default: External/xed)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force repopulation even if architecture metadata already exists",
    )

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)

    # Validate paths
    if not args.xed_dir.exists():
        logging.error(f"XED directory not found: {args.xed_dir}")
        sys.exit(1)

    xed_datafiles = args.xed_dir / "datafiles"
    if not xed_datafiles.exists():
        logging.error(f"XED datafiles directory not found: {xed_datafiles}")
        sys.exit(1)

    # Initialize database
    db = ISADatabase(args.db_path)

    # Ensure database schema is up to date
    logging.info("Initializing database schema...")
    db.initialize_database()

    # Check if architecture metadata already exists
    if not args.force:
        existing_arch = db.get_architecture("x86_32")
        if existing_arch:
            logging.info(
                "Architecture metadata already exists. Use --force to repopulate."
            )
            print("Architecture metadata already exists. Use --force to repopulate.")
            sys.exit(0)

    # Populate architecture metadata
    success = populate_architecture_metadata(db, args.xed_dir)

    if success:
        print("✓ Architecture metadata population completed successfully!")

        # Print summary
        print("\n" + "=" * 50)
        print("ARCHITECTURE METADATA SUMMARY")
        print("=" * 50)

        for isa_name in ["x86_32", "x86_64"]:
            arch = db.get_architecture(isa_name)
            registers = db.get_architecture_registers(isa_name)
            modes = db.get_architecture_addressing_modes(isa_name)

            print(f"\n{isa_name.upper()}:")
            print(f"  Description: {arch.description}")
            print(f"  Word Size: {arch.word_size} bits")
            print(f"  Endianness: {arch.endianness}")
            print(f"  Machine Mode: {arch.machine_mode}")
            print(f"  Registers: {len(registers)}")
            print(f"  Addressing Modes: {len(modes)}")

            # Show main registers
            main_regs = [
                r for r in registers if r.is_main_register and r.register_class == "gpr"
            ]
            reg_names = [r.register_name for r in main_regs]
            print(f"  Main GPRs: {', '.join(reg_names)}")

        sys.exit(0)
    else:
        print("✗ Architecture metadata population failed. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
