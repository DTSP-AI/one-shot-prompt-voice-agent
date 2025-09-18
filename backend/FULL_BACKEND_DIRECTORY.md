# FULL OneShotVoiceAgent Backend Directory Structure

## Complete File and Directory Listing

```
C:\AI_src\SeedPromptTest3\OneShotVoiceAgent\backend/
├── .pytest_cache/
│   ├── .gitignore
│   ├── CACHEDIR.TAG
│   ├── README.md
│   └── v/
│       └── cache/
│           ├── nodeids
│           └── stepwise
├── __pycache__/
│   ├── main.cpython-312.pyc
│   └── memory_manager.cpython-312.pyc
├── agents/
│   ├── __init__.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-312.pyc
│   │   ├── graph.cpython-312.pyc
│   │   └── state.cpython-312.pyc
│   ├── graph.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── __pycache__/
│   │   │   ├── __init__.cpython-312.pyc
│   │   │   ├── memory_node.cpython-312.pyc
│   │   │   ├── orchestrator.cpython-312.pyc
│   │   │   ├── response_generator.cpython-312.pyc
│   │   │   ├── supervisor.cpython-312.pyc
│   │   │   └── voice_processor.cpython-312.pyc
│   │   ├── agent_node.py
│   │   ├── orchestrator.py
│   │   ├── response_generator.py
│   │   ├── supervisor.py
│   │   └── voice_processor.py
│   ├── prompt_chain_template.py
│   ├── prompt_loader.py
│   └── state.py
├── api/
│   ├── __init__.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-312.pyc
│   │   ├── agents.cpython-312.pyc
│   │   ├── health.cpython-312.pyc
│   │   ├── livekit.cpython-312.pyc
│   │   ├── mcp.cpython-312.pyc
│   │   └── voice.cpython-312.pyc
│   ├── agent_api.py
│   ├── agents.py
│   ├── health.py
│   ├── livekit.py
│   ├── mcp.py
│   └── voice.py
├── core/
│   ├── __init__.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-312.pyc
│   │   ├── config.cpython-312.pyc
│   │   └── database.cpython-312.pyc
│   ├── config.py
│   └── database.py
├── data/
│   └── mem0.db
├── logs/
├── memory/
│   └── memory_manager.py
├── models/
│   ├── __init__.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-312.pyc
│   │   ├── agent.cpython-312.pyc
│   │   ├── conversation.cpython-312.pyc
│   │   └── user.cpython-312.pyc
│   ├── agent.py
│   ├── conversation.py
│   └── user.py
├── prompts/
│   └── agent_specific_prompt.json
├── scripts/
├── services/
│   ├── __init__.py
│   ├── __pycache__/
│   │   ├── __init__.cpython-312.pyc
│   │   ├── deepgram_service.cpython-312.pyc
│   │   ├── elevenlabs_service.cpython-312.pyc
│   │   ├── livekit_service.cpython-312.pyc
│   │   ├── mcp_service.cpython-312.pyc
│   │   └── memory_service.cpython-312.pyc
│   ├── deepgram_service.py
│   ├── elevenlabs_service.py
│   ├── livekit_service.py
│   └── mcp_service.py
├── tests/
│   ├── test_agent_api.py
│   ├── test_architecture_flow.py
│   ├── test_memory.py
│   ├── test_memory_manager.py
│   ├── test_prompt_loader.py
│   └── test_voice_integration.py
├── tools/
├── ARCHITECTURE_SUMMARY.md
├── BACKEND_DIRECTORY_MAP.md
├── COMPLETE_BACKEND_TREE.md
├── Dockerfile
├── main.py
└── requirements.txt
```

## Complete File Count

