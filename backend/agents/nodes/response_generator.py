"""
Response Generator Node - EXACT NewCoreLogicAudit.md Blueprint
Lines 334-381 implementation with precise pattern matching
"""

from typing import Callable
from models.agent import AgentPayload
from agents.prompt_loader import load_agent_prompt
from langchain_openai import ChatOpenAI
from core.config import settings

# Blueprint utility - placeholder for utils_llm
def build_llm(max_tokens: int, temperature: float = 0.4):
    """Build LLM with specified parameters"""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key=settings.OPENAI_API_KEY
    )

def respond(memory):
    """EXACT blueprint respond function - lines 343-381"""
    async def _run(state):
        agent: AgentPayload = state["agent"]
        rvr = agent.rvr()
        max_tokens = int(160 + rvr * 640)          # 160..800
        max_iters = 1 + (1 if rvr > 0.5 else 0)    # 1..2

        system_prompt = load_agent_prompt(agent)
        thread = memory.get_thread_context(state["session_id"])
        facts = memory.retrieve(user_id=state["user_id"], query=state["input_text"])

        context = "\n".join([f"- {f['text']}" for f in facts])
        history = "\n".join([f"{m['role']}: {m['content']}" for m in thread[-8:]])

        llm = build_llm(max_tokens=max_tokens, temperature=0.4)
        prompt = f"""{system_prompt}

[Identity Short Description]
{agent.shortDescription}

[Traits JSON]
{agent.traits.model_dump_json()}

[Context Facts]
{context}

[Recent Thread]
{history}

User: {state['input_text']}
Assistant:"""

        out = await llm.ainvoke(prompt)
        text = out.content if hasattr(out, "content") else str(out)
        # append to memory:
        memory.append_thread(state["session_id"], "assistant", text)
        return {**state, "response_text": text}
    return _run