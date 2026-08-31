"""
Memory Retrieval Service — Phase 16

Multi-signal relevance scoring and retrieval of historically similar memories
with explicit explainability reasons and bounded scoring.
"""

from typing import List, Dict, Any, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from app.models.obligation import Obligation
from app.models.memory import OrganizationalMemory
from app.core.status_machine import MemoryType
from app.schemas.memory import (
    MemoryRetrievalItem,
    OrganizationalMemoryResponse,
    SemanticRepresentationResponse,
)
from app.services.intelligence.memory.semantic_context_engine import SemanticContextEngine


def _token_jaccard(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    t1 = set(s1.lower().split())
    t2 = set(s2.lower().split())
    if not t1 or not t2:
        return 0.0
    intersection = t1.intersection(t2)
    union = t1.union(t2)
    return len(intersection) / len(union) if union else 0.0


def _list_jaccard(l1: List[str], l2: List[str]) -> float:
    if not l1 or not l2:
        return 0.0
    s1 = set([x.lower() for x in l1])
    s2 = set([x.lower() for x in l2])
    intersection = s1.intersection(s2)
    union = s1.union(s2)
    return len(intersection) / len(union) if union else 0.0


class MemoryRetrievalService:
    """
    Retrieves and ranks relevant historical memories for an obligation or semantic query.
    """

    @classmethod
    async def retrieve_for_obligation(
        cls,
        session: AsyncSession,
        obligation: Obligation,
        min_relevance: float = 0.25,
        limit: int = 15,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[MemoryRetrievalItem]:
        """
        Retrieves relevant historical memories for a given obligation.
        """
        # Extract semantic features
        sem = SemanticContextEngine.extract_semantic_representation(
            text=obligation.action,
            owner=obligation.owner,
            deadline=obligation.deadline,
            obligation_type=obligation.obligation_type.value if hasattr(obligation.obligation_type, "value") else str(obligation.obligation_type),
        )

        # Query all active memories in workspace (excluding current obligation's direct completion if exists)
        stmt = select(OrganizationalMemory).where(
            and_(
                OrganizationalMemory.workspace_id == obligation.workspace_id,
                OrganizationalMemory.is_active == True,
                or_(
                    OrganizationalMemory.obligation_id.is_(None),
                    OrganizationalMemory.obligation_id != obligation.id,
                ),
            )
        ).order_by(desc(OrganizationalMemory.observed_at)).limit(200)

        if memory_types:
            stmt = stmt.where(OrganizationalMemory.memory_type.in_(memory_types))

        res = await session.execute(stmt)
        candidates = res.scalars().all()

        scored_items: List[MemoryRetrievalItem] = []
        for mem in candidates:
            score, reasons, breakdown = cls._compute_relevance(
                target_sem=sem,
                target_owner=obligation.owner,
                target_action_raw=obligation.action,
                memory=mem,
            )

            if score >= min_relevance:
                scored_items.append(
                    MemoryRetrievalItem(
                        memory=OrganizationalMemoryResponse.model_validate(mem),
                        relevance_score=round(score, 3),
                        match_reasons=reasons,
                        similarity_breakdown=breakdown,
                    )
                )

        scored_items.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_items[:limit]

    @classmethod
    async def search_memories(
        cls,
        session: AsyncSession,
        workspace_id: str = "ws-default",
        query: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        owner_id: Optional[str] = None,
        min_relevance: float = 0.2,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MemoryRetrievalItem]:
        """
        Generic search across organizational memories.
        """
        stmt = select(OrganizationalMemory).where(
            and_(
                OrganizationalMemory.workspace_id == workspace_id,
                OrganizationalMemory.is_active == True,
            )
        ).order_by(desc(OrganizationalMemory.observed_at))

        if memory_type:
            stmt = stmt.where(OrganizationalMemory.memory_type == memory_type)
        if owner_id:
            stmt = stmt.where(OrganizationalMemory.owner_id == owner_id)

        res = await session.execute(stmt.offset(offset).limit(limit * 2))
        candidates = res.scalars().all()

        if not query:
            return [
                MemoryRetrievalItem(
                    memory=OrganizationalMemoryResponse.model_validate(m),
                    relevance_score=1.0,
                    match_reasons=["Direct filter match"],
                    similarity_breakdown={},
                )
                for m in candidates[:limit]
            ]

        query_sem = SemanticContextEngine.extract_semantic_representation(text=query)
        scored_items: List[MemoryRetrievalItem] = []
        for mem in candidates:
            score, reasons, breakdown = cls._compute_relevance(
                target_sem=query_sem,
                target_owner=owner_id,
                target_action_raw=query,
                memory=mem,
            )
            if score >= min_relevance:
                scored_items.append(
                    MemoryRetrievalItem(
                        memory=OrganizationalMemoryResponse.model_validate(mem),
                        relevance_score=round(score, 3),
                        match_reasons=reasons,
                        similarity_breakdown=breakdown,
                    )
                )

        scored_items.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_items[:limit]

    @classmethod
    def _compute_relevance(
        cls,
        target_sem: SemanticRepresentationResponse,
        target_owner: Optional[str],
        target_action_raw: str,
        memory: OrganizationalMemory,
    ) -> tuple[float, List[str], Dict[str, float]]:
        """
        Multi-factor relevance scoring.
        Returns: (relevance_score, match_reasons, breakdown)
        """
        reasons: List[str] = []
        breakdown: Dict[str, float] = {}

        # 1. Deliverable similarity (30%)
        mem_meta = memory.metadata_json or {}
        mem_deliverable = mem_meta.get("deliverable") or memory.semantic_summary
        deliv_sim = _token_jaccard(target_sem.deliverable or target_action_raw, mem_deliverable)
        breakdown["deliverable_similarity"] = round(deliv_sim, 2)
        if deliv_sim >= 0.4:
            reasons.append(f"Similar deliverable topic ({int(deliv_sim*100)}% match)")

        # 2. Owner similarity (20%)
        owner_sim = 0.0
        if target_owner and memory.owner_id:
            if target_owner.strip().lower() == memory.owner_id.strip().lower():
                owner_sim = 1.0
                reasons.append(f"Same owner ({memory.owner_id})")
        breakdown["owner_match"] = owner_sim

        # 3. Entity similarity (15%)
        mem_entities = memory.entities or []
        entity_sim = _list_jaccard(target_sem.entities, mem_entities)
        breakdown["entity_similarity"] = round(entity_sim, 2)
        shared_entities = set([e.lower() for e in target_sem.entities]).intersection([e.lower() for e in mem_entities])
        if shared_entities:
            reasons.append(f"Shared technical entities: {', '.join(shared_entities)}")

        # 4. Topic similarity (15%)
        mem_topics = memory.topics or []
        topic_sim = _list_jaccard(target_sem.topics, mem_topics)
        breakdown["topic_similarity"] = round(topic_sim, 2)
        shared_topics = set([t.lower() for t in target_sem.topics]).intersection([t.lower() for t in mem_topics])
        if shared_topics:
            reasons.append(f"Shared topic domain: {', '.join(shared_topics)}")

        # 5. Action similarity (10%)
        action_sim = 0.0
        mem_action = mem_meta.get("action")
        if target_sem.action and mem_action:
            if target_sem.action.lower() == mem_action.lower():
                action_sim = 1.0
                reasons.append(f"Same core action verb ({target_sem.action})")
        breakdown["action_match"] = action_sim

        # 6. Type similarity (10%)
        type_sim = 0.0
        if target_sem.obligation_type and target_sem.obligation_type in (memory.semantic_labels or []):
            type_sim = 1.0
        breakdown["type_match"] = type_sim

        total_score = (
            deliv_sim * 0.30 +
            owner_sim * 0.20 +
            entity_sim * 0.15 +
            topic_sim * 0.15 +
            action_sim * 0.10 +
            type_sim * 0.10
        )

        # Bounded between 0.0 and 1.0
        bounded_score = max(0.0, min(1.0, total_score))
        return bounded_score, reasons, breakdown
