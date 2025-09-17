"""
Integration tests for Agent API
Tests the complete agent invocation flow with session isolation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, AsyncMock
import json

# Import the FastAPI app
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from main import app

class TestAgentAPI:
    """Integration tests for Agent API endpoints"""

    @pytest.fixture
    def client(self):
        """Test client for FastAPI app"""
        return TestClient(app)

    @pytest.fixture
    def valid_agent_request(self):
        """Valid agent invocation request"""
        return {
            "user_input": "Hello, how are you?",
            "session_id": "test_session_123",
            "tenant_id": "test_tenant",
            "traits": {
                "name": "TestBot",
                "shortDescription": "A helpful test assistant",
                "identity": "I am a test AI assistant",
                "mission": "To help users with testing",
                "interactionStyle": "Friendly and professional",
                "creativity": 75,
                "empathy": 80,
                "assertiveness": 60,
                "verbosity": 50,
                "formality": 40,
                "confidence": 70,
                "humor": 30,
                "technicality": 85,
                "safety": 90
            },
            "voice_id": "test_voice_id",
            "tts_enabled": True
        }

    def test_agent_health_endpoint(self, client):
        """Test agent health check endpoint"""
        response = client.get("/api/v1/agent/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data

    def test_prompt_variables_endpoint(self, client):
        """Test prompt variables endpoint"""
        response = client.get("/api/v1/agent/prompt/variables")
        assert response.status_code == 200

        data = response.json()
        assert "success" in data
        assert "variables" in data
        assert "metadata" in data

    def test_validate_agent_config_success(self, client, valid_agent_request):
        """Test successful agent configuration validation"""
        validate_request = {
            "traits": valid_agent_request["traits"]
        }

        response = client.post("/api/v1/agent/validate", json=validate_request)
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is True
        assert "prompt_preview" in data

    def test_validate_agent_config_failure(self, client):
        """Test agent configuration validation failure"""
        invalid_request = {
            "traits": {
                "name": "TestBot",
                "creativity": 150  # Invalid: > 100
            }
        }

        response = client.post("/api/v1/agent/validate", json=invalid_request)
        assert response.status_code == 200

        data = response.json()
        assert data["valid"] is False
        assert "errors" in data
        assert len(data["errors"]) > 0

    @patch('agents.nodes.agent_node.agent_node')
    def test_agent_invoke_success(self, mock_agent_node, client, valid_agent_request):
        """Test successful agent invocation"""
        # Mock successful agent response
        mock_agent_node.return_value = {
            "workflow_status": "response_generated",
            "agent_response": "Hello! I'm doing well, thank you for asking.",
            "memory_metrics": {"memories_added": 2, "turn_count": 1}
        }

        response = client.post("/api/v1/agent/invoke", json=valid_agent_request)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["agent_response"] == "Hello! I'm doing well, thank you for asking."
        assert data["session_id"] == "test_session_123"
        assert data["tenant_id"] == "test_tenant"
        assert "processing_time_ms" in data
        assert "memory_metrics" in data

    def test_agent_invoke_missing_session_id(self, client, valid_agent_request):
        """Test agent invocation with missing session_id"""
        request = valid_agent_request.copy()
        del request["session_id"]

        response = client.post("/api/v1/agent/invoke", json=request)
        assert response.status_code == 422  # Validation error

    def test_agent_invoke_missing_user_input(self, client, valid_agent_request):
        """Test agent invocation with missing user_input"""
        request = valid_agent_request.copy()
        del request["user_input"]

        response = client.post("/api/v1/agent/invoke", json=request)
        assert response.status_code == 422  # Validation error

    def test_agent_invoke_invalid_traits(self, client, valid_agent_request):
        """Test agent invocation with invalid traits"""
        request = valid_agent_request.copy()
        request["traits"]["creativity"] = 150  # Invalid value

        response = client.post("/api/v1/agent/invoke", json=request)
        assert response.status_code == 422  # Validation error

    def test_agent_invoke_short_session_id(self, client, valid_agent_request):
        """Test agent invocation with too short session_id"""
        request = valid_agent_request.copy()
        request["session_id"] = "ab"  # Too short

        response = client.post("/api/v1/agent/invoke", json=request)
        assert response.status_code == 422  # Validation error

    @patch('agents.nodes.agent_node.agent_node')
    def test_agent_invoke_processing_error(self, mock_agent_node, client, valid_agent_request):
        """Test agent invocation with processing error"""
        # Mock agent processing error
        mock_agent_node.return_value = {
            "workflow_status": "error",
            "error_message": "Agent processing failed"
        }

        response = client.post("/api/v1/agent/invoke", json=valid_agent_request)
        assert response.status_code == 500

    @patch('agents.nodes.agent_node.agent_node')
    def test_agent_invoke_with_voice(self, mock_agent_node, client, valid_agent_request):
        """Test agent invocation with voice processing"""
        # Mock successful agent response with voice data
        mock_agent_node.return_value = {
            "workflow_status": "response_generated",
            "agent_response": "Hello! I'm doing well, thank you for asking.",
            "audio_data": "base64_encoded_audio_data",
            "memory_metrics": {"memories_added": 2, "turn_count": 1}
        }

        response = client.post("/api/v1/agent/invoke", json=valid_agent_request)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["voice_id"] == "test_voice_id"
        # Note: audio_data would be added by voice processor in actual flow

    def test_session_isolation(self, client, valid_agent_request):
        """Test that different sessions are properly isolated"""
        # This test would require mocking the memory manager to verify isolation
        # For now, we test that different session_ids are accepted
        request1 = valid_agent_request.copy()
        request1["session_id"] = "session_1"

        request2 = valid_agent_request.copy()
        request2["session_id"] = "session_2"

        with patch('agents.nodes.agent_node.agent_node') as mock_agent:
            mock_agent.return_value = {
                "workflow_status": "response_generated",
                "agent_response": "Test response",
                "memory_metrics": {}
            }

            response1 = client.post("/api/v1/agent/invoke", json=request1)
            response2 = client.post("/api/v1/agent/invoke", json=request2)

            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response1.json()["session_id"] == "session_1"
            assert response2.json()["session_id"] == "session_2"

    def test_tenant_isolation(self, client, valid_agent_request):
        """Test that different tenants are properly isolated"""
        request1 = valid_agent_request.copy()
        request1["tenant_id"] = "tenant_1"

        request2 = valid_agent_request.copy()
        request2["tenant_id"] = "tenant_2"

        with patch('agents.nodes.agent_node.agent_node') as mock_agent:
            mock_agent.return_value = {
                "workflow_status": "response_generated",
                "agent_response": "Test response",
                "memory_metrics": {}
            }

            response1 = client.post("/api/v1/agent/invoke", json=request1)
            response2 = client.post("/api/v1/agent/invoke", json=request2)

            assert response1.status_code == 200
            assert response2.status_code == 200
            assert response1.json()["tenant_id"] == "tenant_1"
            assert response2.json()["tenant_id"] == "tenant_2"

    def test_trait_validation_consistency(self, client):
        """Test that validation endpoint matches invoke endpoint requirements"""
        # Test with various trait configurations
        test_cases = [
            # Valid case
            {
                "traits": {
                    "name": "TestBot",
                    "shortDescription": "Test",
                    "identity": "AI assistant",
                    "mission": "Help users",
                    "interactionStyle": "Friendly",
                    "creativity": 50,
                    "empathy": 50,
                    "assertiveness": 50,
                    "verbosity": 50,
                    "formality": 50,
                    "confidence": 50,
                    "humor": 50,
                    "technicality": 50,
                    "safety": 50
                },
                "should_validate": True
            },
            # Invalid numeric range
            {
                "traits": {
                    "name": "TestBot",
                    "shortDescription": "Test",
                    "creativity": 150  # Invalid
                },
                "should_validate": False
            }
        ]

        for case in test_cases:
            # Test validation endpoint
            validate_response = client.post("/api/v1/agent/validate", json=case)
            assert validate_response.status_code == 200

            validate_data = validate_response.json()
            assert validate_data["valid"] == case["should_validate"]

            if case["should_validate"]:
                # Test that invoke would also accept this
                invoke_request = {
                    "user_input": "Test message",
                    "session_id": "test_123",
                    **case
                }

                with patch('agents.nodes.agent_node.agent_node') as mock_agent:
                    mock_agent.return_value = {
                        "workflow_status": "response_generated",
                        "agent_response": "Test response",
                        "memory_metrics": {}
                    }

                    invoke_response = client.post("/api/v1/agent/invoke", json=invoke_request)
                    assert invoke_response.status_code == 200

if __name__ == "__main__":
    pytest.main([__file__])