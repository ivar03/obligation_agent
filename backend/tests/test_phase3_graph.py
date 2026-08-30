import pytest
from httpx import AsyncClient
from app.core.status_machine import ObligationStatus, EdgeType


@pytest.mark.asyncio
async def test_1_create_depends_on_edge(client: AsyncClient):
    """Test 1: Create two obligations and connect with DEPENDS_ON."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Finish the report", "obligation_type": "OWED_BY_ME"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send database benchmark numbers", "obligation_type": "OWED_TO_ME"
    })).json()

    edge_res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"],
        "to_obligation_id": ob_b["id"],
        "edge_type": EdgeType.DEPENDS_ON.value,
    })
    assert edge_res.status_code == 201
    edge = edge_res.json()
    assert edge["from_obligation_id"] == ob_a["id"]
    assert edge["to_obligation_id"] == ob_b["id"]
    assert edge["edge_type"] == "DEPENDS_ON"


@pytest.mark.asyncio
async def test_2_duplicate_edge_rejection(client: AsyncClient):
    """Test 2: Duplicate identical edge must be rejected."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Task A", "obligation_type": "OWED_BY_ME"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Task B", "obligation_type": "OWED_TO_ME"
    })).json()

    # Create first
    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })
    # Attempt duplicate
    dup_res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })
    assert dup_res.status_code == 409


@pytest.mark.asyncio
async def test_3_self_dependency_rejection(client: AsyncClient):
    """Test 3: An obligation cannot depend on itself."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Self Task", "obligation_type": "OWED_BY_ME"
    })).json()

    res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_a["id"], "edge_type": "DEPENDS_ON"
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_4_simple_blocking_propagation(client: AsyncClient):
    """Test 4: A DEPENDS_ON B; B becomes OVERDUE -> A becomes BLOCKED with structured reason."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Finish the report", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send database benchmark numbers", "obligation_type": "OWED_TO_ME", "status": "IN_PROGRESS"
    })).json()

    # Link dependency: A depends on B
    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })

    # Transition B -> OVERDUE
    await client.patch(f"/api/obligations/{ob_b['id']}/status", json={"status": "OVERDUE"})

    # Check A: should now be BLOCKED
    ob_a_updated = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_updated["status"] == "BLOCKED"
    assert ob_a_updated["block_reason"] is not None
    assert ob_a_updated["block_reason"]["blocked"] is True
    assert len(ob_a_updated["block_reason"]["blocked_by"]) == 1
    assert ob_a_updated["block_reason"]["blocked_by"][0]["owner"] == "Rahul"


@pytest.mark.asyncio
async def test_5_simple_unblocking_propagation(client: AsyncClient):
    """Test 5: B becomes COMPLETED -> A automatically unblocks back to CONFIRMED."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Finish report 5", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Send numbers 5", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()

    # A depends on B (which is already OVERDUE, so A immediately becomes BLOCKED)
    await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"
    })
    ob_a_blocked = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_blocked["status"] == "BLOCKED"

    # Now B completes
    await client.patch(f"/api/obligations/{ob_b['id']}/status", json={
        "status": "COMPLETED", "evidence": {"text": "CSV sent"}
    })

    # A should now be unblocked back to CONFIRMED
    ob_a_unblocked = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_unblocked["status"] == "CONFIRMED"
    assert ob_a_unblocked["block_reason"] is None


@pytest.mark.asyncio
async def test_6_multi_dependency_blocking(client: AsyncClient):
    """Test 6: A depends on B and C. B completed, C overdue -> A remains BLOCKED."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Client", "action": "Submit proposal", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Finance", "beneficiary": "Ravi", "action": "Pricing approval", "obligation_type": "OWED_TO_ME", "status": "CONFIRMED"
    })).json()
    ob_c = (await client.post("/api/obligations", json={
        "owner": "Legal", "beneficiary": "Ravi", "action": "Terms review", "obligation_type": "OWED_TO_ME", "status": "CONFIRMED"
    })).json()

    # A depends on B and C
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_c["id"], "edge_type": "DEPENDS_ON"})

    # Complete B
    await client.patch(f"/api/obligations/{ob_b['id']}/status", json={"status": "COMPLETED"})
    # Mark C Overdue
    await client.patch(f"/api/obligations/{ob_c['id']}/status", json={"status": "OVERDUE"})

    # A must be BLOCKED by C
    ob_a_check = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_check["status"] == "BLOCKED"
    assert len(ob_a_check["block_reason"]["blocked_by"]) == 1
    assert ob_a_check["block_reason"]["blocked_by"][0]["owner"] == "Legal"


