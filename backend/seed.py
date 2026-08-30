import asyncio
from datetime import datetime, timedelta, timezone
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.status_machine import (
    ObligationStatus,
    ObligationType,
    EdgeType,
    EvidenceType,
    CorrelationStatus,
    EventSemanticRole,
)
from app.core.intervention_status import (
    InterventionType,
    InterventionStatus,
    InterventionOutcome,
)
from app.models.obligation import Obligation, ObligationEdge, Evidence, Intervention
from app.services.intervention_planner import InterventionPlanner
from app.core.logging import logger, setup_logging


async def seed_data():
    setup_logging()
    logger.info("Initializing database schema for seeding...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        logger.info("Clearing previous records...")
        async with session.begin():
            await session.execute(Intervention.__table__.delete())
            await session.execute(Evidence.__table__.delete())
            await session.execute(ObligationEdge.__table__.delete())
            await session.execute(Obligation.__table__.delete())

        now = datetime.now(timezone.utc)
        six_hours_deadline = (now + timedelta(hours=6)).replace(microsecond=0)
        friday_deadline = (now + timedelta(days=2)).replace(hour=17, minute=0, second=0, microsecond=0)
        overdue_deadline = (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        next_week_deadline = (now + timedelta(days=5)).replace(hour=18, minute=0, second=0, microsecond=0)

        # 1. Prerequisite Obligation B: Rahul owes Ravi: "Send database benchmark numbers" (OVERDUE -> CRITICAL RISK)
        ob_b = Obligation(
            owner="Rahul",
            beneficiary="Ravi",
            action="Send the database benchmark numbers",
            deadline=overdue_deadline,
            conditions=None,
            evidence=[],
            status=ObligationStatus.OVERDUE,
            next_action="Ping Rahul on Slack for benchmark CSV",
            source_ref="Team Standup Notes",
            obligation_type=ObligationType.OWED_TO_ME,
            confidence={
                "overall": 0.96,
                "owner": 0.98,
                "beneficiary": 0.98,
                "action": 0.96,
                "deadline": 0.92,
                "conditions": 1.0,
                "obligation_type": 0.98
            }
        )

        # 2. Blocked Obligation A: Ravi owes Team: "Finish the project report" (BLOCKED by ob_b -> HIGH RISK)
        ob_a = Obligation(
            owner="Ravi",
            beneficiary="Team",
            action="Finish the project benchmark analysis report",
            deadline=friday_deadline,
            conditions="After Rahul provides the database numbers",
            evidence=[{
                "type": "graph_transition",
                "event": "OBLIGATION_BLOCKED",
                "reason": "Blocked by Rahul's overdue obligation: Send database benchmark numbers.",
                "recorded_at": now.isoformat(),
            }],
            status=ObligationStatus.BLOCKED,
            block_reason={
                "blocked": True,
                "blocked_by": [{
                    "owner": "Rahul",
                    "beneficiary": "Ravi",
                    "action": "Send the database benchmark numbers",
                    "status": "OVERDUE",
                    "reason": "Prerequisite obligation by Rahul is overdue.",
                }],
                "updated_at": now.isoformat(),
            },
            next_action="Waiting for Rahul to send benchmark numbers",
            source_ref="Engineering Sprint Board",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={
                "overall": 0.95,
                "owner": 1.0,
                "beneficiary": 0.95,
                "action": 0.95,
                "deadline": 0.90,
                "conditions": 0.95,
                "obligation_type": 1.0
            }
        )

        # 3. Dependent Obligation C: Ravi owes Leadership: "Submit final report" (Depends on ob_a)
        ob_c = Obligation(
            owner="Ravi",
            beneficiary="Executive Leadership",
            action="Submit final quarterly project report to executive leadership",
            deadline=next_week_deadline,
            conditions="Once project benchmark analysis report is complete",
            evidence=[],
            status=ObligationStatus.CONFIRMED,
            next_action="Draft executive summary once report is finished",
            source_ref="Sprint Milestone Plan",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.95}
        )

        # 4. Imminent Deadline (Critical Risk, START_WORK): Ravi owes Finance
        ob_imminent = Obligation(
            owner="Ravi",
            beneficiary="Finance Department",
            action="Submit quarterly tax compliance filings",
            deadline=six_hours_deadline,
            conditions=None,
            evidence=[],
            status=ObligationStatus.CONFIRMED,
            next_action="Attach audited Q3 expense spreadsheet",
            source_ref="Finance Advisory Notice",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.98}
        )

        # 5. Ownership Uncertainty (High Risk, ASSIGN_OWNER): "We" owe Enterprise Client
        ob_ambig = Obligation(
            owner="We",
            beneficiary="Acme Enterprise Client",
            action="Deliver custom SOC2 security compliance questionnaire",
            deadline=friday_deadline,
            conditions=None,
            evidence=[],
            status=ObligationStatus.CONFIRMED,
            next_action="Assign dedicated security lead",
            source_ref="Sales Deal Thread",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.65, "owner": 0.50}
        )

        # 6. Conditional Trigger (MONITOR_CONDITION): Deploy to production
        ob_cond = Obligation(
            owner="Ravi",
            beneficiary="DevOps Team",
            action="Deploy production v2.5 release build",
            deadline=None,
            conditions="Once staging QA signoff is complete",
            evidence=[],
            status=ObligationStatus.CONFIRMED,
            next_action="Monitor staging CI/CD test suite",
            source_ref="Release Pipeline Tracker",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 0.90}
        )

        # 7. Completed obligation example
        ob_comp = Obligation(
            owner="Ravi",
            beneficiary="Security Team",
            action="Rotate cloud production credentials",
            deadline=now - timedelta(days=3),
            conditions=None,
            evidence=[{"type": "audit_log", "text": "KMS Key rotation completed on AWS"}],
            status=ObligationStatus.COMPLETED,
            next_action="None (Archived)",
            source_ref="Security Ticket SEC-104",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 1.0}
        )

        session.add_all([ob_b, ob_a, ob_c, ob_imminent, ob_ambig, ob_cond, ob_comp])
        await session.flush()

        # Update block_reason with actual UUID of ob_b
        ob_a.block_reason = {
            "blocked": True,
            "blocked_by": [{
                "obligation_id": ob_b.id,
                "owner": ob_b.owner,
                "beneficiary": ob_b.beneficiary,
                "action": ob_b.action,
                "status": ob_b.status.value,
                "reason": "Prerequisite obligation by Rahul is overdue.",
            }],
            "updated_at": now.isoformat(),
        }

        # Create Dependency Edges
        edge1 = ObligationEdge(
            from_obligation_id=ob_a.id,
            to_obligation_id=ob_b.id,
            edge_type=EdgeType.DEPENDS_ON
        )
        edge2 = ObligationEdge(
            from_obligation_id=ob_c.id,
            to_obligation_id=ob_a.id,
            edge_type=EdgeType.DEPENDS_ON
        )
        session.add_all([edge1, edge2])
        await session.flush()

        # Seed Suggested Completion Evidence for ob_b (Rahul benchmark numbers)
        ev1 = Evidence(
            obligation_id=ob_b.id,
            evidence_type=EvidenceType.FILE,
            source_type="slack",
            source_ref="slack_seed_msg_501",
            content="Rahul attached benchmark_results.csv in #dev-database.",
            correlation_status=CorrelationStatus.SUGGESTED,
            correlation_confidence=0.94,
            semantic_role=EventSemanticRole.COMPLETION_SIGNAL,
            reasoning=[
                "Event sender 'Rahul' matches obligation owner 'Rahul'",
                "Event recipient 'Ravi' matches beneficiary",
                "Action entity 'benchmark numbers' matches attached 'benchmark_results.csv'",
                "Deliverable file artifact attached",
            ],
            extra_metadata={"attachments": [{"name": "benchmark_results.csv", "size": 4096}]},
            actor="Rahul",
            observed_at=now - timedelta(hours=2),
        )

        session.add(ev1)
        await session.commit()

        # Plan initial interventions for seeded scenarios
        await InterventionPlanner.plan_intervention(session, ob_b.id, force=True)
        await InterventionPlanner.plan_intervention(session, ob_a.id, force=True)
        await InterventionPlanner.plan_intervention(session, ob_ambig.id, force=True)
        await InterventionPlanner.plan_intervention(session, ob_imminent.id, force=True)
        await session.commit()

        logger.info("Database successfully seeded with Phase 6 canonical interventions, risk and obligation scenarios!")


if __name__ == "__main__":
    asyncio.run(seed_data())
