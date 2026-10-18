from src.sandbox.insurer_portal import submit_claim, get_status


def test_p01_references_are_sequential(tmp_path):
    db = str(tmp_path / "s.db")
    a = submit_claim("C1", "P3", 600, 525, "laptop", db)
    b = submit_claim("C2", "P3", 300, 100, "phone", db)
    assert (a["reference"], b["reference"]) == ("CLM-0001", "CLM-0002") and a["status"] == "received"


def test_p02_status_moves_forward_and_approves(tmp_path):
    db = str(tmp_path / "s.db")
    ref = submit_claim("C1", "P3", 600, 525, "laptop", db)["reference"]
    out = [get_status(ref, db) for _ in range(4)]
    assert [o["status"] for o in out] == ["received", "in_review", "approved", "approved"]
    assert out[2]["approved_amount"] == 525


def test_p03_zero_estimate_is_denied(tmp_path):
    db = str(tmp_path / "s.db")
    ref = submit_claim("C1", "P3", 800, 0, "stolen", db)["reference"]
    last = [get_status(ref, db) for _ in range(3)][-1]
    assert last["status"] == "denied" and last["approved_amount"] == 0


def test_p04_unknown_reference(tmp_path):
    db = str(tmp_path / "s.db")
    assert "error" in get_status("CLM-9999", db) and "error" in get_status("garbage", db)
