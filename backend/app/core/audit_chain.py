"""
Deterministic Cryptographic Hash-Chain Engine for Audit Logs.
Calculates and verifies workspace-scoped SHA-256 hash chains to guarantee
tamper-evidence and audit log integrity.
"""

import json
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64


def canonicalize_payload(
    event_id: str,
    workspace_id: str,
    actor_user_id: Optional[str],
    actor_role: Optional[str],
    action: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    timestamp: datetime,
    request_id: Optional[str],
    source: str,
    before_state: Optional[Dict[str, Any]],
    after_state: Optional[Dict[str, Any]],
    audit_metadata: Optional[Dict[str, Any]],
    reason: Optional[str],
    severity: str,
    result: str,
) -> str:
    """
    Produces a deterministic, canonical JSON string for an audit event payload.
    """
    ts_str = timestamp.astimezone(timezone.utc).isoformat() if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc).isoformat()
    # Normalize "+00:00" to "Z" for consistency
    if ts_str.endswith("+00:00"):
        ts_str = ts_str[:-6] + "Z"

    payload = {
        "action": str(action),
        "actor_role": str(actor_role) if actor_role else None,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "after_state": after_state,
        "audit_metadata": audit_metadata,
        "before_state": before_state,
        "entity_id": str(entity_id) if entity_id else None,
        "entity_type": str(entity_type) if entity_type else None,
        "id": str(event_id),
        "reason": str(reason) if reason else None,
        "request_id": str(request_id) if request_id else None,
        "result": str(result),
        "severity": str(severity),
        "source": str(source),
        "timestamp": ts_str,
        "workspace_id": str(workspace_id),
    }

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_event_hash(
    previous_hash: Optional[str],
    event_id: str,
    workspace_id: str,
    actor_user_id: Optional[str],
    actor_role: Optional[str],
    action: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    timestamp: datetime,
    request_id: Optional[str],
    source: str,
    before_state: Optional[Dict[str, Any]],
    after_state: Optional[Dict[str, Any]],
    audit_metadata: Optional[Dict[str, Any]],
    reason: Optional[str],
    severity: str,
    result: str,
) -> str:
    """
    Computes SHA256(previous_event_hash + canonical_event_payload).
    """
    prev = previous_hash or GENESIS_HASH
    canonical_json = canonicalize_payload(
        event_id=event_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=timestamp,
        request_id=request_id,
        source=source,
        before_state=before_state,
        after_state=after_state,
        audit_metadata=audit_metadata,
        reason=reason,
        severity=severity,
        result=result,
    )
    combined = f"{prev}:{canonical_json}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def verify_event_chain(events: List[Any]) -> Dict[str, Any]:
    """
    Validates the cryptographic integrity of an ordered list of audit events.
    Returns validation status, count verified, and failure diagnostics if broken.
    """
    if not events:
        return {
            "chain_valid": True,
            "status": "VALID",
            "broken_at_event_id": None,
            "expected_hash": None,
            "actual_hash": None,
            "verified_event_count": 0,
            "message": "Audit chain is empty and valid.",
        }

    expected_prev = GENESIS_HASH
    for idx, event in enumerate(events):
        event_prev = getattr(event, "previous_event_hash", None) or GENESIS_HASH
        if idx == 0:
            # First event in chain
            if event_prev != GENESIS_HASH:
                return {
                    "chain_valid": False,
                    "status": "BROKEN_LINK",
                    "broken_at_event_id": str(event.id),
                    "expected_hash": GENESIS_HASH,
                    "actual_hash": event_prev,
                    "verified_event_count": idx,
                    "message": f"Genesis event {event.id} has invalid previous_hash '{event_prev}'.",
                }
        else:
            if event_prev != expected_prev:
                return {
                    "chain_valid": False,
                    "status": "BROKEN_LINK",
                    "broken_at_event_id": str(event.id),
                    "expected_hash": expected_prev,
                    "actual_hash": event_prev,
                    "verified_event_count": idx,
                    "message": f"Event {event.id} link is broken. Expected previous hash '{expected_prev}', found '{event_prev}'.",
                }

        recalculated = compute_event_hash(
            previous_hash=event.previous_event_hash,
            event_id=str(event.id),
            workspace_id=str(event.workspace_id),
            actor_user_id=str(event.actor_user_id) if event.actor_user_id else None,
            actor_role=str(event.actor_role) if event.actor_role else None,
            action=str(event.action),
            entity_type=str(event.entity_type) if event.entity_type else None,
            entity_id=str(event.entity_id) if event.entity_id else None,
            timestamp=event.timestamp,
            request_id=str(event.request_id) if event.request_id else None,
            source=str(event.source),
            before_state=event.before_state,
            after_state=event.after_state,
            audit_metadata=event.audit_metadata,
            reason=event.reason,
            severity=str(event.severity),
            result=str(event.result),
        )

        if recalculated != event.event_hash:
            return {
                "chain_valid": False,
                "status": "TAMPERED_PAYLOAD",
                "broken_at_event_id": str(event.id),
                "expected_hash": recalculated,
                "actual_hash": event.event_hash,
                "verified_event_count": idx,
                "message": f"Event {event.id} payload has been tampered with or modified. Expected hash '{recalculated}', found '{event.event_hash}'.",
            }

        expected_prev = event.event_hash

    return {
        "chain_valid": True,
        "status": "VALID",
        "broken_at_event_id": None,
        "expected_hash": None,
        "actual_hash": None,
        "verified_event_count": len(events),
        "message": f"Audit hash chain verified across all {len(events)} events with zero anomalies.",
    }
