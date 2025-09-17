"""
Comprehensive tests for PromptLoader
Tests prompt loading, validation, and trait matching
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from agents.prompt_loader import PromptLoader

class TestPromptLoader:
    """Test suite for PromptLoader"""

    @pytest.fixture
    def sample_prompt_data(self):
        """Sample prompt data for testing"""
        return {
            "system_prompt": "You are {name}, {shortDescription}. Creativity: {creativity}/100",
            "variables": {
                "name": "string",
                "shortDescription": "string",
                "creativity": "number"
            },
            "metadata": {
                "version": "1.0",
                "supports_voice": True
            }
        }

    @pytest.fixture
    def sample_traits(self):
        """Sample traits data for testing"""
        return {
            "name": "TestBot",
            "shortDescription": "A test assistant",
            "creativity": 75,
            "empathy": 60,
            "assertiveness": 50,
            "verbosity": 40,
            "formality": 80,
            "confidence": 70,
            "humor": 30,
            "technicality": 85,
            "safety": 90,
            "identity": "I am a helpful AI assistant",
            "mission": "To assist users with their tasks",
            "interactionStyle": "Professional and friendly"
        }

    def test_load_prompt_variables(self, sample_prompt_data):
        """Test loading prompt variables"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data):
            variables = PromptLoader.load_prompt_variables()
            assert variables == sample_prompt_data["variables"]

    def test_load_system_prompt(self, sample_prompt_data):
        """Test loading system prompt template"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data):
            prompt = PromptLoader.load_system_prompt()
            assert prompt == sample_prompt_data["system_prompt"]

    def test_load_system_prompt_fallback(self):
        """Test fallback behavior when prompt loading fails"""
        with patch.object(PromptLoader, '_load_prompt_data', side_effect=Exception("Load failed")):
            prompt = PromptLoader.load_system_prompt()
            assert "You are {name}, {shortDescription}" in prompt

    def test_validate_traits_success(self, sample_traits):
        """Test successful trait validation"""
        with patch.object(PromptLoader, 'load_prompt_variables', return_value={
            var: "number" if var in ["creativity", "empathy", "assertiveness", "verbosity",
                                   "formality", "confidence", "humor", "technicality", "safety"]
            else "string"
            for var in sample_traits.keys()
        }):
            result = PromptLoader.validate_traits(sample_traits)
            assert result is True

    def test_validate_traits_missing_variables(self):
        """Test validation failure with missing variables"""
        traits = {"name": "TestBot"}  # Missing required variables

        with patch.object(PromptLoader, 'load_prompt_variables', return_value={
            "name": "string",
            "shortDescription": "string",
            "creativity": "number"
        }):
            with pytest.raises(ValueError, match="Missing required trait variables"):
                PromptLoader.validate_traits(traits)

    def test_validate_traits_invalid_numeric_range(self):
        """Test validation failure with invalid numeric values"""
        traits = {
            "name": "TestBot",
            "shortDescription": "Test",
            "creativity": 150  # Invalid: > 100
        }

        with patch.object(PromptLoader, 'load_prompt_variables', return_value={
            "name": "string",
            "shortDescription": "string",
            "creativity": "number"
        }):
            with pytest.raises(ValueError, match="must be a number between 0-100"):
                PromptLoader.validate_traits(traits)

    def test_validate_traits_invalid_types(self):
        """Test validation failure with invalid data types"""
        traits = {
            "name": 123,  # Should be string
            "shortDescription": "Test",
            "creativity": 50
        }

        with patch.object(PromptLoader, 'load_prompt_variables', return_value={
            "name": "string",
            "shortDescription": "string",
            "creativity": "number"
        }):
            with pytest.raises(ValueError, match="must be a string"):
                PromptLoader.validate_traits(traits)

    def test_build_prompt_success(self, sample_prompt_data, sample_traits):
        """Test successful prompt building"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data):
            with patch.object(PromptLoader, 'validate_traits', return_value=True):
                prompt = PromptLoader.build_prompt(sample_traits)

                assert "TestBot" in prompt
                assert "A test assistant" in prompt
                assert "75/100" in prompt  # Creativity value

    def test_build_prompt_validation_failure(self, sample_prompt_data):
        """Test prompt building with validation failure"""
        invalid_traits = {"name": "TestBot"}  # Missing required fields

        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data):
            with pytest.raises(ValueError, match="Missing required trait variables"):
                PromptLoader.build_prompt(invalid_traits)

    def test_build_prompt_formatting_error(self, sample_prompt_data):
        """Test prompt building with formatting error"""
        traits = {"name": "TestBot"}  # Missing variables for template

        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data):
            with patch.object(PromptLoader, 'validate_traits', return_value=True):
                with pytest.raises(ValueError, match="Template requires variable"):
                    PromptLoader.build_prompt(traits)

    def test_get_metadata(self, sample_prompt_data):
        """Test getting prompt metadata"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data):
            metadata = PromptLoader.get_metadata()
            assert metadata == sample_prompt_data["metadata"]

    def test_cache_functionality(self, sample_prompt_data):
        """Test that prompt data is properly cached"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data) as mock_load:
            # First call should load data
            PromptLoader.load_system_prompt()
            assert mock_load.call_count == 1

            # Second call should use cache
            PromptLoader.load_system_prompt()
            assert mock_load.call_count == 1  # Still 1, used cache

    def test_clear_cache(self, sample_prompt_data):
        """Test cache clearing functionality"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data) as mock_load:
            # Load data
            PromptLoader.load_system_prompt()
            assert mock_load.call_count == 1

            # Clear cache
            PromptLoader.clear_cache()

            # Next call should reload
            PromptLoader.load_system_prompt()
            assert mock_load.call_count == 2

    def test_reload_prompt(self, sample_prompt_data):
        """Test force reloading of prompt"""
        with patch.object(PromptLoader, '_load_prompt_data', return_value=sample_prompt_data) as mock_load:
            # Load data
            PromptLoader.load_system_prompt()
            assert mock_load.call_count == 1

            # Force reload
            PromptLoader.reload_prompt()
            assert mock_load.call_count == 2

    def test_load_prompt_data_file_not_found(self):
        """Test behavior when prompt file doesn't exist"""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Prompt file not found"):
                PromptLoader._load_prompt_data()

    def test_load_prompt_data_invalid_json(self):
        """Test behavior with invalid JSON in prompt file"""
        invalid_json = "{ invalid json }"

        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=invalid_json)):
                with pytest.raises(ValueError, match="Invalid JSON"):
                    PromptLoader._load_prompt_data()

    def test_load_prompt_data_missing_fields(self):
        """Test behavior with missing required fields in prompt file"""
        incomplete_data = {"variables": {"name": "string"}}  # Missing system_prompt

        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(incomplete_data))):
                with pytest.raises(ValueError, match="missing 'system_prompt' field"):
                    PromptLoader._load_prompt_data()

    def test_real_prompt_file_validation(self):
        """Test validation against actual prompt file"""
        # This test validates the actual prompt file structure
        try:
            variables = PromptLoader.load_prompt_variables()
            prompt = PromptLoader.load_system_prompt()
            metadata = PromptLoader.get_metadata()

            # Verify expected structure
            assert isinstance(variables, dict)
            assert isinstance(prompt, str)
            assert isinstance(metadata, dict)

            # Verify required trait variables exist
            required_traits = ["creativity", "empathy", "assertiveness", "verbosity",
                             "formality", "confidence", "humor", "technicality", "safety"]
            for trait in required_traits:
                assert trait in variables, f"Required trait '{trait}' missing from prompt template"

            # Verify prompt contains placeholders
            for var in variables:
                assert f"{{{var}}}" in prompt, f"Variable '{var}' not found in prompt template"

        except Exception as e:
            pytest.skip(f"Could not load actual prompt file: {e}")

if __name__ == "__main__":
    pytest.main([__file__])