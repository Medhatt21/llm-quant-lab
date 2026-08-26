"""Tests for the knowledge graph seed data."""

from src.knowledge.graph_data import (
    ALGORITHM_NODES,
    DATA_TYPE_NODES,
    EDGES,
    HARDWARE_NODES,
    SCHEME_NODES,
)


def test_all_nodes_have_required_fields():
    """All node definitions should have id, label, category."""
    for nodes in [DATA_TYPE_NODES, HARDWARE_NODES, SCHEME_NODES, ALGORITHM_NODES]:
        for n in nodes:
            assert "id" in n, f"Missing id: {n}"
            assert "label" in n, f"Missing label: {n}"
            assert "category" in n, f"Missing category: {n}"


def test_all_edges_have_required_fields():
    """All edge definitions should have source_id, target_id, edge_type."""
    for e in EDGES:
        assert "source_id" in e, f"Missing source_id: {e}"
        assert "target_id" in e, f"Missing target_id: {e}"
        assert "edge_type" in e, f"Missing edge_type: {e}"


def test_all_edge_sources_exist():
    """All edge source_ids should reference existing nodes."""
    all_ids = set()
    for nodes in [DATA_TYPE_NODES, HARDWARE_NODES, SCHEME_NODES, ALGORITHM_NODES]:
        for n in nodes:
            all_ids.add(n["id"])

    for e in EDGES:
        assert e["source_id"] in all_ids, f"Unknown source: {e['source_id']}"
        assert e["target_id"] in all_ids, f"Unknown target: {e['target_id']}"


def test_minimum_node_counts():
    """Should have a reasonable number of nodes."""
    assert len(DATA_TYPE_NODES) >= 10
    assert len(HARDWARE_NODES) >= 5
    assert len(SCHEME_NODES) >= 5
    assert len(ALGORITHM_NODES) >= 10


def test_minimum_edge_count():
    """Should have enough edges to form a connected graph."""
    assert len(EDGES) >= 30
