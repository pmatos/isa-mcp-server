"""Unit tests for ARMImporter."""

from unittest.mock import patch

import pytest

from src.isa_mcp_server.importers.arm_importer import ARMImporter


class TestARMImporter:
    """Test cases for ARMImporter."""

    def test_init(self, temp_db):
        """Test importer initialization."""
        importer = ARMImporter(temp_db)
        assert importer.db == temp_db
        assert importer.isa_name == "aarch64"
        assert importer.importer_version == "1.0.0"
        assert hasattr(importer, "parser")
        assert not importer._arch_metadata_populated

    def test_get_source_version(self, temp_db, sample_arm_data_dir):
        """Test source version extraction."""
        importer = ARMImporter(temp_db)
        version = importer.get_source_version(sample_arm_data_dir)
        assert version == "v9Ap6-A-2025-06_rel-83"

    def test_get_source_version_error(self, temp_db, tmp_path):
        """Test source version when data is invalid."""
        importer = ARMImporter(temp_db)
        version = importer.get_source_version(tmp_path)
        assert version is None

    @pytest.mark.asyncio
    async def test_parse_sources_missing_file(self, temp_db, tmp_path):
        """Test parsing when instructions file is missing."""
        importer = ARMImporter(temp_db)
        instructions = []

        async for instruction in importer.parse_sources(tmp_path):
            instructions.append(instruction)

        assert len(instructions) == 0

    @pytest.mark.asyncio
    async def test_parse_sources_valid(self, temp_db, sample_arm_data_dir):
        """Test parsing valid ARM data."""
        importer = ARMImporter(temp_db)
        instructions = []

        async for instruction in importer.parse_sources(sample_arm_data_dir):
            instructions.append(instruction)

        # Should get at least one instruction
        assert len(instructions) > 0

        # Check instruction properties
        instruction = instructions[0]
        assert instruction.isa == "aarch64"
        assert instruction.mnemonic == "ADD"

    @pytest.mark.asyncio
    async def test_populate_architecture_metadata(self, temp_db, sample_arm_data_dir):
        """Test architecture metadata population."""
        importer = ARMImporter(temp_db)

        success = await importer.populate_architecture_metadata(sample_arm_data_dir)
        assert success
        assert importer._arch_metadata_populated

        # Check that data was inserted
        # This would require database queries to fully verify

    @pytest.mark.asyncio
    async def test_populate_architecture_metadata_error(self, temp_db, tmp_path):
        """Test architecture metadata population with database error."""
        importer = ARMImporter(temp_db)

        # Mock the database insert to raise an exception
        with patch.object(
            temp_db, "insert_architecture", side_effect=Exception("DB error")
        ):
            with patch.object(importer.logger, "error") as mock_error:
                success = await importer.populate_architecture_metadata(tmp_path)
                assert not success
                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_import_from_source_success(self, temp_db, sample_arm_data_dir):
        """Test complete import process."""
        importer = ARMImporter(temp_db)

        result = await importer.import_from_source(sample_arm_data_dir)

        assert result["success"]
        assert "duration_seconds" in result
        assert "stats" in result
        assert result["stats"]["instructions_inserted"] > 0

    @pytest.mark.asyncio
    async def test_import_from_source_skip_metadata(self, temp_db, sample_arm_data_dir):
        """Test import process skipping metadata."""
        importer = ARMImporter(temp_db)

        result = await importer.import_from_source(
            sample_arm_data_dir, skip_metadata=True
        )

        assert result["success"]
        # Should not have populated metadata
        assert not hasattr(result, "metadata_imported") or not result.get(
            "metadata_imported", False
        )
