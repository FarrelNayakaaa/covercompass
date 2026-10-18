from pathlib import Path
from src.data_loader import load_policies

DATA = Path(__file__).resolve().parent.parent / "data" / "golden"


def test_every_source_clause_exists():
    for p in load_policies(DATA):
        for c in p.coverages:
            assert c.source_clause in p.clauses, f"{p.policy_id}: {c.id}"


def test_policy_ids_are_unique():
    ids = [p.policy_id for p in load_policies(DATA)]
    assert len(ids) == len(set(ids))
