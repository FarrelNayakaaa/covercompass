from pathlib import Path

from src.data_loader import load_policies
from src.scenarios import run_scenarios

POL = load_policies(Path(__file__).resolve().parent.parent / "data" / "golden")


def row(r, rid):
    return next(x for x in r["rows"] if x["id"] == rid)


def test_scenarios_use_the_payout_engine():
    r = run_scenarios(POL)
    assert (row(r, "outpatient")["insurer_pays"], row(r, "outpatient")["you_pay"]) == (0.0, 250.0)   # di bawah deductible
    assert (row(r, "er")["insurer_pays"], row(r, "er")["you_pay"]) == (1200.0, 600.0)
    assert (row(r, "hospital")["insurer_pays"], row(r, "hospital")["you_pay"]) == (8700.0, 300.0)
    assert (row(r, "damage")["insurer_pays"], row(r, "damage")["you_pay"]) == (525.0, 75.0)
    assert (row(r, "dental")["insurer_pays"], row(r, "dental")["you_pay"]) == (500.0, 100.0)
    assert row(r, "outpatient")["note"]


def test_total_cost_of_risk_is_premiums_plus_expected_out_of_pocket():
    r = run_scenarios(POL)
    assert r["premiums"] == sum(p.premium_annual for p in POL)
    expected = sum(x["probability"] * x["you_pay"] for x in r["rows"])
    assert abs(r["expected_out_of_pocket"] - expected) < 0.01
    assert abs(r["total_cost_of_risk"] - (r["premiums"] + r["expected_out_of_pocket"])) < 0.01


def test_shortfall_against_emergency_fund():
    assert run_scenarios(POL, emergency_fund=500)["shortfall"] == 100.0       # terburuk: IGD, bayar 600
    assert run_scenarios(POL, emergency_fund=1500)["shortfall"] == 0.0


def test_uncovered_type_is_fully_out_of_pocket():
    sc = [{"id": "x", "label": "Space trip", "coverage_type": "space_travel", "bill": 1000, "probability": 0.5, "context": {}}]
    r = run_scenarios(POL, sc)
    assert r["rows"][0]["you_pay"] == 1000 and r["rows"][0]["note"]


def test_user_can_change_assumptions():
    sc = [{"id": "o", "label": "Visit", "coverage_type": "outpatient", "bill": 1000, "probability": 1.0, "context": {}}]
    assert run_scenarios(POL, sc)["rows"][0]["you_pay"] == 440.0            # (1000-300)*0.8=560 dibayar
