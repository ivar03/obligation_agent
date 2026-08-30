import asyncio
from datetime import datetime, timedelta, timezone
from app.core.database import AsyncSessionLocal, engine, Base
from app.core.status_machine import ObligationStatus, ObligationType, EdgeType
from app.models.obligation import Obligation, ObligationEdge
from app.core.logging import logger, setup_logging


async def seed_data():
    setup_logging()
    logger.info("Initializing database schema for seeding...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Clear existing seed data if any
        logger.info("Clearing previous records...")
        async with session.begin():
            await session.execute(ObligationEdge.__table__.delete())
            await session.execute(Obligation.__table__.delete())

        now = datetime.now(timezone.utc)
        friday_deadline = (now + timedelta(days=2)).replace(hour=17, minute=0, second=0, microsecond=0)
        overdue_deadline = (now - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        next_week_deadline = (now + timedelta(days=5)).replace(hour=18, minute=0, second=0, microsecond=0)

        # 1. Ravi owes Rahul: "Send the API documentation by Friday."
        ob1 = Obligation(
            owner="Ravi",
            beneficiary="Rahul",
            action="Send the API documentation",
            deadline=friday_deadline,
            conditions=None,
            evidence=[{"type": "note", "text": "Drafting markdown docs in repo"}],
            status=ObligationStatus.CONFIRMED,
            next_action="Finish endpoint specs in OpenAPI and email Rahul",
            source_ref="Slack DM from Rahul",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={
                "overall": 0.98,
                "owner": 1.0,
                "beneficiary": 1.0,
                "action": 0.98,
                "deadline": 0.95,
                "conditions": 1.0,
                "obligation_type": 1.0
            }
        )

        # 2. Professor owes Ravi: "Review the project report after Ravi submits it."
        ob2 = Obligation(
            owner="Professor Sharma",
            beneficiary="Ravi",
            action="Review the project report and provide grading feedback",
            deadline=next_week_deadline,
            conditions="After Ravi submits the final project PDF",
            evidence=[],
            status=ObligationStatus.CONFIRMED,
            next_action="Await submission confirmation from Ravi",
            source_ref="Academic Email Thread",
            obligation_type=ObligationType.OWED_TO_ME,
            confidence={
                "overall": 0.92,
                "owner": 0.95,
                "beneficiary": 0.95,
                "action": 0.90,
                "deadline": 0.85,
                "conditions": 0.95,
                "obligation_type": 0.95
            }
        )

        # 3. Ravi owes the client: "Send the revised proposal once the pricing numbers are confirmed."
        ob3 = Obligation(
            owner="Ravi",
            beneficiary="Acme Corp Client",
            action="Send the revised enterprise proposal",
            deadline=now + timedelta(hours=36),  # At risk: approaching within 48h
            conditions="Once pricing numbers are confirmed by finance",
            evidence=[],
            status=ObligationStatus.IN_PROGRESS,
            next_action="Follow up with finance for the revised pricing table",
            source_ref="Client Zoom Call Notes",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={
                "overall": 0.94,
                "owner": 0.98,
                "beneficiary": 0.90,
                "action": 0.95,
                "deadline": 0.85,
                "conditions": 0.92,
                "obligation_type": 0.98
            }
        )

        # 4. Rahul owes Ravi: "Send the database numbers before Ravi can finish the report."
        ob4 = Obligation(
            owner="Rahul",
            beneficiary="Ravi",
            action="Send the database benchmark numbers",
            deadline=overdue_deadline,  # At risk: Overdue
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

        # 5. An ambiguous obligation where ownership is unclear.
        ob5 = Obligation(
            owner="Unassigned / Team (Ambiguous)",
            beneficiary="Client Leadership",
            action="Send the quarterly risk analysis deck to client leadership",
            deadline=now + timedelta(days=1),
            conditions="Pending executive sign-off",
            evidence=[],
            status=ObligationStatus.CONFIRMED,
            next_action="Clarify owner in tomorrow morning's sync",
            source_ref="Leadership Email: 'We should probably send this to the client tomorrow'",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={
                "overall": 0.42,
                "owner": 0.30,
                "beneficiary": 0.50,
                "action": 0.70,
                "deadline": 0.80,
                "conditions": 0.40,
                "obligation_type": 0.45
            }
        )

        # 6. Completed obligation example
        ob6 = Obligation(
            owner="Ravi",
            beneficiary="Security Team",
            action="Rotate cloud production secrets",
            deadline=now - timedelta(days=3),
            conditions=None,
            evidence=[{"type": "audit_log", "text": "KMS Key rotation completed on AWS"}],
            status=ObligationStatus.COMPLETED,
            next_action="None (Archived)",
            source_ref="Security Ticket SEC-104",
            obligation_type=ObligationType.OWED_BY_ME,
            confidence={"overall": 1.0}
        )

        session.add_all([ob1, ob2, ob3, ob4, ob5, ob6])
        await session.flush()

        # Link obligations with an edge: Rahul sending database numbers (ob4) blocks Ravi finishing report (ob2 / ob1)
        edge1 = ObligationEdge(
            from_obligation_id=ob4.id,
            to_obligation_id=ob3.id,
            edge_type=EdgeType.DEPENDS_ON
        )
        edge2 = ObligationEdge(
            from_obligation_id=ob1.id,
            to_obligation_id=ob2.id,
            edge_type=EdgeType.LINKED
        )
        session.add_all([edge1, edge2])
        await session.commit()

        logger.info("Database successfully seeded with 6 canonical obligations and 2 dependency edges!")


if __name__ == "__main__":
    asyncio.run(seed_data())
