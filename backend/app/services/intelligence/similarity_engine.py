import re
from typing import List, Set, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.obligation import Obligation
from app.models.intelligence import ObligationOutcomeSnapshot
from app.schemas.intelligence import SimilarObligationItem, SimilarObligationsResponse


STOP_WORDS = {
    "a", "an", "the", "and", "or", "to", "for", "in", "on", "at", "of", "with",
    "by", "is", "are", "was", "were", "be", "been", "from", "as", "that", "this",
    "please", "can", "you", "will", "do", "i", "we", "my", "our", "it", "its"
}


def extract_keywords(text: str) -> Set[str]:
    """Extracts alphanumeric keyword tokens, lowercased and stripped of stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
    return {t for t in tokens if t not in STOP_WORDS}


class SimilarityEngine:
    """
    Deterministic feature similarity engine for retrieving historically similar
    obligations based on keyword overlap, duty parties, obligation types, and structural traits.
    """

    @classmethod
    def calculate_similarity(
        cls,
        target_action: str,
        target_owner: str,
        target_beneficiary: str,
        target_type: str,
        cand_action: str,
        cand_owner: str,
        cand_beneficiary: str,
        cand_type: str,
    ) -> Tuple[float, List[str]]:
        """
        Computes deterministic similarity score [0.0, 1.0] and returns shared feature descriptors.
        """
        shared_features: List[str] = []
        score = 0.0

        # 1. Action Keyword Overlap (Weight: 0.50)
        target_kw = extract_keywords(target_action)
        cand_kw = extract_keywords(cand_action)
        overlap = target_kw.intersection(cand_kw)

        if target_kw and cand_kw:
            union = target_kw.union(cand_kw)
            jaccard = len(overlap) / len(union) if union else 0.0
            score += jaccard * 0.50
            if overlap:
                shared_features.append(f"Matching keywords: {', '.join(sorted(overlap))}")

        # 2. Owner Match (Weight: 0.20)
        if target_owner and cand_owner and target_owner.strip().lower() == cand_owner.strip().lower():
            score += 0.20
            shared_features.append(f"Same owner ({target_owner})")

        # 3. Beneficiary Match (Weight: 0.15)
        if target_beneficiary and cand_beneficiary and target_beneficiary.strip().lower() == cand_beneficiary.strip().lower():
            score += 0.15
            shared_features.append(f"Same beneficiary ({target_beneficiary})")

        # 4. Obligation Type Match (Weight: 0.15)
        if target_type and cand_type and target_type == cand_type:
            score += 0.15
            shared_features.append(f"Same obligation direction ({target_type})")

        return min(1.0, score), shared_features

    @classmethod
    async def find_similar_obligations(
        cls,
        session: AsyncSession,
        obligation_id: str,
        limit: int = 6,
        min_threshold: float = 0.15,
    ) -> SimilarObligationsResponse:
        """
        Finds historically similar obligations from persisted outcome snapshots.
        """
        target = await session.get(Obligation, obligation_id)
        if not target:
            return SimilarObligationsResponse(
                obligation_id=obligation_id,
                items=[],
                total_similar_count=0,
                historical_summary="Target obligation not found."
            )

        # Query outcome snapshots excluding current obligation
        stmt = (
            select(ObligationOutcomeSnapshot)
            .where(ObligationOutcomeSnapshot.obligation_id != obligation_id)
            .order_by(ObligationOutcomeSnapshot.created_at.desc())
        )
        res = await session.execute(stmt)
        snapshots = res.scalars().all()

        # Deduplicate snapshots per obligation (take latest)
        seen_ob_ids = set()
        unique_snapshots = []
        for snap in snapshots:
            if snap.obligation_id not in seen_ob_ids:
                seen_ob_ids.add(snap.obligation_id)
                unique_snapshots.append(snap)

        scored_items: List[SimilarObligationItem] = []
        for snap in unique_snapshots:
            sim_score, shared = cls.calculate_similarity(
                target_action=target.action,
                target_owner=target.owner,
                target_beneficiary=target.beneficiary,
                target_type=target.obligation_type.value if hasattr(target.obligation_type, "value") else str(target.obligation_type),
                cand_action=snap.action,
                cand_owner=snap.owner,
                cand_beneficiary=snap.beneficiary,
                cand_type=snap.obligation_type,
            )

            if sim_score >= min_threshold:
                scored_items.append(
                    SimilarObligationItem(
                        obligation_id=snap.obligation_id,
                        action=snap.action,
                        owner=snap.owner,
                        beneficiary=snap.beneficiary,
                        status=snap.status,
                        outcome_type=snap.outcome_type,
                        delay_hours=snap.delay_hours,
                        similarity_score=round(sim_score, 2),
                        shared_features=shared,
                        completed_at=snap.completed_at,
                    )
                )

        # Sort descending by similarity
        scored_items.sort(key=lambda x: x.similarity_score, reverse=True)
        top_items = scored_items[:limit]

        # Summarize historical outcome distribution
        if not top_items:
            summary = "No historically similar obligations found matching current task traits."
        else:
            on_time = sum(1 for x in top_items if x.outcome_type in ["COMPLETED_ON_TIME", "COMPLETED_AFTER_INTERVENTION"])
            late = sum(1 for x in top_items if x.outcome_type in ["COMPLETED_LATE", "OVERDUE"])
            blocked = sum(1 for x in top_items if x.outcome_type == "BLOCKED")
            summary = (
                f"{len(top_items)} similar obligations observed: "
                f"{on_time} completed on time, {late} completed late/overdue, {blocked} blocked."
            )

        return SimilarObligationsResponse(
            obligation_id=obligation_id,
            items=top_items,
            total_similar_count=len(top_items),
            historical_summary=summary,
        )
