"""Database schema and models for ISA instruction data."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class OperandRecord:
    """Represents an instruction operand."""

    name: str
    type: str  # register, memory, immediate, etc.
    access: str  # r, w, rw
    size: Optional[str] = None  # operand size
    visibility: str = "EXPLICIT"  # EXPLICIT, IMPLICIT, SUPPRESSED


@dataclass
class EncodingRecord:
    """Represents instruction encoding information."""

    pattern: str  # XED pattern or encoding description
    opcode: Optional[str] = None  # base opcode bytes
    prefix: Optional[str] = None  # required prefixes
    modrm: Optional[bool] = None  # uses ModR/M byte
    sib: Optional[bool] = None  # uses SIB byte
    displacement: Optional[str] = None  # displacement info
    immediate: Optional[str] = None  # immediate info


@dataclass
class InstructionRecord:
    """Represents a complete instruction record."""

    id: Optional[int] = None
    isa: str = ""
    mnemonic: str = ""
    variant: Optional[str] = None
    category: str = ""
    extension: str = ""
    isa_set: str = ""
    description: str = ""
    syntax: str = ""

    # Serialized as JSON in database
    operands: List[OperandRecord] = None
    encoding: Optional[EncodingRecord] = None
    flags_affected: List[str] = None
    cpuid_features: List[str] = None

    # Metadata
    cpl: Optional[int] = None  # privilege level
    attributes: List[str] = None
    added_version: Optional[str] = None
    deprecated: bool = False

    def __post_init__(self):
        if self.operands is None:
            self.operands = []
        if self.flags_affected is None:
            self.flags_affected = []
        if self.cpuid_features is None:
            self.cpuid_features = []
        if self.attributes is None:
            self.attributes = []


@dataclass
class ArchitectureRecord:
    """Represents architecture metadata."""

    id: Optional[int] = None
    isa_name: str = ""
    word_size: int = 0
    endianness: str = ""
    description: str = ""
    machine_mode: str = ""


@dataclass
class RegisterRecord:
    """Represents a register definition."""

    id: Optional[int] = None
    architecture_id: int = 0
    register_name: str = ""
    register_class: str = ""
    width_bits: int = 0
    encoding_id: Optional[int] = None
    is_main_register: bool = True


@dataclass
class AddressingModeRecord:
    """Represents an addressing mode."""

    id: Optional[int] = None
    architecture_id: int = 0
    mode_name: str = ""
    description: str = ""
    example_syntax: str = ""


class ISADatabase:
    """Database manager for ISA instruction data."""

    def __init__(self, db_path: str = "isa_docs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize_database(self):
        """Create database schema."""
        with self.get_connection() as conn:
            # Main instructions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isa TEXT NOT NULL,
                    mnemonic TEXT NOT NULL,
                    variant TEXT,
                    category TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    isa_set TEXT NOT NULL,

                    -- Denormalized for fast lookups
                    description TEXT,
                    syntax TEXT,

                    -- Structured data as JSON
                    operands_json TEXT,
                    encoding_json TEXT,
                    flags_affected_json TEXT,
                    cpuid_features_json TEXT,
                    attributes_json TEXT,

                    -- Metadata
                    cpl INTEGER,
                    added_version TEXT,
                    deprecated BOOLEAN DEFAULT FALSE,

                    -- Constraints
                    UNIQUE(isa, mnemonic, variant)
                )
            """)

            # Indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instructions_isa
                ON instructions(isa)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instructions_mnemonic
                ON instructions(mnemonic)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instructions_category
                ON instructions(category)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_instructions_extension
                ON instructions(extension)
            """)

            # Full-text search table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS instruction_search
                USING fts5(
                    isa, mnemonic, description, category, extension,
                    content='instructions',
                    content_rowid='id'
                )
            """)

            # Triggers to keep FTS table in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS instructions_ai
                    AFTER INSERT ON instructions
                BEGIN
                    INSERT INTO instruction_search(
                        rowid, isa, mnemonic, description, category, extension
                    )
                    VALUES (
                        new.id, new.isa, new.mnemonic, new.description,
                        new.category, new.extension
                    );
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS instructions_ad
                    AFTER DELETE ON instructions
                BEGIN
                    INSERT INTO instruction_search(
                        instruction_search, rowid, isa, mnemonic, description,
                        category, extension
                    )
                    VALUES (
                        'delete', old.id, old.isa, old.mnemonic, old.description,
                        old.category, old.extension
                    );
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS instructions_au
                    AFTER UPDATE ON instructions
                BEGIN
                    INSERT INTO instruction_search(
                        instruction_search, rowid, isa, mnemonic, description,
                        category, extension
                    )
                    VALUES (
                        'delete', old.id, old.isa, old.mnemonic, old.description,
                        old.category, old.extension
                    );
                    INSERT INTO instruction_search(
                        rowid, isa, mnemonic, description, category, extension
                    )
                    VALUES (
                        new.id, new.isa, new.mnemonic, new.description,
                        new.category, new.extension
                    );
                END
            """)

            # Import metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS import_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isa TEXT NOT NULL,
                    source_path TEXT,
                    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    instruction_count INTEGER,
                    source_version TEXT,
                    importer_version TEXT,
                    import_duration_seconds REAL,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT
                )
            """)

            # Architecture metadata tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS architectures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isa_name TEXT NOT NULL UNIQUE,
                    word_size INTEGER NOT NULL,
                    endianness TEXT NOT NULL,
                    description TEXT,
                    machine_mode TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS architecture_registers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    architecture_id INTEGER NOT NULL,
                    register_name TEXT NOT NULL,
                    register_class TEXT NOT NULL,
                    width_bits INTEGER NOT NULL,
                    encoding_id INTEGER,
                    is_main_register BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (architecture_id) REFERENCES architectures(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS architecture_addressing_modes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    architecture_id INTEGER NOT NULL,
                    mode_name TEXT NOT NULL,
                    description TEXT,
                    example_syntax TEXT,
                    FOREIGN KEY (architecture_id) REFERENCES architectures(id)
                )
            """)

            # Indexes for architecture metadata
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_architectures_isa_name
                ON architectures(isa_name)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_registers_architecture_id
                ON architecture_registers(architecture_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_addressing_modes_architecture_id
                ON architecture_addressing_modes(architecture_id)
            """)

            conn.commit()

    def insert_instruction(self, instruction: InstructionRecord) -> int:
        """Insert instruction into database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO instructions (
                    isa, mnemonic, variant, category, extension, isa_set,
                    description, syntax, operands_json, encoding_json,
                    flags_affected_json, cpuid_features_json, attributes_json,
                    cpl, added_version, deprecated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    instruction.isa,
                    instruction.mnemonic,
                    instruction.variant,
                    instruction.category,
                    instruction.extension,
                    instruction.isa_set,
                    instruction.description,
                    instruction.syntax,
                    json.dumps([asdict(op) for op in instruction.operands]),
                    json.dumps(
                        asdict(instruction.encoding) if instruction.encoding else None
                    ),
                    json.dumps(instruction.flags_affected),
                    json.dumps(instruction.cpuid_features),
                    json.dumps(instruction.attributes),
                    instruction.cpl,
                    instruction.added_version,
                    instruction.deprecated,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_instruction(
        self, isa: str, mnemonic: str, variant: Optional[str] = None
    ) -> Optional[InstructionRecord]:
        """Get instruction by ISA and mnemonic."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM instructions
                WHERE isa = ? AND mnemonic = ? AND (
                    variant = ? OR (variant IS NULL AND ? IS NULL)
                )
            """,
                (isa, mnemonic, variant, variant),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return self._row_to_instruction(row)

    def list_instructions(
        self, isa: str, limit: Optional[int] = None
    ) -> List[InstructionRecord]:
        """List all instructions for an ISA."""
        with self.get_connection() as conn:
            query = "SELECT * FROM instructions WHERE isa = ? ORDER BY mnemonic"
            params = [isa]

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = conn.execute(query, params)
            return [self._row_to_instruction(row) for row in cursor.fetchall()]

    def search_instructions(
        self, query: str, isa: Optional[str] = None, limit: int = 50
    ) -> List[InstructionRecord]:
        """Search instructions using full-text search."""
        with self.get_connection() as conn:
            if isa:
                cursor = conn.execute(
                    """
                    SELECT instructions.* FROM instruction_search
                    JOIN instructions ON instruction_search.rowid = instructions.id
                    WHERE instruction_search MATCH ? AND isa = ?
                    ORDER BY rank
                    LIMIT ?
                """,
                    (query, isa, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT instructions.* FROM instruction_search
                    JOIN instructions ON instruction_search.rowid = instructions.id
                    WHERE instruction_search MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """,
                    (query, limit),
                )

            return [self._row_to_instruction(row) for row in cursor.fetchall()]

    def get_supported_isas(self) -> List[str]:
        """Get list of supported ISAs."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT isa FROM instructions ORDER BY isa")
            return [row[0] for row in cursor.fetchall()]

    def get_instruction_count(self, isa: Optional[str] = None) -> int:
        """Get total instruction count."""
        with self.get_connection() as conn:
            if isa:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM instructions WHERE isa = ?", (isa,)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM instructions")

            return cursor.fetchone()[0]

    def record_import_metadata(
        self,
        isa: str,
        source_path: str,
        instruction_count: int,
        source_version: Optional[str] = None,
        importer_version: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> int:
        """Record import metadata."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO import_metadata (
                    isa, source_path, instruction_count, source_version,
                    importer_version, import_duration_seconds, success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    isa,
                    source_path,
                    instruction_count,
                    source_version,
                    importer_version,
                    duration_seconds,
                    success,
                    error_message,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_architecture(self, architecture: ArchitectureRecord) -> int:
        """Insert architecture metadata into database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO architectures (
                    isa_name, word_size, endianness, description, machine_mode
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    architecture.isa_name,
                    architecture.word_size,
                    architecture.endianness,
                    architecture.description,
                    architecture.machine_mode,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_register(self, register: RegisterRecord) -> int:
        """Insert register into database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO architecture_registers (
                    architecture_id, register_name, register_class, width_bits,
                    encoding_id, is_main_register
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    register.architecture_id,
                    register.register_name,
                    register.register_class,
                    register.width_bits,
                    register.encoding_id,
                    register.is_main_register,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def insert_addressing_mode(self, addressing_mode: AddressingModeRecord) -> int:
        """Insert addressing mode into database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO architecture_addressing_modes (
                    architecture_id, mode_name, description, example_syntax
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    addressing_mode.architecture_id,
                    addressing_mode.mode_name,
                    addressing_mode.description,
                    addressing_mode.example_syntax,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_architecture(self, isa_name: str) -> Optional[ArchitectureRecord]:
        """Get architecture by ISA name."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM architectures WHERE isa_name = ?", (isa_name,)
            )
            row = cursor.fetchone()
            if row:
                return ArchitectureRecord(
                    id=row["id"],
                    isa_name=row["isa_name"],
                    word_size=row["word_size"],
                    endianness=row["endianness"],
                    description=row["description"],
                    machine_mode=row["machine_mode"],
                )
            return None

    def get_architecture_registers(self, isa_name: str) -> List[RegisterRecord]:
        """Get all registers for an architecture."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT ar.* FROM architecture_registers ar
                JOIN architectures a ON ar.architecture_id = a.id
                WHERE a.isa_name = ?
                ORDER BY ar.register_class, ar.register_name
                """,
                (isa_name,),
            )

            registers = []
            for row in cursor.fetchall():
                registers.append(
                    RegisterRecord(
                        id=row["id"],
                        architecture_id=row["architecture_id"],
                        register_name=row["register_name"],
                        register_class=row["register_class"],
                        width_bits=row["width_bits"],
                        encoding_id=row["encoding_id"],
                        is_main_register=bool(row["is_main_register"]),
                    )
                )
            return registers

    def get_architecture_addressing_modes(
        self, isa_name: str
    ) -> List[AddressingModeRecord]:
        """Get all addressing modes for an architecture."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT aam.* FROM architecture_addressing_modes aam
                JOIN architectures a ON aam.architecture_id = a.id
                WHERE a.isa_name = ?
                ORDER BY aam.mode_name
                """,
                (isa_name,),
            )

            modes = []
            for row in cursor.fetchall():
                modes.append(
                    AddressingModeRecord(
                        id=row["id"],
                        architecture_id=row["architecture_id"],
                        mode_name=row["mode_name"],
                        description=row["description"],
                        example_syntax=row["example_syntax"],
                    )
                )
            return modes

    def _row_to_instruction(self, row: sqlite3.Row) -> InstructionRecord:
        """Convert database row to InstructionRecord."""
        # Parse JSON fields
        operands_data = json.loads(row["operands_json"] or "[]")
        operands = [OperandRecord(**op) for op in operands_data]

        encoding_data = json.loads(row["encoding_json"] or "null")
        encoding = EncodingRecord(**encoding_data) if encoding_data else None

        flags_affected = json.loads(row["flags_affected_json"] or "[]")
        cpuid_features = json.loads(row["cpuid_features_json"] or "[]")
        attributes = json.loads(row["attributes_json"] or "[]")

        return InstructionRecord(
            id=row["id"],
            isa=row["isa"],
            mnemonic=row["mnemonic"],
            variant=row["variant"],
            category=row["category"],
            extension=row["extension"],
            isa_set=row["isa_set"],
            description=row["description"],
            syntax=row["syntax"],
            operands=operands,
            encoding=encoding,
            flags_affected=flags_affected,
            cpuid_features=cpuid_features,
            attributes=attributes,
            cpl=row["cpl"],
            added_version=row["added_version"],
            deprecated=bool(row["deprecated"]),
        )
