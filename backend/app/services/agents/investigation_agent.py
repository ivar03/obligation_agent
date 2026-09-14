"""
Strands investigation agent.

Wraps the read-only obligation tools (app/services/agents/tools/obligation_tools.py)
in a Strands Agent that decides, turn by turn, which existing deterministic
service to consult before producing a grounded natural-language investigation
summary. The agent never mutates state, and its output is a validated
AgentInvestigationSummary, not a free-form message.
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.agents import runtime
from app.services.agents.agent_run_recorder import record_agent_run
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

    @staticmethod
    async def _run_grounded(agent, prompt, schema_cls):
        """Run the tool-calling loop, then shape the result into schema_cls.

        structured_output_async() alone never invokes tools, so the model would
        answer from nothing. invoke_async() drives the loop; the follow-up
        structured call reads the conversation the tools produced.
        """
        await agent.invoke_async(prompt)
        return await agent.structured_output_async(schema_cls)

    async def investigate(
        self, session: AsyncSession, obligation_id: str, workspace_id: str
    ) -> AgentInvestigationSummary:
        counter: dict = {}
        async with record_agent_run(
            session, workspace_id=workspace_id, agent_name="investigation",
            obligation_id=obligation_id, counter=counter,
        ):
            tools = build_obligation_tools(
                session, workspace_id,
                max_calls=settings.STRANDS_MAX_TOOL_CALLS, counter=counter,
            )
            agent = self._agent_factory(INVESTIGATION_SYSTEM_PROMPT, tools=tools)

            prompt = (
                f"Investigate obligation '{obligation_id}' in this workspace. "
                f"Use your tools to gather evidence before answering."
            )
            # Two steps on purpose. structured_output_async() is a one-shot
            # schema fill: it does NOT run the tool-calling loop even when tools
            # are attached, so calling it alone makes the model invent its
            # answer. invoke_async() runs the loop; the structured call then
            # shapes what the tools actually returned.
            result = await asyncio.wait_for(
                self._run_grounded(agent, prompt, AgentInvestigationSummary),
                timeout=settings.STRANDS_TIMEOUT_SECONDS,
            )

        # grounded_on is evidence, not narration: report the tools that actually
        # ran, never the names the model claims it used.
        result.grounded_on = counter.get("names", [])
        result.obligation_id = obligation_id
        result.schema_version = "agent-investigation-summary-v1"
        return result
