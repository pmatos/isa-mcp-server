"""Unit tests for the architectures resource."""

import json
import pytest
from unittest.mock import patch

from src.isa_mcp_server.server import create_mcp_server
from src.isa_mcp_server.isa_database import InstructionRecord


class TestArchitecturesResource:
    """Test cases for the isa://architectures resource."""

    @pytest.mark.asyncio
    async def test_list_architectures_success(self, temp_db):
        """Test successful architectures listing with JSON response."""
        # Add some test instruction data (since get_supported_isas reads from instructions table)
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES 
                    ('x86_64', 'MOV', 'DATAXFER', 'BASE', 'I86', 'Move data', 'MOV dst, src'),
                    ('aarch64', 'ADD', 'ARITH', 'BASE', 'A64', 'Add numbers', 'ADD dst, src1, src2'),
                    ('x86_32', 'JMP', 'BRANCH', 'BASE', 'I86', 'Jump', 'JMP target')
            """)
            conn.commit()
        
        # Create server with our test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Get the resource handler by calling the resource directly
        resource = await server.get_resource("isa://architectures")
        result = await resource.read()
        
        # Parse and verify JSON response
        data = json.loads(result)
        assert "architectures" in data
        assert isinstance(data["architectures"], list)
        assert len(data["architectures"]) == 3
        
        # Should be sorted
        expected_archs = ["aarch64", "x86_32", "x86_64"]
        assert data["architectures"] == expected_archs

    @pytest.mark.asyncio
    async def test_list_architectures_empty_database(self, temp_db):
        """Test architectures listing when database is empty."""
        # Create server with empty test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Call the resource
        resource = await server.get_resource("isa://architectures")
        result = await resource.read()
        
        # Parse and verify JSON response
        data = json.loads(result)
        assert "architectures" in data
        assert isinstance(data["architectures"], list)
        assert len(data["architectures"]) == 0

    @pytest.mark.asyncio
    async def test_list_architectures_database_error(self, temp_db):
        """Test architectures listing when database throws an error."""
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Mock the database to throw an error
        with patch.object(server._db, 'get_supported_isas', side_effect=Exception("Database connection failed")):
            resource = await server.get_resource("isa://architectures")
            result = await resource.read()
            
            # Parse and verify error JSON response
            data = json.loads(result)
            assert "error" in data
            assert "Database connection failed" in data["error"]

    @pytest.mark.asyncio
    async def test_json_response_format(self, temp_db):
        """Test that the response is valid JSON with correct structure."""
        # Add one instruction to create an architecture
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES ('test_arch', 'TEST', 'TEST', 'BASE', 'TEST', 'Test instruction', 'TEST')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Call the resource
        resource = await server.get_resource("isa://architectures")
        result = await resource.read()
        
        # Verify it's valid JSON
        data = json.loads(result)  # Should not raise exception
        
        # Verify structure
        assert isinstance(data, dict)
        assert "architectures" in data
        assert isinstance(data["architectures"], list)
        assert data["architectures"] == ["test_arch"]

    @pytest.mark.asyncio
    async def test_architectures_are_sorted(self, temp_db):
        """Test that architectures are returned in sorted order."""
        # Add instructions in non-alphabetical order
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES 
                    ('z_arch', 'Z_INST', 'TEST', 'BASE', 'Z', 'Z instruction', 'Z_INST'),
                    ('a_arch', 'A_INST', 'TEST', 'BASE', 'A', 'A instruction', 'A_INST'),
                    ('m_arch', 'M_INST', 'TEST', 'BASE', 'M', 'M instruction', 'M_INST')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Call the resource
        resource = await server.get_resource("isa://architectures")
        result = await resource.read()
        
        # Parse and verify sorting
        data = json.loads(result)
        expected_order = ["a_arch", "m_arch", "z_arch"]
        assert data["architectures"] == expected_order