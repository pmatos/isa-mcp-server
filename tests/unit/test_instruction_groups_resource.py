"""Unit tests for the instruction groups resource."""

import json
import pytest
from unittest.mock import patch

from src.isa_mcp_server.server import create_mcp_server


class TestInstructionGroupsResource:
    """Test cases for the isa://architectures/{arch}/instruction-groups resource."""

    @pytest.mark.asyncio
    async def test_instruction_groups_success(self, temp_db):
        """Test successful instruction groups listing with JSON response."""
        # Add test instruction data with different categories
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES 
                    ('x86_64', 'ADD', 'ARITH', 'BASE', 'I86', 'Add integers', 'ADD dst, src'),
                    ('x86_64', 'SUB', 'ARITH', 'BASE', 'I86', 'Subtract integers', 'SUB dst, src'),
                    ('x86_64', 'MUL', 'ARITH', 'BASE', 'I86', 'Multiply', 'MUL src'),
                    ('x86_64', 'JMP', 'BRANCH', 'BASE', 'I86', 'Jump', 'JMP target'),
                    ('x86_64', 'CALL', 'BRANCH', 'BASE', 'I86', 'Call procedure', 'CALL target'),
                    ('x86_64', 'MOV', 'DATAXFER', 'BASE', 'I86', 'Move data', 'MOV dst, src'),
                    ('x86_64', 'MOVAPS', 'SIMD', 'SSE', 'SSE', 'Move aligned packed singles', 'MOVAPS dst, src'),
                    ('x86_64', 'ADDPS', 'SIMD', 'SSE', 'SSE', 'Add packed singles', 'ADDPS dst, src')
            """)
            conn.commit()
        
        # Create server with our test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Get the resource template and call it directly (simulating MCP client)
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/instruction-groups"]
        result = await template.fn("x86_64")
        
        # Parse and verify JSON response
        data = json.loads(result)
        assert "groups" in data
        assert isinstance(data["groups"], dict)
        
        # Check expected categories
        expected_categories = {"arith", "branch", "dataxfer", "simd"}
        assert set(data["groups"].keys()) == expected_categories
        
        # Check specific instruction groupings
        assert "ADD" in data["groups"]["arith"]
        assert "SUB" in data["groups"]["arith"]
        assert "MUL" in data["groups"]["arith"]
        assert "JMP" in data["groups"]["branch"]
        assert "CALL" in data["groups"]["branch"]
        assert "MOV" in data["groups"]["dataxfer"]
        assert "MOVAPS" in data["groups"]["simd"]
        assert "ADDPS" in data["groups"]["simd"]
        
        # Check that instructions are sorted within groups
        assert data["groups"]["arith"] == ["ADD", "MUL", "SUB"]
        assert data["groups"]["branch"] == ["CALL", "JMP"]

    @pytest.mark.asyncio
    async def test_instruction_groups_architecture_not_found(self, temp_db):
        """Test instruction groups for non-existent architecture."""
        # Create server with empty test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Call the resource for non-existent architecture
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/instruction-groups"]
        result = await template.fn("nonexistent")
        
        # Parse and verify error JSON response
        data = json.loads(result)
        assert "error" in data
        assert "Architecture 'nonexistent' not found" in data["error"]

    @pytest.mark.asyncio
    async def test_instruction_groups_no_instructions(self, temp_db):
        """Test instruction groups when architecture exists but has no instructions."""
        # Add an instruction for different architecture to make it exist in supported_isas
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES ('other_arch', 'TEST', 'TEST', 'BASE', 'TEST', 'Test instruction', 'TEST')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Mock to make x86_64 appear as supported but with no instructions
        with patch.object(server._db, 'get_supported_isas', return_value=['x86_64']), \
             patch.object(server._db, 'list_instructions', return_value=[]):
            templates = await server.get_resource_templates()
            template = templates["isa://architectures/{arch}/instruction-groups"]
            result = await template.fn("x86_64")
            
            # Parse and verify JSON response
            data = json.loads(result)
            assert "groups" in data
            assert isinstance(data["groups"], dict)
            assert len(data["groups"]) == 0

    @pytest.mark.asyncio
    async def test_instruction_groups_database_error(self, temp_db):
        """Test instruction groups when database throws an error."""
        # Add one instruction to make architecture exist
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES ('x86_64', 'MOV', 'DATAXFER', 'BASE', 'I86', 'Move data', 'MOV dst, src')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Mock the database to throw an error
        with patch.object(server._db, 'list_instructions', side_effect=Exception("Database connection failed")):
            templates = await server.get_resource_templates()
            template = templates["isa://architectures/{arch}/instruction-groups"]
            result = await template.fn("x86_64")
            
            # Parse and verify error JSON response
            data = json.loads(result)
            assert "error" in data
            assert "Database connection failed" in data["error"]

    @pytest.mark.asyncio
    async def test_instruction_groups_duplicate_mnemonics(self, temp_db):
        """Test that duplicate mnemonics in same category are handled correctly."""
        # Add test instructions with duplicate mnemonics in same category
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES 
                    ('x86_64', 'ADD', 'ARITH', 'BASE', 'I86', 'Add integers', 'ADD dst, src'),
                    ('x86_64', 'ADD', 'ARITH', 'BASE', 'I86', 'Add integers variant', 'ADD dst, src, imm'),
                    ('x86_64', 'SUB', 'ARITH', 'BASE', 'I86', 'Subtract integers', 'SUB dst, src')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Get the resource template and call it directly (simulating MCP client)
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/instruction-groups"]
        result = await template.fn("x86_64")
        
        # Parse and verify JSON response
        data = json.loads(result)
        assert "groups" in data
        assert "arith" in data["groups"]
        
        # Should only have unique mnemonics
        assert data["groups"]["arith"] == ["ADD", "SUB"]
        assert data["groups"]["arith"].count("ADD") == 1

    @pytest.mark.asyncio
    async def test_instruction_groups_case_normalization(self, temp_db):
        """Test that category names are normalized to lowercase."""
        # Add test instructions with mixed case categories
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES 
                    ('x86_64', 'ADD', 'ARITH', 'BASE', 'I86', 'Add integers', 'ADD dst, src'),
                    ('x86_64', 'SUB', 'Arith', 'BASE', 'I86', 'Subtract integers', 'SUB dst, src'),
                    ('x86_64', 'MUL', 'ARITHMETIC', 'BASE', 'I86', 'Multiply', 'MUL src')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Get the resource template and call it directly (simulating MCP client)
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/instruction-groups"]
        result = await template.fn("x86_64")
        
        # Parse and verify JSON response
        data = json.loads(result)
        assert "groups" in data
        
        # All should be grouped under lowercase categories
        expected_groups = {"arith", "arithmetic"}
        assert set(data["groups"].keys()) == expected_groups

    @pytest.mark.asyncio
    async def test_json_response_format(self, temp_db):
        """Test that the response is valid JSON with correct structure."""
        # Add one instruction to create a group
        with temp_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO instructions (isa, mnemonic, category, extension, isa_set, description, syntax)
                VALUES ('test_arch', 'TEST', 'TEST_CAT', 'BASE', 'TEST', 'Test instruction', 'TEST')
            """)
            conn.commit()
        
        # Create server with test database
        server = create_mcp_server(str(temp_db.db_path))
        
        # Call the resource
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/instruction-groups"]
        result = await template.fn("test_arch")
        
        # Verify it's valid JSON
        data = json.loads(result)  # Should not raise exception
        
        # Verify structure
        assert isinstance(data, dict)
        assert "groups" in data
        assert isinstance(data["groups"], dict)
        assert "test_cat" in data["groups"]
        assert isinstance(data["groups"]["test_cat"], list)
        assert data["groups"]["test_cat"] == ["TEST"]