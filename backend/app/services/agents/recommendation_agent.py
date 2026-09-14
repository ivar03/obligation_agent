"""
Strands recommendation agent.

Proposes a resolution strategy for one obligation, grounded in the
deterministic DecisionPlan that IntelligenceOrchestrator already produces plus
the read-only agent toolkit.

The agent recommends; it never acts. It does not create, approve, reject or
execute a DecisionPlan, and the authorization flag on its output is set by this
service, not by the model.
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.agents import runtime
from app.services.agents.agent_run_recorder import record_agent_run
from app.services.agents.tools.obligation_tools import build_obligation_tools
from app.services.intelligence.intelligence_orchestrator import IntelligenceOrchestrator
from app.schemas.llm import AgentRecommendation

RECOMMENDATION_SYSTEM_PROMPT = (
    "You are a resolution advisor for Obligation Agent. A deterministic "
    "decision plan has already been computed for this obligation and is given "
    "to you below; the read-only tools let you inspect the obligation, its "
    "dependencies, evidence, risk and recent events. Recommend ONE strategy "
    "and explain why, citing only facts you retrieved. You do not have the "
    "authority to approve, execute or change anything -- a human reviews every "
    "recommendation. Never claim an action has been taken."
)


class RecommendationAgentService:
    """Runs a bounded, tool-using Strands agent to propose one resolution strategy."""

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

    async def recommend(
        self, session: AsyncSession, obligation_id: str, workspace_id: str
    ) -> AgentRecommendation:
        # Translate the orchestrator's not-found ValueError into LookupError so the
        # route can map it to 404 without also swallowing configuration errors --
        # build_gemini_agent raises a plain ValueError when GEMINI_API_KEY is absent,
        # and reporting that as "obligation not found" misdirects operators at cutover.
        try:
            plan = await IntelligenceOrchestrator.generate_decision_plan(
                session, obligation_id, workspace_id=workspace_id
            )
        except ValueError as e:
            raise LookupError(str(e)) from e

        counter: dict = {}
        async with record_agent_run(
            session, workspace_id=workspace_id, agent_name="recommendation",
            obligation_id=obligation_id, counter=counter,
        ):
            tools = build_obligation_tools(
                session, workspace_id,
                max_calls=settings.STRANDS_MAX_TOOL_CALLS, counter=counter,
            )
            agent = self._agent_factory(RECOMMENDATION_SYSTEM_PROMPT, tools=tools)

            prompt = (
                f"Recommend how to resolve obligation '{obligation_id}'.\n"
                f"Deterministic decision plan {plan.id} says:\n"
                f"  primary objective: {plan.primary_objective}\n"
                f"  overall urgency: {plan.overall_urgency}\n"
                f"  overall risk: {plan.overall_risk}\n"
                f"  recommended actions: {plan.recommended_actions}\n"
                f"  open human decisions: {plan.human_decisions_required}\n"
                f"Use your tools to verify before recommending."
            )
            recommendation = await asyncio.wait_for(
                self._run_grounded(agent, prompt, AgentRecommendation),
                timeout=settings.STRANDS_TIMEOUT_SECONDS,
            )

        # Authorization is this service's to assert, never the model's.
        recommendation.grounded_on = counter.get("names", [])
        recommendation.schema_version = "agent-recommendation-v1"
        recommendation.decision_plan_id = plan.id
        recommendation.obligation_id = obligation_id
        recommendation.requires_human_authorization = True
        return recommendation