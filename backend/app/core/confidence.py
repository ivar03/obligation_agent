from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# Centralized Confidence Thresholds (Do NOT hardcode magic numbers in services)
CONFIDENCE_THRESHOLD_HIGH = 0.80
CONFIDENCE_THRESHOLD_MEDIUM = 0.60
CONFIDENCE_THRESHOLD_LOW = 0.60


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def get_confidence_level(score: float) -> ConfidenceLevel:
    if score >= CONFIDENCE_THRESHOLD_HIGH:
        return ConfidenceLevel.HIGH
    elif score >= CONFIDENCE_THRESHOLD_MEDIUM:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class AmbiguityDetail(BaseModel):
    field: str
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_action: Optional[str] = None


class ConfidenceEvaluator:
    """Centralized domain evaluator for field confidence and ambiguity resolution."""

    @staticmethod
    def is_review_required(confidences: Dict[str, float], ambiguities: List[AmbiguityDetail]) -> bool:
        """
        Determines whether human review is recommended/required based on confidence thresholds
        and explicit ambiguity flags.
        """
        if len(ambiguities) > 0:
            return True
        for field, score in confidences.items():
            if score < CONFIDENCE_THRESHOLD_HIGH:
                return True
        return False
