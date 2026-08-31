"""
Phase 20 Versioned Prompt Registry.

Provides an immutable, versioned store of prompts used across the
LLM Natural-Language Intelligence Layer. Ensures every LLM analysis
records its exact prompt template, version, and parameters for reproducibility.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class PromptTemplate:
    def __init__(self, key: str, version: str, system_prompt: str, user_template: str, description: str):
        self.key = key
        self.version = version
        self.system_prompt = system_prompt
        self.user_template = user_template
        self.description = description

    def format_user_prompt(self, **kwargs) -> str:
        return self.user_template.format(**kwargs)


class PromptRegistry:
    """Central registry of versioned prompt templates."""

    _registry: Dict[str, PromptTemplate] = {}

    @classmethod
    def register(cls, template: PromptTemplate):
        full_key = f"{template.key}:{template.version}"
        cls._registry[full_key] = template
        cls._registry[template.key] = template  # Default alias points to latest registered

    @classmethod
    def get(cls, key: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        if version:
            lookup = f"{key}:{version}"
            return cls._registry.get(lookup)
        return cls._registry.get(key)

    @classmethod
    def list_prompts(cls) -> Dict[str, Dict[str, Any]]:
        return {
            k: {
                "key": v.key,
                "version": v.version,
                "description": v.description,
            }
            for k, v in cls._registry.items()
            if ":" in k  # Only return versioned keys
        }


# -----------------------------------------------------------------------------
# Standard Phase 20 Versioned Prompts
# -----------------------------------------------------------------------------

PromptRegistry.register(
    PromptTemplate(
        key="obligation_extraction",
        version="v1",
        description="Extracts structured obligation proposals from unstructured natural language.",
        system_prompt=(
            "You are an expert natural language obligation extraction assistant. "
            "Analyze the user message and extract commitment facts strictly into the provided JSON schema. "
            "Identify the duty bearer (owner), beneficiary, action, deadline, obligation type, and any conditions. "
            "If ownership or deadline is ambiguous, state the ambiguity explicitly and lower your confidence. "
            "Do not fabricate entities or deadlines not mentioned in the text."
        ),
        user_template=(
            "Extract any obligation or commitment from the following message:\n\n"
            "Source Reference: {source_ref}\n"
            "Sender: {sender}\n"
            "Channel: {channel}\n"
            "Message Content:\n\"\"\"\n{text}\n\"\"\"\n\n"
            "Provide the structured JSON output adhering to obligation-proposal-v1 schema."
        ),
    )
)

PromptRegistry.register(
    PromptTemplate(
        key="event_semantics",
        version="v1",
        description="Interprets semantic role, actor, deliverable and evidence clues in asynchronous events.",
        system_prompt=(
            "You are a semantic event classifier for a collaborative obligation management system. "
            "Classify the event into one of: COMPLETION_SIGNAL, COMMITMENT, REQUEST, PROGRESS_UPDATE, "
            "NEGATIVE_BLOCKER, or IRRELEVANT. Identify the actor, deliverable mentioned, recipient, and evidence strength. "
            "Note: Even a strong completion signal is only evidence and does NOT automatically complete an obligation."
        ),
        user_template=(
            "Analyze the semantic meaning of this inbound event:\n\n"
            "Provider: {provider}\n"
            "Channel/Stream: {stream_key}\n"
            "Event Content:\n\"\"\"\n{content}\n\"\"\"\n\n"
            "Provide structured JSON output according to event-semantic-proposal-v1 schema."
        ),
    )
)

PromptRegistry.register(
    PromptTemplate(
        key="evidence_interpretation",
        version="v1",
        description="Interprets whether an event or document fulfills an active obligation deliverable.",
        system_prompt=(
            "You are an evidence interpretation assistant. Evaluate whether the candidate event/document "
            "provides verifiable evidence for the specified active obligation. Identify exact deliverable match, "
            "temporal alignment, and potential contradictions."
        ),
        user_template=(
            "Target Obligation:\n"
            "- ID: {obligation_id}\n"
            "- Action: {action}\n"
            "- Owner: {owner}\n"
            "- Deadline: {deadline}\n\n"
            "Candidate Evidence Event:\n\"\"\"\n{evidence_content}\n\"\"\"\n\n"
            "Provide structured evidence interpretation JSON."
        ),
    )
)

PromptRegistry.register(
    PromptTemplate(
        key="grounded_explanation",
        version="v1",
        description="Generates concise human-readable explanations grounded exclusively in verified application facts.",
        system_prompt=(
            "You are an explanatory assistant for an obligation intelligence system. "
            "Generate a clear, natural-language explanation of the root cause, cascade impact, or risk situation. "
            "CRITICAL RULE: You must ground your explanation EXCLUSIVELY in the provided Verified Facts packet. "
            "Never invent names, dates, obligation IDs, causal claims, or deliverables not present in the facts packet. "
            "If information is missing, explicitly note that it is unknown."
        ),
        user_template=(
            "Verified Facts Packet:\n\"\"\"\n{context_packet_json}\n\"\"\"\n\n"
            "Focus Entity: {target_entity_id}\n"
            "Explanation Request: {prompt_instruction}\n\n"
            "Provide a grounded explanation with exact references to the supplied facts."
        ),
    )
)

PromptRegistry.register(
    PromptTemplate(
        key="decision_explanation",
        version="v1",
        description="Explains trade-offs and rationale for recommended intervention decision plans.",
        system_prompt=(
            "You are a decision rationale assistant. Explain why a recommended intervention plan was generated, "
            "what trade-offs exist, and why human authorization is required. Ground strictly in verified decision facts."
        ),
        user_template=(
            "Decision Plan Facts:\n\"\"\"\n{decision_plan_json}\n\"\"\"\n\n"
            "Provide a clear summary of the recommended action and trade-offs."
        ),
    )
)
