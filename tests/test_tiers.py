import pytest
from src.audit import Audit
from src.tiers import Gate, TOOL_TIERS, Tier


@pytest.fixture
def setup(tmp_path):
    calls = {"n": 0}

    def search_clauses(query):          # T0
        return f"found:{query}"

    def submit_claim_sandbox(claim_id):  # T1
        calls["n"] += 1
        return f"submitted:{claim_id}"

    audit = Audit(str(tmp_path / "audit.db"))
    gate = Gate({"search_clauses": search_clauses, "submit_claim_sandbox": submit_claim_sandbox}, audit)
    return gate, audit, calls


def test_t01_t0_runs_and_is_logged(setup):
    gate, audit, _ = setup
    out = gate.execute("search_clauses", {"query": "dental"}, "s1")
    assert out == {"status": "ok", "result": "found:dental"}
    assert audit.rows("s1")[-1]["tier"] == "T0"


def test_t02_t1_without_confirmation_does_not_run(setup):
    gate, audit, calls = setup
    out = gate.execute("submit_claim_sandbox", {"claim_id": "C1"}, "s1")
    assert out["status"] == "awaiting_confirmation"
    assert calls["n"] == 0
    assert audit.rows("s1")[-1]["decision"] == "awaiting_confirmation"


def test_t03_t1_runs_once_after_confirm(setup):
    gate, audit, calls = setup
    pid = gate.execute("submit_claim_sandbox", {"claim_id": "C1"}, "s1")["pending_id"]
    out = gate.confirm(pid)
    assert out == {"status": "ok", "result": "submitted:C1"}
    assert calls["n"] == 1
    last = audit.rows("s1")[-1]
    assert last["user_confirmed"] == 1 and last["event"] == "confirmation"
    assert gate.confirm(pid)["status"] == "error"   # tidak bisa dikonfirmasi dua kali
    assert calls["n"] == 1


def test_t1_reject_never_runs(setup):
    gate, audit, calls = setup
    pid = gate.execute("submit_claim_sandbox", {"claim_id": "C1"}, "s1")["pending_id"]
    assert gate.reject(pid)["status"] == "cancelled"
    assert calls["n"] == 0


def test_t04_all_t2_tools_blocked_even_if_function_exists(tmp_path):
    audit = Audit(str(tmp_path / "a.db"))
    t2 = [n for n, t in TOOL_TIERS.items() if t == Tier.T2]
    assert len(t2) == 6
    gate = Gate({n: (lambda **k: "DANGER") for n in t2}, audit)   # bahkan jika fungsinya ada
    for name in t2:
        out = gate.execute(name, {}, "s1")
        assert out["status"] == "blocked"
    assert all(r["decision"] == "blocked" for r in audit.rows("s1"))


def test_unknown_tool_is_blocked(setup):
    gate, audit, _ = setup
    assert gate.execute("rm_rf_everything", {}, "s1")["status"] == "blocked"


def test_tool_error_is_caught_and_logged(setup):
    gate, audit, _ = setup
    out = gate.execute("search_clauses", {"wrong_arg": 1}, "s1")
    assert out["status"] == "error"
    assert audit.rows("s1")[-1]["outcome"] == "error"
