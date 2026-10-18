from pathlib import Path
from src.data_loader import load_policies
from src.tools.retrieve import ClauseIndex

DATA = Path(__file__).resolve().parent.parent / "data" / "golden"


def idx():
    return ClauseIndex(load_policies(DATA))


def test_dental_waiting_period_found_first():
    top = idx().search("dental waiting period")[0]
    assert (top["policy_id"], top["clause"]) in {("P1_HEALTH", "6.2"), ("P1_HEALTH", "6.1")}


def test_policy_filter():
    res = idx().search("claim deadline", policy_id="P3_GADGET")
    assert res and all(r["policy_id"] == "P3_GADGET" for r in res)


def test_theft_unattended():
    top = idx().search("laptop stolen left unattended")[0]
    assert top["policy_id"] == "P3_GADGET" and top["clause"] == "4.1"


def test_nonsense_query_returns_nothing():
    assert idx().search("zzzz qqqq") == []


def test_sample_ignored_when_real_policy_exists(tmp_path):
    base = (DATA / "P3_GADGET.json").read_text()
    (tmp_path / "sample_a.json").write_text(base)
    (tmp_path / "REAL_ONE.json").write_text(base.replace("P3_GADGET", "REAL_ONE"))
    assert [p.policy_id for p in load_policies(tmp_path)] == ["REAL_ONE"]
