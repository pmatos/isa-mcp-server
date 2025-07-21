#!/usr/bin/env python3
"""
ISA Data Import Script

This script imports instruction set architecture data from various sources
into a unified SQLite database for use by the MCP server.

Usage:
    python import_isa_data.py --all
    python import_isa_data.py --intel --source-dir External/xed
    python import_isa_data.py --arm --source-dir /path/to/arm/docs
    python import_isa_data.py --riscv --source-dir /path/to/riscv/docs
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from isa_mcp_server.isa_database import ISADatabase
from isa_mcp_server.importers.base import importer_registry
from isa_mcp_server.importers.xed_importer import XEDImporter
from isa_mcp_server.importers.arm_importer import ARMImporter


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('import_isa_data.log')
        ]
    )


async def import_intel_data(
    db: ISADatabase, source_dir: Path, skip_metadata: bool = False
) -> Dict:
    """Import Intel x86_32 and x86_64 data from XED."""
    logging.info(f"Importing Intel x86_32 and x86_64 data from {source_dir}")
    
    importer = XEDImporter(db)
    result = await importer.import_from_source(source_dir, skip_metadata=skip_metadata)
    
    if result['success']:
        instr_count = result['stats']['instructions_inserted']
        metadata_msg = ""
        if 'metadata_imported' in result and result['metadata_imported']:
            metadata_msg = " (including architecture metadata)"
        elif skip_metadata:
            metadata_msg = " (metadata skipped)"
        logging.info(
            f"Intel import successful: {instr_count} instructions imported{metadata_msg}"
        )
    else:
        logging.error(f"Intel import failed: {result['error']}")
    
    return result


async def import_arm_data(db: ISADatabase, source_dir: Path, skip_metadata: bool = False) -> Dict:
    """Import ARM AArch64 data from machine-readable JSON files."""
    logging.info(f"Importing ARM AArch64 data from {source_dir}")
    
    importer = ARMImporter(db)
    result = await importer.import_from_source(source_dir, skip_metadata=skip_metadata)
    
    if result['success']:
        instr_count = result['stats']['instructions_inserted']
        metadata_msg = ""
        if 'metadata_imported' in result and result['metadata_imported']:
            metadata_msg = " (including architecture metadata)"
        elif skip_metadata:
            metadata_msg = " (metadata skipped)"
        logging.info(
            f"ARM import successful: {instr_count} instructions imported{metadata_msg}"
        )
    else:
        logging.error(f"ARM import failed: {result['error']}")
    
    return result


async def import_riscv_data(db: ISADatabase, source_dir: Path) -> Dict:
    """Import RISC-V data (placeholder for future implementation)."""
    logging.warning("RISC-V importer not yet implemented")
    return {'success': False, 'error': 'RISC-V importer not implemented'}


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Import ISA instruction data into database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                                    # Import all available ISAs with metadata
  %(prog)s --intel --source-dir External/xed       # Import Intel x86_32/x86_64 from XED
  %(prog)s --intel --skip-metadata                 # Import Intel instructions only
  %(prog)s --arm --source-dir /path/to/arm         # Import ARM (future)
  %(prog)s --riscv --source-dir /path/to/riscv     # Import RISC-V (future)
  %(prog)s --intel --db-path custom.db             # Use custom database path
        """
    )
    
    # Database options
    parser.add_argument(
        '--db-path',
        default='isa_docs.db',
        help='Path to SQLite database file (default: isa_docs.db)'
    )
    
    parser.add_argument(
        '--recreate-db',
        action='store_true',
        help='Recreate database (WARNING: deletes existing data)'
    )
    
    # ISA selection
    parser.add_argument(
        '--all',
        action='store_true',
        help='Import all available ISAs'
    )
    
    parser.add_argument(
        '--intel',
        action='store_true',
        help='Import Intel x86_32 and x86_64 instructions'
    )
    
    parser.add_argument(
        '--arm',
        action='store_true',
        help='Import ARM AArch64 instructions'
    )
    
    parser.add_argument(
        '--riscv',
        action='store_true',
        help='Import RISC-V instructions (future)'
    )
    
    # Source directories
    parser.add_argument(
        '--source-dir',
        type=Path,
        help='Source directory for ISA data'
    )
    
    parser.add_argument(
        '--intel-source-dir',
        type=Path,
        default=Path('External/xed'),
        help='Source directory for Intel XED data (default: External/xed)'
    )
    
    parser.add_argument(
        '--arm-source-dir',
        type=Path,
        default=Path('External/arm-machine-readable'),
        help='Source directory for ARM data (default: External/arm-machine-readable)'
    )
    
    parser.add_argument(
        '--riscv-source-dir',
        type=Path,
        help='Source directory for RISC-V data'
    )
    
    # Logging options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    parser.add_argument(
        '--skip-metadata',
        action='store_true',
        help='Skip architecture metadata import (instructions only)'
    )
    
    args = parser.parse_args()
    
    # Set up logging
    if args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        setup_logging(args.verbose)
    
    # Validate arguments
    if not any([args.all, args.intel, args.arm, args.riscv]):
        parser.error("Must specify at least one ISA to import (--all, --intel, --arm, or --riscv)")
    
    # Initialize database
    db = ISADatabase(args.db_path)
    
    if args.recreate_db:
        if Path(args.db_path).exists():
            logging.info(f"Removing existing database: {args.db_path}")
            Path(args.db_path).unlink()
    
    logging.info("Initializing database schema")
    db.initialize_database()
    
    # Track results
    results = {}
    overall_success = True
    
    # Import Intel x86
    if args.all or args.intel:
        source_dir = args.source_dir or args.intel_source_dir
        if not source_dir.exists():
            logging.error(f"Intel source directory not found: {source_dir}")
            overall_success = False
        else:
            results['intel'] = await import_intel_data(
                db, source_dir, skip_metadata=args.skip_metadata
            )
            if not results['intel']['success']:
                overall_success = False
    
    # Import ARM (future)
    if args.all or args.arm:
        source_dir = args.source_dir or args.arm_source_dir
        if not source_dir or not source_dir.exists():
            logging.error(f"ARM source directory not found: {source_dir}")
            overall_success = False
        else:
            results['arm'] = await import_arm_data(db, source_dir, skip_metadata=args.skip_metadata)
            if not results['arm']['success']:
                overall_success = False
    
    # Import RISC-V (future)
    if args.all or args.riscv:
        source_dir = args.source_dir or args.riscv_source_dir
        if not source_dir or not source_dir.exists():
            logging.error(f"RISC-V source directory not found: {source_dir}")
            overall_success = False
        else:
            results['riscv'] = await import_riscv_data(db, source_dir)
            if not results['riscv']['success']:
                overall_success = False
    
    # Print summary
    if not args.quiet:
        print("\n" + "="*60)
        print("IMPORT SUMMARY")
        print("="*60)
        
        total_instructions = 0
        total_time = 0
        
        for isa, result in results.items():
            status = "✓" if result['success'] else "✗"
            print(f"{status} {isa.upper():<8}: ", end="")
            
            if result['success']:
                instructions = result['stats']['instructions_inserted']
                duration = result['duration_seconds']
                total_instructions += instructions
                total_time += duration
                print(f"{instructions:,} instructions in {duration:.1f}s")
            else:
                print(f"FAILED - {result['error']}")
        
        print("-" * 60)
        print(f"Total: {total_instructions:,} instructions in {total_time:.1f}s")
        print(f"Database: {args.db_path}")
        
        if overall_success:
            print("\n🎉 Import completed successfully!")
        else:
            print("\n❌ Import completed with errors")
    
    # Set exit code
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    asyncio.run(main())