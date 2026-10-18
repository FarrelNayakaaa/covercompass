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
    args = {"claim": CLAIM, "policy_ids": ["P1_HEALTH"]}
    pending = gate.execute("submit_claim_sandbox", args, "s1")
    assert pending["status"] == "awaiting_confirmation"
    done = gate.confirm(pending["pending_id"])
    out = done["result"]
    assert out["reference"] == "CLM-0001" and out["estimated_payout"] == 40 and out["policy_id"] == "P1_HEALTH"
    statuses = [gate.execute("get_claim_status", {"reference": out["reference"]}, "s1")["result"] for _ in range(3)]
    assert [x["status"] for x in statuses] == ["received", "in_review", "approved"]
    assert statuses[-1]["approved_amount"] == 40      # angka dari kalkulator, bukan dari model
    assert audit.rows("s1")[-1]["tier"] == "T0"


def test_model_cannot_inject_its_own_payout_amount(tmp_path):
    gate, audit = make(tmp_path)
    args = {"claim": CLAIM, "policy_ids": ["P1_HEALTH"], "estimated_payout": 99999, "amount_claimed": 99999}
    pending = gate.execute("submit_claim_sandbox", args, "s1")
    done = gate.confirm(pending["pending_id"])
    assert done["status"] == "error"                   # argumen asing ditolak
    status = gate.execute("get_claim_status", {"reference": "CLM-0001"}, "s1")["result"]
    assert "error" in status                           # tidak ada klaim yang tersimpan


def test_submit_without_matching_cover_is_clean_error(tmp_path):
    gate, _ = make(tmp_path)
    claim = dict(CLAIM, coverage_type="space_travel")
    pending = gate.execute("submit_claim_sandbox", {"claim": claim}, "s1")
    assert gate.confirm(pending["pending_id"])["status"] == "error"
