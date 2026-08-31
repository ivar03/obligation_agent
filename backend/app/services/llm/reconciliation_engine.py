"""
Phase 20 Hybrid Extraction Reconciliation Engine.

Reconciles deterministic heuristic extraction candidates with LLM-generated proposals.
If they agree, confidence is boosted; if they disagree or contain ambiguity,
human review is mandatory and conservative defaults are preserved.
"""

from typing import Optional, Dict, Any, List
from app.schemas.obligation import ObligationCandidate
from app.schemas.llm import ObligationProposal, ExtractionReconciliation


class ExtractionReconciliationEngine:
    """
    Combines deterministic extraction and LLM interpretation into a canonical candidate.
    """

    @classmethod
    def reconcile(
        cls,
        deterministic_detected: bool,
        deterministic_candidate: Optional[ObligationCandidate],
        llm_proposal: Optional[ObligationProposal],
    ) -> ExtractionReconciliation:
        # Case 1: Deterministic only (LLM disabled, timed out, or unavailable)
        if not llm_proposal and deterministic_candidate:
            return ExtractionReconciliation(
                deterministic_detected=True,
                deterministic_candidate=deterministic_candidate.model_dump() if deterministic_candidate else None,
                llm_proposal=None,
                agreement_fields=["action", "owner", "deadline"],
                disagreement_fields=[],
                final_action=deterministic_candidate.action,
                final_owner=deterministic_candidate.owner,
                final_beneficiary=deterministic_candidate.beneficiary,
                final_deadline=str(deterministic_candidate.deadline) if deterministic_candidate.deadline else None,
                final_obligation_type=str(deterministic_candidate.obligation_type),
                final_conditions=deterministic_candidate.conditions,
                confidence=deterministic_candidate.confidence.overall,
                human_review_required=deterministic_candidate.resolution.review_required if deterministic_candidate.resolution else False,
                reconciliation_strategy="DETERMINISTIC_FALLBACK",
                reconciliation_reason="LLM proposal unavailable. Deterministic pipeline output used as baseline.",
            )

        # Case 2: Neither detected
        if not deterministic_detected and not llm_proposal:
            return ExtractionReconciliation(
                deterministic_detected=False,
                deterministic_candidate=None,
                llm_proposal=None,
                agreement_fields=[],
                disagreement_fields=[],
                final_action="No obligation detected",
                confidence=0.95,
                human_review_required=False,
                reconciliation_strategy="DETERMINISTIC_FALLBACK",
                reconciliation_reason="Both deterministic and LLM pipelines found no obligation.",
            )

        # Case 3: LLM only (Deterministic missed subtle conversational phrasing)
        if not deterministic_detected and llm_proposal:
            review_req = llm_proposal.confidence < 0.85 or bool(llm_proposal.uncertainties) or not llm_proposal.owner
            return ExtractionReconciliation(
                deterministic_detected=False,
                deterministic_candidate=None,
                llm_proposal=llm_proposal,
                agreement_fields=[],
                disagreement_fields=["detection_status"],
                final_action=llm_proposal.action,
                final_owner=llm_proposal.owner,
                final_beneficiary=llm_proposal.beneficiary,
                final_deadline=llm_proposal.deadline,
                final_obligation_type=llm_proposal.obligation_type,
                final_conditions=llm_proposal.conditions,
                confidence=round(llm_proposal.confidence * 0.90, 2),  # Slight discount since deterministic didn't trigger
                human_review_required=review_req,
                reconciliation_strategy="LLM_SUPPLEMENTED",
                reconciliation_reason="LLM detected commitment in conversational phrasing not matched by heuristics.",
            )

        # Case 4: Both detected -> Compare fields
        det = deterministic_candidate
        llm = llm_proposal

        agreement_fields: List[str] = []
        disagreement_fields: List[str] = []

        # Check Owner agreement
        det_owner = (det.owner or "").strip().lower() if det else ""
        llm_owner = (llm.owner or "").strip().lower() if llm else ""
        if det_owner and llm_owner and det_owner == llm_owner:
            agreement_fields.append("owner")
        elif det_owner != llm_owner:
            disagreement_fields.append("owner")

        # Check Action agreement (fuzzy)
        if det and llm:
            det_words = set(det.action.lower().split())
            llm_words = set(llm.action.lower().split())
            if det_words.intersection(llm_words):
                agreement_fields.append("action")
            else:
                disagreement_fields.append("action")

        # Check Deadline agreement
        if det and llm:
            if bool(det.deadline) == bool(llm.deadline):
                agreement_fields.append("deadline")
            else:
                disagreement_fields.append("deadline")

        # Evaluate Agreement vs Disagreement
        has_owner_disagreement = "owner" in disagreement_fields
        has_ambiguity = bool(llm.uncertainties) or not llm.owner if llm else False

        if not disagreement_fields and agreement_fields:
            # Strong Agreement Boost
            base_conf = max(det.confidence.overall if det else 0.5, llm.confidence if llm else 0.5)
            boosted_conf = min(0.98, round(base_conf + 0.08, 2))
            return ExtractionReconciliation(
                deterministic_detected=True,
                deterministic_candidate=det.model_dump() if det else None,
                llm_proposal=llm,
                agreement_fields=agreement_fields,
                disagreement_fields=[],
                final_action=llm.action if llm else (det.action if det else ""),
                final_owner=llm.owner if (llm and llm.owner) else (det.owner if det else None),
                final_beneficiary=llm.beneficiary if (llm and llm.beneficiary) else (det.beneficiary if det else None),
                final_deadline=llm.deadline if (llm and llm.deadline) else (str(det.deadline) if det and det.deadline else None),
                final_obligation_type=llm.obligation_type if llm else "OWED_TO_ME",
                final_conditions=llm.conditions if llm else (det.conditions if det else None),
                confidence=boosted_conf,
                human_review_required=False,
                reconciliation_strategy="AGREEMENT_BOOST",
                reconciliation_reason="Deterministic heuristics and LLM proposal in full agreement.",
            )
        else:
            # Disagreement or Ambiguity Gating
            avg_conf = round(((det.confidence.overall if det else 0.5) + (llm.confidence if llm else 0.5)) / 2.0, 2)
            # Penalize confidence on owner disagreement
            final_conf = max(0.40, round(avg_conf - 0.15, 2)) if has_owner_disagreement else avg_conf
            return ExtractionReconciliation(
                deterministic_detected=True,
                deterministic_candidate=det.model_dump() if det else None,
                llm_proposal=llm,
                agreement_fields=agreement_fields,
                disagreement_fields=disagreement_fields,
                final_action=det.action if det else (llm.action if llm else ""),
                final_owner=det.owner if (det and det.owner) else (llm.owner if llm else None),
                final_beneficiary=det.beneficiary if det else (llm.beneficiary if llm else None),
                final_deadline=str(det.deadline) if det and det.deadline else (llm.deadline if llm else None),
                final_obligation_type=str(det.obligation_type) if det else (llm.obligation_type if llm else "OWED_TO_ME"),
                final_conditions=det.conditions if det else (llm.conditions if llm else None),
                confidence=final_conf,
                human_review_required=True,
                reconciliation_strategy="DISAGREEMENT_GATED",
                reconciliation_reason=f"Disagreement on fields {disagreement_fields} or ambiguous ownership. Gated for human review.",
            )