@pytest.mark.asyncio
async def test_7_multi_dependency_recovery(client: AsyncClient):
    """Test 7: When C finally completes as well, A unblocks."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Client", "action": "Submit proposal 7", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Finance", "beneficiary": "Ravi", "action": "Pricing 7", "obligation_type": "OWED_TO_ME", "status": "COMPLETED"
    })).json()
    ob_c = (await client.post("/api/obligations", json={
        "owner": "Legal", "beneficiary": "Ravi", "action": "Terms 7", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()

    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_c["id"], "edge_type": "DEPENDS_ON"})

    ob_a_check = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_check["status"] == "BLOCKED"

    # Now complete C
    await client.patch(f"/api/obligations/{ob_c['id']}/status", json={"status": "COMPLETED"})

    ob_a_unblocked = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_unblocked["status"] == "CONFIRMED"
    assert ob_a_unblocked["block_reason"] is None


@pytest.mark.asyncio
async def test_8_linked_obligations_non_blocking(client: AsyncClient):
    """Test 8: LINKED relationship connects obligations without causing blocking."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Send report", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Review report", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()

    # Create LINKED edge
    edge_res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "LINKED"
    })
    assert edge_res.status_code == 201

    # Verify A does NOT become blocked because LINKED is non-blocking
    ob_a_check = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_check["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_9_reciprocal_obligations(client: AsyncClient):
    """Test 9: Reciprocal obligations remain distinct records that can be linked."""
    ob1 = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Duty 1", "obligation_type": "OWED_BY_ME"
    })).json()
    ob2 = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Duty 2", "obligation_type": "OWED_TO_ME"
    })).json()

    assert ob1["id"] != ob2["id"]
    edge_res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob1["id"], "to_obligation_id": ob2["id"], "edge_type": "LINKED"
    })
    assert edge_res.status_code == 201


