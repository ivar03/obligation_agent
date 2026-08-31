"""
Semantic Context Engine — Phase 16

Deterministic extraction of structured semantic signals from obligation actions,
deliverables, entities, topics, deadline characteristics, and blocker keywords.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.schemas.memory import SemanticRepresentationResponse

# Known action verbs
COMMON_ACTIONS = {
    "send", "deliver", "submit", "deploy", "review", "migrate", "complete",
    "prepare", "update", "verify", "export", "fix", "implement", "release",
    "test", "write", "configure", "integrate", "investigate", "generate",
    "share", "draft", "finalize", "publish", "run", "execute", "provide"
}

# Known domain entities
ENTITY_PATTERNS = {
    "database": [r"\bdatabase\b", r"\bdb\b", r"\bpostgres\b", r"\bmysql\b", r"\bmongo\b", r"\bschema\b", r"\bmigration\b"],
    "api": [r"\bapi\b", r"\brest\b", r"\bgraphql\b", r"\bendpoint\b", r"\bswagger\b"],
    "frontend": [r"\bfrontend\b", r"\bui\b", r"\bux\b", r"\bdashboard\b", r"\bview\b", r"\breact\b"],
    "backend": [r"\bbackend\b", r"\bserver\b", r"\bmicroservice\b", r"\bgrpc\b"],
    "billing": [r"\bbilling\b", r"\binvoice\b", r"\bpayment\b", r"\bstripe\b"],
    "infrastructure": [r"\bk8s\b", r"\bkubernetes\b", r"\bcluster\b", r"\bdisk\b", r"\bmemory\b", r"\baws\b", r"\bcloud\b", r"\bstaging\b", r"\bprod\b"],
    "security": [r"\bauth\b", r"\baudit\b", r"\bsecurity\b", r"\btoken\b", r"\bpermission\b", r"\bssl\b"],
    "analytics": [r"\bmetrics\b", r"\bbenchmark\b", r"\banalytics\b", r"\breport\b", r"\bperformance\b"],
}

# Topic taxonomy
TOPIC_PATTERNS = {
    "performance": [r"\bbenchmark\b", r"\bperformance\b", r"\blatency\b", r"\bthroughput\b", r"\bspeed\b", r"\boptimization\b"],
    "compliance": [r"\baudit\b", r"\bcompliance\b", r"\bgdpr\b", r"\bsecurity\b", r"\bgovernance\b"],
    "infrastructure": [r"\bmigration\b", r"\bcluster\b", r"\bdeploy\b", r"\bserver\b", r"\bdisk\b", r"\benvironment\b"],
    "release": [r"\brelease\b", r"\bdemo\b", r"\bclient\b", r"\blaunch\b", r"\bprod\b", r"\bproduction\b"],
    "integration": [r"\bintegration\b", r"\bapi\b", r"\bendpoint\b", r"\bwebhook\b", r"\bslack\b", r"\bconnect\b"],
    "documentation": [r"\bdoc\b", r"\bdocumentation\b", r"\bspec\b", r"\bguide\b", r"\breadme\b"],
    "billing": [r"\bbilling\b", r"\binvoice\b", r"\bfinance\b", r"\breconciliation\b"],
}

# Blocker patterns
BLOCKER_PATTERNS = [
    r"\bdisk full\b", r"\bout of memory\b", r"\boom\b", r"\btimeout\b",
    r"\bpermission denied\b", r"\bfailed build\b", r"\bcrash\b", r"\bblocked\b",
    r"\bunavailable\b", r"\benvironment\b", r"\bdependency\b", r"\bdown\b",
    r"\bnetwork error\b", r"\baccess issue\b", r"\bdelayed\b"
]

# Dependency keywords
DEPENDENCY_PATTERNS = [
    r"\bdepends on\b", r"\bblocked by\b", r"\bprerequisite\b",
    r"\bafter\b", r"\bwaiting on\b", r"\brequires\b", r"\bfollowing\b"
]


class SemanticContextEngine:
    """
    Extracts deterministic, explainable semantic features from obligation text,
    deliverables, deadlines, and context.
    """

    @classmethod
    def extract_semantic_representation(
        cls,
        text: str,
        owner: Optional[str] = None,
        deadline: Optional[datetime] = None,
        obligation_type: Optional[str] = None,
    ) -> SemanticRepresentationResponse:
        clean_text = (text or "").strip()
        lower_text = clean_text.lower()

        # 1. Extract action
        action = cls._extract_action(lower_text)

        # 2. Extract deliverable
        deliverable = cls._extract_deliverable(clean_text, action)

        # 3. Extract entities
        entities = cls._extract_entities(lower_text)

        # 4. Extract topics
        topics = cls._extract_topics(lower_text)

        # 5. Extract deadline characteristic
        deadline_char = cls._classify_deadline(deadline)

        # 6. Extract blocker terms
        blocker_terms = cls._extract_blocker_terms(lower_text)

        # 7. Extract dependency terms
        dependency_terms = cls._extract_dependency_terms(lower_text)

        return SemanticRepresentationResponse(
            action=action,
            deliverable=deliverable,
            entities=entities,
            topics=topics,
            obligation_type=obligation_type,
            deadline_characteristic=deadline_char,
            blocker_terms=blocker_terms,
            dependency_terms=dependency_terms,
        )

    @classmethod
    def _extract_action(cls, lower_text: str) -> Optional[str]:
        words = re.findall(r"\b[a-z]+\b", lower_text)
        for word in words:
            if word in COMMON_ACTIONS:
                return word
        if words:
            return words[0]
        return None

    @classmethod
    def _extract_deliverable(cls, text: str, action: Optional[str]) -> str:
        # Strip action word from front if present
        clean = text.strip()
        if action and clean.lower().startswith(action.lower()):
            clean = clean[len(action):].strip()
            # Remove leading articles/prepositions
            clean = re.sub(r"^(the|a|an|to|for|on|in|with)\s+", "", clean, flags=re.IGNORECASE)
        return clean.strip() or text.strip()

    @classmethod
    def _extract_entities(cls, lower_text: str) -> List[str]:
        found = []
        for entity, patterns in ENTITY_PATTERNS.items():
            for p in patterns:
                if re.search(p, lower_text):
                    found.append(entity)
                    break
        return found

    @classmethod
    def _extract_topics(cls, lower_text: str) -> List[str]:
        found = []
        for topic, patterns in TOPIC_PATTERNS.items():
            for p in patterns:
                if re.search(p, lower_text):
                    found.append(topic)
                    break
        return found

    @classmethod
    def _classify_deadline(cls, deadline: Optional[datetime]) -> str:
        if not deadline:
            return "no_deadline"
        now = datetime.now(timezone.utc)
        dl = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        if dl < now:
            return "overdue"
        elif (dl - now).total_seconds() < 86400 * 2:
            return "due_soon"
        else:
            return "fixed_future_deadline"

    @classmethod
    def _extract_blocker_terms(cls, lower_text: str) -> List[str]:
        found = []
        for p in BLOCKER_PATTERNS:
            match = re.search(p, lower_text)
            if match:
                found.append(match.group(0))
        return list(set(found))

    @classmethod
    def _extract_dependency_terms(cls, lower_text: str) -> List[str]:
        found = []
        for p in DEPENDENCY_PATTERNS:
            match = re.search(p, lower_text)
            if match:
                found.append(match.group(0))
        return list(set(found))
