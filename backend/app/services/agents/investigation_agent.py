"""
Strands investigation agent.

Wraps the read-only obligation tools (app/services/agents/tools/obligation_tools.py)
in a Strands Agent that decides, turn by turn, which existing deterministic
service to consult before producing a grounded natural-language investigation
summary. The agent never mutates state, and its output is a validated
AgentInvestigationSummary, not a free-form message.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.agents import runtime
from app.services.agents.tools.obligation_tools import build_obligation_tools
from app.schemas.llm import AgentInvestigationSummary

INVESTIGATION_SYSTEM_PROMPT = (
    "You are an investigation assistant for Obligation Agent. You may call "
    "the provided read-only tools to inspect one obligation's state, its "
    "dependency chain, and its deterministic root-cause analysis. You must "
    "never claim a fact you did not retrieve through a tool call. Produce a "
    "short, plain-language narrative explaining why the obligation is at "
    "risk, and list which tools you used in `grounded_on`."
)


class InvestigationAgentService:
    """Runs a bounded, tool-using Strands agent over one obligation."""

    def __init__(self, agent_factory=runtime.build_gemini_agent):
        self._agent_factory = agent_factory

    async def investigate(
        self, session: AsyncSession, obligation_id: str, workspace_id: str
    ) -> AgentInvestigationSummary:
        tools = build_obligation_tools(
            session, workspace_id, max_calls=settings.STRANDS_MAX_TOOL_CALLS
        )
        agent = self._agent_factory(INVESTIGATION_SYSTEM_PROMPT, tools=tools)

        prompt = (
            f"Investigate obligation '{obligation_id}' in this workspace. "
            f"Use your tools to gather evidence before answering."
        )
        return await agent.structured_output_async(AgentInvestigationSummary, prompt)