### Source Files (Python)
```
agents/__init__.py
agents/graph.py
agents/nodes/__init__.py
agents/nodes/agent_node.py
agents/nodes/orchestrator.py
agents/nodes/response_generator.py
agents/nodes/supervisor.py
agents/nodes/voice_processor.py
agents/prompt_chain_template.py
agents/prompt_loader.py
agents/state.py
api/__init__.py
api/agent_api.py
api/agents.py
api/health.py
api/livekit.py
api/mcp.py
api/voice.py
core/__init__.py
core/config.py
core/database.py
memory/memory_manager.py
models/__init__.py
models/agent.py
models/conversation.py
models/user.py
services/__init__.py
services/deepgram_service.py
services/elevenlabs_service.py
services/livekit_service.py
services/mcp_service.py
tests/test_agent_api.py
tests/test_architecture_flow.py
tests/test_memory.py
tests/test_memory_manager.py
tests/test_prompt_loader.py
tests/test_voice_integration.py
main.py
```
**Total Python Files: 38**

### Configuration Files
```
prompts/agent_specific_prompt.json
requirements.txt
Dockerfile
ARCHITECTURE_SUMMARY.md
BACKEND_DIRECTORY_MAP.md
COMPLETE_BACKEND_TREE.md
```
**Total Config Files: 6**

### Data Files
```
data/mem0.db
```
**Total Data Files: 1**

### Cache Files (Python bytecode)
```
__pycache__/main.cpython-312.pyc
__pycache__/memory_manager.cpython-312.pyc
agents/__pycache__/__init__.cpython-312.pyc
agents/__pycache__/graph.cpython-312.pyc
agents/__pycache__/state.cpython-312.pyc
agents/nodes/__pycache__/__init__.cpython-312.pyc
agents/nodes/__pycache__/memory_node.cpython-312.pyc
agents/nodes/__pycache__/orchestrator.cpython-312.pyc
agents/nodes/__pycache__/response_generator.cpython-312.pyc
agents/nodes/__pycache__/supervisor.cpython-312.pyc
agents/nodes/__pycache__/voice_processor.cpython-312.pyc
api/__pycache__/__init__.cpython-312.pyc
api/__pycache__/agents.cpython-312.pyc
api/__pycache__/health.cpython-312.pyc
api/__pycache__/livekit.cpython-312.pyc
api/__pycache__/mcp.cpython-312.pyc
api/__pycache__/voice.cpython-312.pyc
core/__pycache__/__init__.cpython-312.pyc
core/__pycache__/config.cpython-312.pyc
core/__pycache__/database.cpython-312.pyc
models/__pycache__/__init__.cpython-312.pyc
models/__pycache__/agent.cpython-312.pyc
models/__pycache__/conversation.cpython-312.pyc
models/__pycache__/user.cpython-312.pyc
services/__pycache__/__init__.cpython-312.pyc
services/__pycache__/deepgram_service.cpython-312.pyc
services/__pycache__/elevenlabs_service.cpython-312.pyc
services/__pycache__/livekit_service.cpython-312.pyc
services/__pycache__/mcp_service.cpython-312.pyc
services/__pycache__/memory_service.cpython-312.pyc
```
**Total Cache Files: 30**

### Test Cache Files
```
.pytest_cache/.gitignore
.pytest_cache/CACHEDIR.TAG
.pytest_cache/README.md
.pytest_cache/v/cache/nodeids
.pytest_cache/v/cache/stepwise
```
**Total Test Cache Files: 5**

## Directory Summary

### Populated Directories (22 directories)
1. **backend/** (root)
2. **.pytest_cache/**
3. **.pytest_cache/v/**
4. **.pytest_cache/v/cache/**
5. **__pycache__/**
6. **agents/**
7. **agents/__pycache__/**
8. **agents/nodes/**
9. **agents/nodes/__pycache__/**
10. **api/**
11. **api/__pycache__/**
12. **core/**
13. **core/__pycache__/**
14. **data/**
15. **memory/**
16. **models/**
17. **models/__pycache__/**
18. **prompts/**
19. **services/**
20. **services/__pycache__/**
21. **tests/**
22. **tools/**

### Empty Directories (2 directories)
1. **logs/**
2. **scripts/**

## Grand Total Files: 80 files across 22 directories

### File Type Breakdown:
- **Python source files**: 38
- **Python bytecode cache**: 30
- **Configuration files**: 6
- **Test cache files**: 5
- **Database files**: 1

**Total: 80 files**