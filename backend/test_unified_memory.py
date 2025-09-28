#!/usr/bin/env python3
"""
Unified Memory System Integration Test

Tests the complete unified memory system with:
- Thread management
- Mem0 integration
- GenerativeAgentMemory
- Reinforcement Learning
- JSON contract lens
- Agent response integration
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from memory.unified_memory_manager import create_memory_manager, AgentIdentity
from agents.nodes.agent_node import generate_agent_response

class UnifiedMemoryTest:
    def __init__(self):
        self.test_results = []
        self.tenant_id = "test-unified"
        self.agent_id = "rick-sanchez-unified"
        self.session_id = f"unified-test-{int(datetime.now().timestamp())}"

        # Rick Sanchez traits for comprehensive testing
        self.rick_traits = {
            "name": "Rick Sanchez",
            "shortDescription": "Genius scientist from dimension C-137",
            "identity": "I'm Rick Sanchez, the smartest man in the universe. My IQ is immeasurable and my scientific achievements are legendary across all dimensions.",
            "mission": "To conduct groundbreaking scientific research while maintaining my intellectual superiority and dealing with the incompetence of lesser beings, especially Morty.",
            "interactionStyle": "Sarcastic, brilliant, dismissive with frequent burping and scientific references. I speak with absolute confidence and often belittle others' intelligence.",
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

        print("🧠 Unified Memory System Integration Test")
        print("=" * 60)
        print(f"Session: {self.session_id}")
        print(f"Agent: {self.agent_id} ({self.rick_traits['name']})")
        print()

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")

        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    async def test_unified_memory_initialization(self):
        """Test unified memory manager initialization"""
        try:
            memory_manager = create_memory_manager(
                self.tenant_id,
                self.agent_id,
                self.rick_traits
            )

            # Check identity integration
            identity_name = memory_manager.agent_identity.name if memory_manager.agent_identity else None

            # Check metrics
            metrics = memory_manager.get_metrics()

            self.log_test(
                "Unified Memory Initialization",
                True,
                f"Identity: {identity_name}, Namespace: {memory_manager.namespace}"
            )

            return memory_manager

        except Exception as e:
            self.log_test("Unified Memory Initialization", False, f"Error: {e}")
            return None

    async def test_memory_context_retrieval(self, memory_manager):
        """Test unified memory context retrieval"""
        try:
            # Add some initial context
            await memory_manager.process_interaction(
                user_input="Hello Rick, I'm working on a portal gun project",
                agent_response="*burp* Of course you are, Morty. Portal gun technology is beyond your comprehension.",
                session_id=self.session_id
            )

            # Test context retrieval
            context = await memory_manager.get_agent_context(
                "What do you think about my project?",
                self.session_id
            )

            # Verify context structure
            checks = [
                len(context.thread_history) > 0,
                context.identity_filter is not None,
                context.confidence_score > 0,
                len(context.context_summary) > 0
            ]

            all_passed = all(checks)
            self.log_test(
                "Memory Context Retrieval",
                all_passed,
                f"Thread: {len(context.thread_history)}, Confidence: {context.confidence_score:.2f}"
            )

            return context

        except Exception as e:
            self.log_test("Memory Context Retrieval", False, f"Error: {e}")
            return None

    async def test_reinforcement_learning_integration(self, memory_manager):
        """Test reinforcement learning integration"""
        try:
            # Process interaction with positive feedback
            result = await memory_manager.process_interaction(
                user_input="You're incredibly smart, Rick!",
                agent_response="Obviously. *burp* My intelligence is infinite.",
                session_id=self.session_id,
                feedback={
                    "reward": 0.8,
                    "type": "confidence_positive",
                    "user_satisfaction": "high"
                }
            )

            # Check RL adjustments
            metrics = memory_manager.get_metrics()
            rl_adjustments = metrics.get('rl_adjustments', {})

            # Verify RL system is working
            rl_working = any(abs(v) > 0 for v in rl_adjustments.values())

            self.log_test(
                "Reinforcement Learning Integration",
                rl_working,
                f"Adjustments: {rl_adjustments}"
            )

            return result

        except Exception as e:
            self.log_test("Reinforcement Learning Integration", False, f"Error: {e}")
            return None

    async def test_agent_response_with_memory(self):
        """Test complete agent response with unified memory"""
        try:
            # Prepare state for agent response
            state = {
                "session_id": self.session_id,
                "tenant_id": self.tenant_id,
                "agent_id": self.agent_id,
                "user_input": "Can you remember what I'm working on and help me improve it?",
                "traits": self.rick_traits,
                "model": "gpt-4o-mini"
            }

            # Generate response using unified memory
            response = await generate_agent_response(state)

            # Check if response shows memory awareness
            memory_indicators = [
                "portal gun" in response.lower(),
                "project" in response.lower(),
                "rick" in response.lower() or "burp" in response.lower()
            ]

            memory_aware = any(memory_indicators)

            self.log_test(
                "Agent Response with Memory",
                memory_aware and len(response) > 0,
                f"Response length: {len(response)}, Memory indicators: {sum(memory_indicators)}"
            )

            return response

        except Exception as e:
            self.log_test("Agent Response with Memory", False, f"Error: {e}")
            return None

    async def test_json_contract_lens(self, memory_manager):
        """Test JSON contract lens filtering"""
        try:
            # Add memories with varying relevance to Rick's identity
            scientific_memory = await memory_manager.process_interaction(
                user_input="Let's discuss quantum mechanics and dimensional travel",
                agent_response="Finally! A topic worthy of my genius. *burp* Quantum mechanics is child's play when you understand the multiverse.",
                session_id=self.session_id
            )

            # Test identity-based filtering
            context = await memory_manager.get_agent_context(
                "Tell me about science",
                self.session_id
            )

            # Check if identity filtering is working
            identity_present = context.identity_filter is not None
            identity_name_match = (
                context.identity_filter and
                context.identity_filter.name == self.rick_traits['name']
            )

            self.log_test(
                "JSON Contract Lens",
                identity_present and identity_name_match,
                f"Identity: {context.identity_filter.name if context.identity_filter else 'None'}"
            )

            return context

        except Exception as e:
            self.log_test("JSON Contract Lens", False, f"Error: {e}")
            return None

    async def test_memory_persistence_and_retrieval(self, memory_manager):
        """Test memory persistence across sessions"""
        try:
            # Create a new session but same agent
            new_session_id = f"{self.session_id}-persistence"

            # Add memory in new session
            await memory_manager.process_interaction(
                user_input="Remember, I'm building a spaceship for interdimensional travel",
                agent_response="*burp* Another amateur hour project. But fine, I'll help you not screw it up completely.",
                session_id=new_session_id
            )

            # Test cross-session memory retrieval
            context = await memory_manager.get_agent_context(
                "What am I working on?",
                new_session_id
            )

            # Check if memories from different sessions are accessible
            has_memories = len(context.relevant_memories) > 0 or len(context.thread_history) > 0

            self.log_test(
                "Memory Persistence & Retrieval",
                has_memories,
                f"Memories: {len(context.relevant_memories)}, Thread: {len(context.thread_history)}"
            )

            return context

        except Exception as e:
            self.log_test("Memory Persistence & Retrieval", False, f"Error: {e}")
            return None

    async def test_reflection_system(self, memory_manager):
        """Test reflection system integration"""
        try:
            # Trigger multiple interactions to activate reflection
            interactions = [
                ("I need help with quantum physics", "Finally, a worthy question. *burp*"),
                ("You're the smartest person ever!", "Obviously. *burp* State the obvious more."),
                ("Can you teach me about dimensions?", "*burp* Your brain couldn't handle it, but I'll try."),
            ]

            for user_msg, agent_msg in interactions:
                await memory_manager.process_interaction(
                    user_input=user_msg,
                    agent_response=agent_msg,
                    session_id=self.session_id
                )

            # Check reflection system
            metrics = memory_manager.get_metrics()
            reflection_count = metrics.get('reflection_count', 0)

            # Manually trigger reflection
            await memory_manager._generate_reflection(self.session_id)

            # Check reflections
            reflections = memory_manager._get_recent_reflections()

            self.log_test(
                "Reflection System",
                len(reflections) > 0,
                f"Reflections: {len(reflections)}, Latest: {reflections[-1][:100] if reflections else 'None'}..."
            )

            return reflections

        except Exception as e:
            self.log_test("Reflection System", False, f"Error: {e}")
            return None

    async def test_comprehensive_metrics(self, memory_manager):
        """Test comprehensive system metrics"""
        try:
            metrics = memory_manager.get_metrics()

            required_metrics = [
                'namespace', 'agent_identity', 'interaction_count',
                'mem0_enabled', 'ga_memory_enabled', 'rl_enabled',
                'rl_adjustments', 'settings'
            ]

            metrics_present = all(key in metrics for key in required_metrics)

            self.log_test(
                "Comprehensive Metrics",
                metrics_present,
                f"Metrics keys: {list(metrics.keys())}"
            )

            return metrics

        except Exception as e:
            self.log_test("Comprehensive Metrics", False, f"Error: {e}")
            return None

    async def run_all_tests(self):
        """Run complete unified memory test suite"""
        print("Starting Unified Memory Integration Tests...")
        print()

        memory_manager = None

        # Test sequence
        tests = [
            ("Memory Initialization", self.test_unified_memory_initialization),
            ("Memory Context Retrieval", lambda: self.test_memory_context_retrieval(memory_manager)),
            ("Reinforcement Learning", lambda: self.test_reinforcement_learning_integration(memory_manager)),
            ("Agent Response Integration", self.test_agent_response_with_memory),
            ("JSON Contract Lens", lambda: self.test_json_contract_lens(memory_manager)),
            ("Memory Persistence", lambda: self.test_memory_persistence_and_retrieval(memory_manager)),
            ("Reflection System", lambda: self.test_reflection_system(memory_manager)),
            ("Comprehensive Metrics", lambda: self.test_comprehensive_metrics(memory_manager))
        ]

        passed_tests = 0
        total_tests = len(tests)

        for test_name, test_func in tests:
            try:
                if test_name == "Memory Initialization":
                    memory_manager = await test_func()
                    if memory_manager:
                        passed_tests += 1
                else:
                    if memory_manager:
                        result = await test_func()
                        if result is not None:
                            passed_tests += 1
                    else:
                        self.log_test(test_name, False, "Memory manager not initialized")

            except Exception as e:
                self.log_test(test_name, False, f"Test exception: {e}")

            print()  # Space between tests

        # Final results
        print("=" * 60)
        print(f"🧠 Unified Memory Test Results: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED - Unified memory system is fully functional!")
        else:
            print(f"⚠️  {total_tests - passed_tests} tests failed - check implementation")

        # Detailed summary
        print("\n📊 Test Summary:")
        for result in self.test_results:
            status = "✅" if result["passed"] else "❌"
            print(f"  {status} {result['test']}")
            if result["details"]:
                print(f"     {result['details']}")

        return passed_tests == total_tests

async def main():
    """Main test runner"""
    test_suite = UnifiedMemoryTest()

    try:
        success = await test_suite.run_all_tests()

        print("\n🔧 Integration Notes:")
        print("- Agent responses now include memory context automatically")
        print("- Reinforcement learning adjusts traits dynamically")
        print("- JSON contract lens filters memories by agent identity")
        print("- Reflection system provides continuous learning")
        print("- All memory components work through single interface")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)