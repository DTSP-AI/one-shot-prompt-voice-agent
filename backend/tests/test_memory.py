#!/usr/bin/env python3
"""
Quick test script for streamlined memory_manager.py
"""

import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from OneShotVoiceAgent.backend.memory.memory_manager import MemoryManager, build_context_prompt

async def test_memory_manager():
    """Test the streamlined memory manager"""
    print("Testing MemoryManager...")

    # Create memory manager for test agent
    memory = MemoryManager("test_agent")

    # Test adding messages
    print("\n1. Adding messages to memory...")
    user_msg = HumanMessage(content="I prefer coffee over tea")
    ai_msg = AIMessage(content="I'll remember that you prefer coffee!")

    memory.add_memory(user_msg)
    memory.add_memory(ai_msg)

    print(f"Turn count: {memory.turn_count}")
    print(f"STM size: {len(memory.stm.chat_memory.messages)}")

    # Test memory retrieval
    print("\n2. Testing memory retrieval...")
    context = memory.get_memory_context("What drinks do I like?")

    print(f"Recent context:\n{context['recent_context']}")
    print(f"Persistent context:\n{context['persistent_context']}")
    print(f"Retrieval time: {context['retrieval_ms']:.2f}ms")

    # Test prompt building
    print("\n3. Testing prompt building...")
    agent_config = {
        "payload": {
            "name": "TestBot",
            "shortDescription": "A helpful assistant",
            "traits": {"verbosity": 70}
        }
    }

    prompt = build_context_prompt(
        agent_config=agent_config,
        memory_context=context,
        current_query="What should I drink?"
    )

    print(f"Generated prompt:\n{prompt}")

    # Test metrics
    print("\n4. Testing metrics...")
    metrics = memory.get_metrics()
    print(f"Metrics: {metrics}")

    # Test feedback
    print("\n5. Testing feedback...")
    memory.add_feedback("Coffee recommendation", 0.9)

    print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_memory_manager())