@pytest.mark.asyncio
async def test_10_dependency_cycle_rejection(client: AsyncClient):
    """Test 10: Dependency cycle A -> B -> C -> A must be rejected."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "A", "beneficiary": "B", "action": "Act A", "obligation_type": "OWED_BY_ME"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "B", "beneficiary": "C", "action": "Act B", "obligation_type": "OWED_BY_ME"
    })).json()
    ob_c = (await client.post("/api/obligations", json={
        "owner": "C", "beneficiary": "A", "action": "Act C", "obligation_type": "OWED_BY_ME"
    })).json()

    # A depends on B
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})
    # B depends on C
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_b["id"], "to_obligation_id": ob_c["id"], "edge_type": "DEPENDS_ON"})

    # Attempt C depends on A (creates cycle A -> B -> C -> A)
    cycle_res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": ob_c["id"], "to_obligation_id": ob_a["id"], "edge_type": "DEPENDS_ON"
    })
    assert cycle_res.status_code == 400
    assert "cycle" in cycle_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_11_chain_propagation(client: AsyncClient):
    """Test 11: Chain propagation: A -> B -> C; C overdue -> B blocked -> A blocked."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Client", "action": "Step A", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Alex", "beneficiary": "Ravi", "action": "Step B", "obligation_type": "OWED_TO_ME", "status": "CONFIRMED"
    })).json()
    ob_c = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Alex", "action": "Step C", "obligation_type": "OWED_TO_ME", "status": "CONFIRMED"
    })).json()

    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_b["id"], "to_obligation_id": ob_c["id"], "edge_type": "DEPENDS_ON"})

    # C becomes OVERDUE
    await client.patch(f"/api/obligations/{ob_c['id']}/status", json={"status": "OVERDUE"})

    # Both B and A should become BLOCKED
    ob_b_check = (await client.get(f"/api/obligations/{ob_b['id']}")).json()
    ob_a_check = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_b_check["status"] == "BLOCKED"
    assert ob_a_check["status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_12_unblock_chain_propagation(client: AsyncClient):
    """Test 12: C completes -> B unblocks -> when B completes -> A unblocks."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Client", "action": "Step A 12", "obligation_type": "OWED_BY_ME", "status": "CONFIRMED"
    })).json()
    ob_b = (await client.post("/api/obligations", json={
        "owner": "Alex", "beneficiary": "Ravi", "action": "Step B 12", "obligation_type": "OWED_TO_ME", "status": "CONFIRMED"
    })).json()
    ob_c = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Alex", "action": "Step C 12", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()

    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_b["id"], "edge_type": "DEPENDS_ON"})
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_b["id"], "to_obligation_id": ob_c["id"], "edge_type": "DEPENDS_ON"})

    # C completes
    await client.patch(f"/api/obligations/{ob_c['id']}/status", json={"status": "COMPLETED"})

    # B unblocks to CONFIRMED
    ob_b_check = (await client.get(f"/api/obligations/{ob_b['id']}")).json()
    assert ob_b_check["status"] == "CONFIRMED"

    # Complete B as well
    await client.patch(f"/api/obligations/{ob_b['id']}/status", json={"status": "COMPLETED"})

    # A unblocks to CONFIRMED
    ob_a_check = (await client.get(f"/api/obligations/{ob_a['id']}")).json()
    assert ob_a_check["status"] == "CONFIRMED"
    assert ob_a_check["block_reason"] is None


@pytest.mark.asyncio
async def test_13_invalid_obligation_id(client: AsyncClient):
    """Test 13: Non-existent obligation ID in edge creation returns 404."""
    res = await client.post("/api/obligations/edges", json={
        "from_obligation_id": "00000000-0000-0000-0000-000000000000",
        "to_obligation_id": "11111111-1111-1111-1111-111111111111",
        "edge_type": "DEPENDS_ON"
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_14_get_obligation_graph_composite(client: AsyncClient):
    """Test 14: GET /api/obligations/{id}/graph returns composite graph metadata."""
    ob_a = (await client.post("/api/obligations", json={
        "owner": "Ravi", "beneficiary": "Rahul", "action": "Graph Target", "obligation_type": "OWED_BY_ME"
    })).json()
    ob_dep = (await client.post("/api/obligations", json={
        "owner": "Rahul", "beneficiary": "Ravi", "action": "Prerequisite", "obligation_type": "OWED_TO_ME", "status": "OVERDUE"
    })).json()
    ob_link = (await client.post("/api/obligations", json={
        "owner": "Sarah", "beneficiary": "Ravi", "action": "Related Task", "obligation_type": "OWED_TO_ME"
    })).json()

    # Create edges
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_dep["id"], "edge_type": "DEPENDS_ON"})
    await client.post("/api/obligations/edges", json={"from_obligation_id": ob_a["id"], "to_obligation_id": ob_link["id"], "edge_type": "LINKED"})

    graph_res = await client.get(f"/api/obligations/{ob_a['id']}/graph")
    assert graph_res.status_code == 200
    g = graph_res.json()
    assert g["obligation"]["id"] == ob_a["id"]
    assert len(g["dependencies"]) == 1
    assert g["dependencies"][0]["id"] == ob_dep["id"]
    assert len(g["linked"]) == 1
    assert g["linked"][0]["id"] == ob_link["id"]
    assert len(g["blockers"]) == 1
    assert g["blockers"][0]["owner"] == "Rahul"
    assert g["is_blocked"] is True
