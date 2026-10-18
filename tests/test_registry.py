from pathlib import Path
from src.audit import Audit
from src.data_loader import load_policies
from src.tiers import Gate
from src.tool_registry import build_tools

DATA = Path(__file__).resolve().parent.parent / "data" / "golden"
CLAIM = {"claim_id": "C1", "coverage_type": "outpatient", "incident_date": "2026-10-01", "bill_amount": 350}


def make(tmp_path):
    pols = load_policies(DATA)
    audit = Audit(str(tmp_path / "a.db"))
    return Gate(build_tools(pols, str(tmp_path / "s.db")), audit), audit


def test_calc_payout_tool_returns_json_ready_dict(tmp_path):
    gate, _ = make(tmp_path)
    out = gate.execute("calc_payout", {"claim": CLAIM, "policy_ids": ["P1_HEALTH"]}, "s1")
    assert out["status"] == "ok" and out["result"]["total_payout"] == 40


def test_unknown_policy_id_is_a_clean_error(tmp_path):
    gate, _ = make(tmp_path)
    out = gate.execute("calc_payout", {"claim": CLAIM, "policy_ids": ["NOPE"]}, "s1")
    assert out["status"] == "error"


def test_w03_submit_needs_confirmation_then_status_works(tmp_path):
    gate, audit = make(tmp_path)
    args = {"claim_id": "C1", "policy_id": "P1_HEALTH", "amount_claimed": 350,
            "estimated_payout": 40, "summary": "outpatient visit"}
    pending = gate.execute("submit_claim_sandbox", args, "s1")
    assert pending["status"] == "awaiting_confirmation"
    done = gate.confirm(pending["pending_id"])
    ref = done["result"]["reference"]
    assert ref == "CLM-0001"
    assert gate.execute("get_claim_status", {"reference": ref}, "s1")["result"]["status"] == "received"
    assert audit.rows("s1")[-1]["tier"] == "T0"
