#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.nodes.agent_node import agent_node

async def test_agent_node_directly():
    """Test the agent_node function directly to see if it works"""
    
    test_state = {
        "user_input": "Hello test",
        "session_id": "test-session-123",
        "tenant_id": "default",
        "traits": {
            "name": "TestBot",
            "shortDescription": "Test assistant",
            "identity": "I am an AI assistant",
            "mission": "To help users",
            "interactionStyle": "Friendly",
            "creativity": 75,
            "empathy": 80,
            "assertiveness": 60,
            "verbosity": 50,
            "formality": 40,
            "confidence": 70,
            "humor": 35,
            "technicality": 65,
            "safety": 90
        },
        "model": "gpt-4",
        "agent_id": "test-agent",
        "voice_id": "test-voice",
        "tts_enabled": False
    }
    
    print("🧬 Testing agent_node directly...")
    print(f"Input state keys: {list(test_state.keys())}")
    
    try:
        result = await agent_node(test_state)
        print(f"🧬 SUCCESS: agent_node returned: {result}")
        print(f"🧬 Agent response: '{result.get('agent_response', 'NO RESPONSE')}'")
        return result
    except Exception as e:
        print(f"🧬 ERROR: agent_node failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_agent_node_directly())
