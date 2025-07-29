"""Unit tests for the registers resource."""

import json
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch

from src.isa_mcp_server.server import create_mcp_server
from src.isa_mcp_server.isa_database import RegisterRecord


class TestRegistersResource:
    """Test cases for the /architectures/{arch}/registers resource."""

    @pytest.fixture
    def mock_server(self):
        """Create server with mocked database."""
        with patch('src.isa_mcp_server.server.ISADatabase') as mock_db_class:
            mock_db = Mock()
            mock_db_class.return_value = mock_db
            mock_db.initialize_database.return_value = None
            
            server = create_mcp_server()
            server._db = mock_db
            
            return server, mock_db

    @pytest.fixture
    def sample_registers(self):
        """Sample register data for testing."""
        return [
            RegisterRecord(
                id=1,
                architecture_id=1,
                register_name="RAX",
                register_class="gpr",
                width_bits=64,
                encoding_id=0,
                is_main_register=True,
                parent_register_id=None,
                aliases_json='["EAX", "AX", "AL", "AH"]',
                calling_convention_preserved=False,
                register_purpose="accumulator"
            ),
            RegisterRecord(
                id=2,
                architecture_id=1,
                register_name="EAX",
                register_class="gpr",
                width_bits=32,
                encoding_id=0,
                is_main_register=False,
                parent_register_id=1,
                aliases_json='["AX", "AL", "AH"]',
                calling_convention_preserved=False,
                register_purpose=None
            ),
            RegisterRecord(
                id=3,
                architecture_id=1,
                register_name="XMM0",
                register_class="simd",
                width_bits=128,
                encoding_id=0,
                is_main_register=True,
                parent_register_id=None,
                aliases_json='[]',
                calling_convention_preserved=None,
                register_purpose="vector"
            ),
            RegisterRecord(
                id=4,
                architecture_id=1,
                register_name="RBX",
                register_class="gpr",
                width_bits=64,
                encoding_id=3,
                is_main_register=True,
                parent_register_id=None,
                aliases_json='["EBX", "BX", "BL", "BH"]',
                calling_convention_preserved=True,
                register_purpose=None
            )
        ]

    @pytest.mark.asyncio
    async def test_get_registers_success(self, mock_server, sample_registers):
        """Test successful register retrieval with complete data."""
        server, mock_db = mock_server
        
        # Mock database responses
        mock_db.get_supported_isas.return_value = ["x86_64", "x86_32", "aarch64"]
        mock_db.get_architecture_registers_with_aliases.return_value = sample_registers
        
        # Get resource template and call with parameters
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call the resource function
        result = await template.fn("x86_64")
        
        # Parse and verify JSON response
        response = json.loads(result)
        assert "registers" in response
        assert isinstance(response["registers"], list)
        assert len(response["registers"]) == 4
        
        # Verify register structure and sorting (by type, then name)
        registers = response["registers"]
        
        # Find and check RAX register (main register)
        rax = next(r for r in registers if r["name"] == "RAX")
        assert rax["type"] == "general-purpose"
        assert rax["width_bits"] == 64
        assert rax["is_main_register"] is True
        assert rax["aliases"] == ["EAX", "AX", "AL", "AH"]
        assert rax["calling_convention"] == "volatile"
        assert rax["purpose"] == "accumulator"
        assert rax["encoding_id"] == 0
        assert "parent_register" not in rax
        
        # Check sub-register (EAX)
        eax = next(r for r in registers if r["name"] == "EAX")
        assert eax["type"] == "general-purpose"
        assert eax["width_bits"] == 32
        assert eax["is_main_register"] is False
        assert eax["parent_register"] == "RAX"
        assert eax["calling_convention"] == "volatile"
        
        # Check preserved register (RBX)
        rbx = next(r for r in registers if r["name"] == "RBX")
        assert rbx["calling_convention"] == "preserved"
        
        # Check vector register (XMM0)
        xmm0 = next(r for r in registers if r["name"] == "XMM0")
        assert xmm0["type"] == "vector"
        assert xmm0["width_bits"] == 128
        assert xmm0["aliases"] == []
        assert xmm0["calling_convention"] is None
        assert xmm0["purpose"] == "vector"

    @pytest.mark.asyncio
    async def test_get_registers_architecture_not_found(self, mock_server):
        """Test handling of unsupported architecture."""
        server, mock_db = mock_server
        
        # Mock database to return supported architectures without 'unsupported'
        mock_db.get_supported_isas.return_value = ["x86_64", "x86_32", "aarch64"]
        
        # Get resource template
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call with unsupported architecture
        result = await template.fn("unsupported")
        
        # Verify error response
        response = json.loads(result)
        assert "error" in response
        assert "Architecture 'unsupported' not found" in response["error"]

    @pytest.mark.asyncio
    async def test_get_registers_no_registers_found(self, mock_server):
        """Test handling when no registers are found for architecture."""
        server, mock_db = mock_server
        
        # Mock database responses
        mock_db.get_supported_isas.return_value = ["x86_64", "x86_32", "aarch64"]
        mock_db.get_architecture_registers_with_aliases.return_value = []
        
        # Get resource template
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call the resource function
        result = await template.fn("x86_64")
        
        # Verify empty response
        response = json.loads(result)
        assert "registers" in response
        assert response["registers"] == []

    @pytest.mark.asyncio
    async def test_get_registers_database_error(self, mock_server):
        """Test handling of database errors."""
        server, mock_db = mock_server
        
        # Mock database to raise exception
        mock_db.get_supported_isas.side_effect = Exception("Database connection failed")
        
        # Get resource template
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call the resource function
        result = await template.fn("x86_64")
        
        # Verify error response
        response = json.loads(result)
        assert "error" in response
        assert "Error accessing registers for 'x86_64'" in response["error"]

    @pytest.mark.asyncio
    async def test_get_registers_invalid_aliases_json(self, mock_server):
        """Test handling of invalid JSON in aliases field."""
        server, mock_db = mock_server
        
        # Create register with invalid JSON
        invalid_register = RegisterRecord(
            id=1,
            architecture_id=1,
            register_name="RAX",
            register_class="gpr",
            width_bits=64,
            encoding_id=0,
            is_main_register=True,
            parent_register_id=None,
            aliases_json='invalid json',  # Invalid JSON
            calling_convention_preserved=False,
            register_purpose=None
        )
        
        # Mock database responses
        mock_db.get_supported_isas.return_value = ["x86_64"]
        mock_db.get_architecture_registers_with_aliases.return_value = [invalid_register]
        
        # Get resource template
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call the resource function
        result = await template.fn("x86_64")
        
        # Should handle gracefully with empty aliases
        response = json.loads(result)
        assert "registers" in response
        assert len(response["registers"]) == 1
        assert response["registers"][0]["aliases"] == []

    @pytest.mark.asyncio
    async def test_get_registers_aarch64(self, mock_server):
        """Test register retrieval for AArch64 architecture."""
        server, mock_db = mock_server
        
        # Create AArch64 registers
        aarch64_registers = [
            RegisterRecord(
                id=1,
                architecture_id=2,
                register_name="X0",
                register_class="gpr64",
                width_bits=64,
                encoding_id=0,
                is_main_register=True,
                parent_register_id=None,
                aliases_json='["W0"]',
                calling_convention_preserved=False,
                register_purpose=None
            ),
            RegisterRecord(
                id=2,
                architecture_id=2,
                register_name="X19",
                register_class="gpr64",
                width_bits=64,
                encoding_id=19,
                is_main_register=True,
                parent_register_id=None,
                aliases_json='["W19"]',
                calling_convention_preserved=True,
                register_purpose=None
            )
        ]
        
        # Mock database responses
        mock_db.get_supported_isas.return_value = ["aarch64"]
        mock_db.get_architecture_registers_with_aliases.return_value = aarch64_registers
        
        # Get resource template
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call the resource function
        result = await template.fn("aarch64")
        
        # Verify AArch64-specific handling
        response = json.loads(result)
        assert "registers" in response
        assert len(response["registers"]) == 2
        
        # Check register types are mapped correctly
        x0 = next(r for r in response["registers"] if r["name"] == "X0")
        assert x0["type"] == "general-purpose"  # gpr64 -> general-purpose
        assert x0["calling_convention"] == "volatile"
        
        x19 = next(r for r in response["registers"] if r["name"] == "X19") 
        assert x19["calling_convention"] == "preserved"

    @pytest.mark.asyncio
    async def test_get_registers_register_type_mapping(self, mock_server):
        """Test register type mapping for different register classes."""
        server, mock_db = mock_server
        
        # Create registers with different classes
        diverse_registers = [
            RegisterRecord(
                id=1, architecture_id=1, register_name="RAX", register_class="gpr",
                width_bits=64, encoding_id=0, is_main_register=True,
                parent_register_id=None, aliases_json='[]',
                calling_convention_preserved=False, register_purpose=None
            ),
            RegisterRecord(
                id=2, architecture_id=1, register_name="XMM0", register_class="simd", 
                width_bits=128, encoding_id=0, is_main_register=True,
                parent_register_id=None, aliases_json='[]',
                calling_convention_preserved=None, register_purpose=None
            ),
            RegisterRecord(
                id=3, architecture_id=1, register_name="ST0", register_class="x87",
                width_bits=80, encoding_id=0, is_main_register=True,
                parent_register_id=None, aliases_json='[]',
                calling_convention_preserved=None, register_purpose=None
            ),
            RegisterRecord(
                id=4, architecture_id=1, register_name="EFLAGS", register_class="flags",
                width_bits=32, encoding_id=None, is_main_register=True,
                parent_register_id=None, aliases_json='[]',
                calling_convention_preserved=None, register_purpose=None
            ),
            RegisterRecord(
                id=5, architecture_id=1, register_name="UNKNOWN_REG", register_class="unknown",
                width_bits=32, encoding_id=None, is_main_register=True,
                parent_register_id=None, aliases_json='[]',
                calling_convention_preserved=None, register_purpose=None
            )
        ]
        
        # Mock database responses
        mock_db.get_supported_isas.return_value = ["x86_64"]
        mock_db.get_architecture_registers_with_aliases.return_value = diverse_registers
        
        # Get resource template
        templates = await server.get_resource_templates()
        template = templates["isa://architectures/{arch}/registers"]
        
        # Call the resource function
        result = await template.fn("x86_64")
        
        # Verify type mappings
        response = json.loads(result)
        registers = response["registers"]
        
        type_map = {r["name"]: r["type"] for r in registers}
        assert type_map["RAX"] == "general-purpose"
        assert type_map["XMM0"] == "vector"
        assert type_map["ST0"] == "floating-point"
        assert type_map["EFLAGS"] == "flags"
        assert type_map["UNKNOWN_REG"] == "special-purpose"  # fallback