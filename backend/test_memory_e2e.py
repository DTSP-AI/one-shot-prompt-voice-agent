#!/usr/bin/env python3
"""
E2E Memory Test Suite for OneShotVoiceAgent with Mem0 Integration
Tests conversation threading, memory persistence, and recall functionality

Usage:
    python test_memory_e2e.py

This will test:
1. Memory initialization and Mem0 connection
2. Short-term memory (within conversation)
3. Long-term memory (across sessions)
4. Context retrieval and recall
5. Tenant/agent isolation
6. Memory performance and threading
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from memory.memory_manager import MemoryManager
from agents.nodes.agent_node import agent_node
from core.config import settings

class MemoryE2ETest:
    def __init__(self):
        self.test_results = []
        self.tenant_id = "test-tenant"
        self.agent_id = "rick-sanchez"
        self.session_id = f"e2e-test-{int(time.time())}"

        print("*** OneShotVoiceAgent E2E Memory Test Suite ***")
        print("="*60)
        print(f"Session ID: {self.session_id}")
        print(f"Tenant ID: {self.tenant_id}")
        print(f"Agent ID: {self.agent_id}")
        print("")

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")

        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def test_memory_initialization(self) -> bool:
        """Test 1: Memory Manager Initialization"""
        try:
            memory = MemoryManager(self.tenant_id, self.agent_id)

            # Check namespace isolation
            expected_namespace = f"{self.tenant_id}:{self.agent_id}"
            if memory.namespace != expected_namespace:
                self.log_test("Memory Initialization", False, f"Namespace mismatch: {memory.namespace}")
                return False

            # Check Mem0 availability
            mem0_status = "Available" if memory.persistent else "Not available"

            self.log_test("Memory Initialization", True, f"Namespace: {memory.namespace}, Mem0: {mem0_status}")
            return True

        except Exception as e:
            self.log_test("Memory Initialization", False, f"Error: {e}")
            return False

    def test_short_term_memory(self) -> bool:
        """Test 2: Short-term Memory (InMemoryChatMessageHistory)"""
        try:
            memory = MemoryManager(self.tenant_id, self.agent_id)

            # Add test messages
            test_messages = [
                ("user", "Hello Rick, I'm testing your memory system"),
                ("assistant", "Morty! *burp* Of course you are. My memory is infinitely superior to your goldfish brain."),
                ("user", "Can you remember what I just said about testing?"),
                ("assistant", "You said you're testing my memory system. Obviously. *burp*")
            ]

            for role, content in test_messages:
                memory.add_message(role, content)

            # Test recall
            thread_history = memory.get_thread_history()

            if len(thread_history) != 4:
                self.log_test("Short-term Memory", False, f"Expected 4 messages, got {len(thread_history)}")
                return False

            # Verify message content
            last_message = thread_history[-1].content
            if "testing my memory system" not in last_message:
                self.log_test("Short-term Memory", False, "Failed to recall recent conversation")
                return False

            self.log_test("Short-term Memory", True, f"Stored and recalled {len(thread_history)} messages")
            return True

        except Exception as e:
            self.log_test("Short-term Memory", False, f"Error: {e}")
            return False

    async def test_agent_node_memory_integration(self) -> bool:
        """Test 3: Agent Node Memory Integration"""
        try:
            # Rick Sanchez traits for testing
            rick_traits = {
                "name": "Rick Sanchez",
                "shortDescription": "Genius scientist from dimension C-137",
                "identity": "I'm Rick Sanchez, the smartest man in the universe",
                "mission": "To maintain my intellectual superiority while dealing with Morty's incompetence",
                "interactionStyle": "Sarcastic, brilliant, dismissive, with frequent burping",
                "creativity": 95,
                "empathy": 15,
                "assertiveness": 90,
                "verbosity": 75,
                "formality": 10,
                "confidence": 100,
                "humor": 85,
                "technicality": 100,
                "safety": 20
            }

            # First conversation
            state1 = {
                "session_id": self.session_id,
                "tenant_id": self.tenant_id,
                "agent_id": self.agent_id,
                "user_input": "Hi Rick, I'm working on a portal gun project",
                "traits": rick_traits,
                "workflow_status": "active"
            }

            result1 = await agent_node(state1)

            if result1.get("workflow_status") == "error":
                self.log_test("Agent Node Memory Integration", False, f"Agent error: {result1.get('error_message')}")
                return False

            response1 = result1.get("agent_response", "")

            # Second conversation (should remember portal gun mention)
            state2 = {
                "session_id": self.session_id,
                "tenant_id": self.tenant_id,
                "agent_id": self.agent_id,
                "user_input": "What did I just tell you about my project?",
                "traits": rick_traits,
                "workflow_status": "active"
            }

            result2 = await agent_node(state2)
            response2 = result2.get("agent_response", "")

            # Check if Rick remembered the portal gun mention
            memory_indicators = ["portal gun", "project", "working on"]
            remembered = any(indicator.lower() in response2.lower() for indicator in memory_indicators)

            if not remembered:
                self.log_test("Agent Node Memory Integration", False, f"Failed to recall portal gun project. Response: {response2[:100]}...")
                return False

            self.log_test("Agent Node Memory Integration", True, "Agent recalled previous conversation context")
            return True

        except Exception as e:
            self.log_test("Agent Node Memory Integration", False, f"Error: {e}")
            return False

    def test_persistent_memory_search(self) -> bool:
        """Test 4: Persistent Memory Search (Mem0)"""
        try:
            memory = MemoryManager(self.tenant_id, self.agent_id)

            if not memory.persistent:
                self.log_test("Persistent Memory Search", False, "Mem0 not available - skipping test")
                return False

            # Add some memories
            test_memories = [
                ("user", "I love interdimensional travel and science"),
                ("assistant", "Of course you do, Morty. Science is the only thing that matters."),
                ("user", "Tell me about your portal gun technology"),
                ("assistant", "Portal gun technology is complex quantum mechanics that your tiny brain couldn't comprehend.")
            ]

            for role, content in test_memories:
                memory.add_message(role, content)

            # Wait a moment for indexing
            time.sleep(2)

            # Search for relevant context
            context = memory.get_context("portal gun technology")

            relevant_memories = context.get("relevant", [])
            recent_memories = context.get("recent", [])

            total_memories = len(relevant_memories) + len(recent_memories)

            if total_memories == 0:
                self.log_test("Persistent Memory Search", False, "No memories retrieved from search")
                return False

            self.log_test("Persistent Memory Search", True, f"Retrieved {len(relevant_memories)} relevant + {len(recent_memories)} recent memories")
            return True

        except Exception as e:
            self.log_test("Persistent Memory Search", False, f"Error: {e}")
            return False

    def test_memory_isolation(self) -> bool:
        """Test 5: Tenant/Agent Memory Isolation"""
        try:
            # Different tenant and agent
            memory1 = MemoryManager(self.tenant_id, self.agent_id)
            memory2 = MemoryManager("different-tenant", "different-agent")
            memory3 = MemoryManager(self.tenant_id, "different-agent")

            # Check namespace isolation
            namespaces = [memory1.namespace, memory2.namespace, memory3.namespace]
            unique_namespaces = set(namespaces)

            if len(unique_namespaces) != 3:
                self.log_test("Memory Isolation", False, f"Namespace collision: {namespaces}")
                return False

            # Add data to first memory
            memory1.add_message("user", "Secret information for agent 1")

            # Check that other memories don't see it
            history2 = memory2.get_thread_history()
            history3 = memory3.get_thread_history()

            if len(history2) > 0 or len(history3) > 0:
                self.log_test("Memory Isolation", False, "Memory leaked between isolated namespaces")
                return False

            self.log_test("Memory Isolation", True, f"Confirmed isolation: {unique_namespaces}")
            return True

        except Exception as e:
            self.log_test("Memory Isolation", False, f"Error: {e}")
            return False

    async def test_conversation_threading(self) -> bool:
        """Test 6: Multi-turn Conversation Threading"""
        try:
            conversation_states = [
                "Hi Rick, I'm planning to build a spaceship",
                "What materials do I need for the hull?",
                "How do I calculate the fuel requirements?",
                "Can you remind me what my original project was?"
            ]

            rick_traits = {
                "name": "Rick Sanchez",
                "shortDescription": "Genius scientist with poor people skills",
                "identity": "Rick C-137, smartest man in the universe",
                "creativity": 95, "empathy": 15, "assertiveness": 90,
                "verbosity": 75, "formality": 10, "confidence": 100,
                "humor": 85, "technicality": 100, "safety": 20
            }

            responses = []

            for i, user_input in enumerate(conversation_states):
                state = {
                    "session_id": f"{self.session_id}-threading",
                    "tenant_id": self.tenant_id,
                    "agent_id": self.agent_id,
                    "user_input": user_input,
                    "traits": rick_traits,
                    "workflow_status": "active"
                }

                result = await agent_node(state)
                response = result.get("agent_response", "")
                responses.append(response)

                # Small delay to ensure proper sequencing
                await asyncio.sleep(0.5)

            # Final response should reference the original spaceship project
            final_response = responses[-1].lower()
            project_mentioned = any(word in final_response for word in ["spaceship", "ship", "project", "build"])

            if not project_mentioned:
                self.log_test("Conversation Threading", False, f"Failed to recall original project. Final response: {responses[-1][:150]}...")
                return False

            self.log_test("Conversation Threading", True, f"Successfully threaded {len(conversation_states)} conversation turns")
            return True

        except Exception as e:
            self.log_test("Conversation Threading", False, f"Error: {e}")
            return False

    def test_memory_performance(self) -> bool:
        """Test 7: Memory Performance Metrics"""
        try:
            memory = MemoryManager(self.tenant_id, self.agent_id)

            # Performance test: Add multiple messages
            start_time = time.time()

            for i in range(10):
                memory.add_message("user", f"Test message {i}")
                memory.add_message("assistant", f"Response to message {i}")

            add_time = time.time() - start_time

            # Performance test: Retrieve context
            start_time = time.time()
            context = memory.get_context("test message")
            retrieve_time = time.time() - start_time

            # Check performance thresholds
            if add_time > 5.0:  # 5 seconds for 20 messages
                self.log_test("Memory Performance", False, f"Add operation too slow: {add_time:.2f}s")
                return False

            if retrieve_time > 3.0:  # 3 seconds for context retrieval
                self.log_test("Memory Performance", False, f"Retrieval too slow: {retrieve_time:.2f}s")
                return False

            self.log_test("Memory Performance", True, f"Add: {add_time:.2f}s, Retrieve: {retrieve_time:.2f}s")
            return True

        except Exception as e:
            self.log_test("Memory Performance", False, f"Error: {e}")
            return False

    async def run_all_tests(self):
        """Run complete E2E test suite"""
        print("Starting E2E Memory Tests...")
        print("")

        # Test sequence
        tests = [
            ("Memory Initialization", self.test_memory_initialization),
            ("Short-term Memory", self.test_short_term_memory),
            ("Agent Node Integration", self.test_agent_node_memory_integration),
            ("Persistent Memory Search", self.test_persistent_memory_search),
            ("Memory Isolation", self.test_memory_isolation),
            ("Conversation Threading", self.test_conversation_threading),
            ("Memory Performance", self.test_memory_performance)
        ]

        passed_tests = 0
        total_tests = len(tests)

        for test_name, test_func in tests:
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()

                if result:
                    passed_tests += 1

            except Exception as e:
                self.log_test(test_name, False, f"Test exception: {e}")

            print("")  # Space between tests

        # Final results
        print("="*60)
        print(f"E2E Memory Test Results: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            print("*** ALL TESTS PASSED - Memory system is working correctly! ***")
        else:
            print("*** Some tests failed - check memory configuration ***")

        print("")
        print("Detailed Results:")
        for result in self.test_results:
            status = "[PASS]" if result["passed"] else "[FAIL]"
            print(f"  {status} {result['test']}")
            if result["details"]:
                print(f"     {result['details']}")

        return passed_tests == total_tests

async def main():
    """Main test runner"""
    test_suite = MemoryE2ETest()

    try:
        success = await test_suite.run_all_tests()
        exit_code = 0 if success else 1

        print("")
        print("*** Troubleshooting Tips: ***")
        print("- Ensure Mem0 is installed: pip install mem0ai")
        print("- Check OpenAI API key in environment")
        print("- Verify Qdrant is running for vector storage")
        print("- Check database connectivity")

        return exit_code

    except KeyboardInterrupt:
        print("\n*** Test interrupted by user ***")
        return 1
    except Exception as e:
        print(f"\n*** Test suite crashed: {e} ***")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)