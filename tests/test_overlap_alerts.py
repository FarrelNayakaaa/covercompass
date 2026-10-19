from datetime import date
from pathlib import Path

from src.data_loader import load_policies
from src.tools.alerts import list_alerts, list_deadlines
from src.tools.overlap import find_overlaps

POL = load_policies(Path(__file__).resolve().parent.parent / "data" / "golden")
TODAY = date(2026, 10, 18)


def test_four_policies_are_loaded():
    assert [p.policy_id for p in POL] == ["P1_HEALTH", "P2_TRAVEL", "P3_GADGET", "P4_RENTERS"]


def test_accidental_damage_overlap_and_duplicate_premium():
    ov = find_overlaps(POL)
    ad = next(o for o in ov["overlaps"] if o["coverage_type"] == "accidental_damage")
    by = {i["policy_id"]: i for i in ad["policies"]}
    assert [i["policy_id"] for i in ad["policies"]] == ["P3_GADGET", "P2_TRAVEL", "P4_RENTERS"]
    assert by["P3_GADGET"]["pays_first"] and by["P3_GADGET"]["typical_payout"] == 525.0
    assert by["P2_TRAVEL"]["typical_payout"] == 0.0 and by["P4_RENTERS"]["typical_payout"] == 0.0
    assert by["P2_TRAVEL"]["adds_money_above"] == 1550 and by["P4_RENTERS"]["adds_money_above"] == 2100
    assert by["P4_RENTERS"].get("likely_duplicate") is True


def test_only_a_policy_with_a_separate_premium_is_flagged():
    ov = find_overlaps(POL)
    ad = next(o for o in ov["overlaps"] if o["coverage_type"] == "accidental_damage")
    assert not any(i.get("likely_duplicate") for i in ad["policies"] if i["policy_id"] == "P2_TRAVEL")
    assert ov["possible_duplicate_premium"] == 60.0


def test_no_overlap_for_types_held_once():
    types = {o["coverage_type"] for o in find_overlaps(POL)["overlaps"]}
    assert types == {"accidental_damage", "theft"}


def test_alerts_waiting_period_and_renewal_in_urgency_order():
    alerts = list_alerts(POL, TODAY)
    assert [a["kind"] for a in alerts] == ["waiting_period", "renewal"]
    assert alerts[0]["date"] == "2026-11-13" and alerts[0]["days_left"] == 26 and alerts[0]["severity"] == "soon"
    assert "Accidents are covered" in alerts[0]["detail"]
    assert alerts[1]["date"] == "2026-12-01" and alerts[1]["days_left"] == 44


def test_expired_policy_alert_and_no_cover_after_end():
    alerts = list_alerts(POL, date(2026, 12, 10))
    assert any(a["kind"] == "expired" and a["policy_id"] == "P3_GADGET" and a["severity"] == "urgent" for a in alerts)


def test_claim_deadlines_per_policy():
    d = list_deadlines({"incident_date": "2026-10-10", "coverage_type": "accidental_damage"}, POL, TODAY)
    assert [(x["policy_id"], x["deadline"], x["days_left"]) for x in d] == [
        ("P2_TRAVEL", "2026-11-09", 22), ("P3_GADGET", "2026-11-09", 22), ("P4_RENTERS", "2026-11-24", 37)]
