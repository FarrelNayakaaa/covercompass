from datetime import date
from pathlib import Path

from src.data_loader import load_policies
from src.schemas import ClaimInput, Coverage, Policy
from src.tools.payout import calc_payout, check_claim_eligibility

DATA = Path(__file__).resolve().parent.parent / "data" / "golden"
POL = {p.policy_id: p for p in load_policies(DATA)}


def claim(ctype, bill, incident=date(2026, 10, 1), **ctx):
    return ClaimInput(claim_id="C1", coverage_type=ctype, incident_date=incident, bill_amount=bill, context=ctx)


def fake_policy(pid, deductible=0.0, ctype="accidental_damage"):
    return Policy(policy_id=pid, name=pid, premium_annual=0,
                  coverages=[Coverage(id=pid + "_c", type=ctype, deductible=deductible, source_clause="1.1")],
                  clauses={"1.1": "x"})


def test_c01_outpatient_deductible_then_coinsurance():
    r = calc_payout(claim("outpatient", 350), [POL["P1_HEALTH"]])
    assert r.total_payout == 40 and r.out_of_pocket == 310


def test_c02_gadget_damage():
    r = calc_payout(claim("accidental_damage", 600), [POL["P3_GADGET"]])
    assert r.total_payout == 525 and r.out_of_pocket == 75


def test_c02b_second_policy_pays_only_remaining_loss():
    r = calc_payout(claim("accidental_damage", 600), [POL["P3_GADGET"], fake_policy("TRAVEL", 100)])
    assert r.total_payout == 525 and r.out_of_pocket == 75
    assert [p.payout for p in r.per_policy] == [525, 0]


def test_c04_annual_cap():
    usage = {"cov_outpatient": {"deductible_met": 300, "annual_used": 1990}}
    r = calc_payout(claim("outpatient", 350), [POL["P1_HEALTH"]], usage)
    assert r.total_payout == 10 and r.out_of_pocket == 340
    assert any(s.step == "annual_cap" for s in r.per_policy[0].steps)


def test_c05a_dental_waiting_period_blocks():
    pol = POL["P1_HEALTH"].model_copy(update={"start_date": date(2026, 9, 1)})
    r = calc_payout(claim("dental_emergency", 300), [pol])
    pp = r.per_policy[0]
    assert (pp.eligible, pp.payout) == (False, 0) and "Waiting period" in pp.reason
    assert r.out_of_pocket == 300


def test_c05b_dental_accident_waives_waiting_period():
    pol = POL["P1_HEALTH"].model_copy(update={"start_date": date(2026, 9, 1)})
    r = calc_payout(claim("dental_emergency", 300, accident=True), [pol])
    assert r.total_payout == 300 and r.per_policy[0].eligible


def test_c06_claim_deadline_missed():
    r = calc_payout(claim("accidental_damage", 600, incident=date(2026, 9, 1), claim_date="2026-10-17"),
                    [POL["P3_GADGET"]])
    assert not r.per_policy[0].eligible and r.total_payout == 0 and "deadline" in r.per_policy[0].reason


def test_c07_exclusion_blocks_and_control_case_pays():
    blocked = calc_payout(claim("theft", 800, exclusion_flags=["unattended"]), [POL["P3_GADGET"]])
    assert not blocked.per_policy[0].eligible and blocked.total_payout == 0
    ok = calc_payout(claim("theft", 800), [POL["P3_GADGET"]])
    assert ok.total_payout == 725


def test_c08_total_never_exceeds_bill():
    r = calc_payout(claim("accidental_damage", 100), [fake_policy("A"), fake_policy("B"), fake_policy("C")])
    assert r.total_payout == 100 and r.out_of_pocket == 0


def test_incident_before_cover_start_is_not_eligible():
    pol = POL["P3_GADGET"].model_copy(update={"start_date": date(2026, 10, 5)})
    r = calc_payout(claim("accidental_damage", 600), [pol])
    assert not r.per_policy[0].eligible


def test_every_step_names_a_clause():
    r = calc_payout(claim("outpatient", 350), [POL["P1_HEALTH"]])
    assert all(s.clause for s in r.per_policy[0].steps)


def test_unknown_coverage_type_pays_nothing():
    r = calc_payout(claim("space_travel", 500), list(POL.values()))
    assert r.total_payout == 0 and r.out_of_pocket == 500 and r.per_policy == []


def test_check_claim_eligibility_lists_policies():
    out = check_claim_eligibility(claim("theft", 800, exclusion_flags=["unattended"]), [POL["P3_GADGET"]])
    assert out == [{"policy_id": "P3_GADGET", "eligible": False, "reason": "Excluded: unattended.",
                    "clause": "4.1", "claim_deadline_days": 30}]
