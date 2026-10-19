"""Berapa uang yang benar-benar dilindungi? Menjalankan skenario kejadian umum melalui mesin payout
dan menghitung Total Cost of Risk (TCR) = premi tahunan + expected out-of-pocket (EOOP).
Probabilitas di sini adalah ASUMSI untuk simulasi, bukan statistik atau hitungan aktuaria."""
from datetime import date

from src.claims_flow import order_policies
from src.schemas import ClaimInput
from src.tools.payout import calc_payout

DEFAULT_SCENARIOS = [
    {"id": "outpatient", "label": "Doctor visit", "coverage_type": "outpatient", "bill": 250.0,
     "probability": 0.60, "context": {}},
    {"id": "er", "label": "Emergency room visit", "coverage_type": "outpatient", "bill": 1800.0,
     "probability": 0.08, "context": {"emergency": True}},
    {"id": "hospital", "label": "Hospital stay (3 days)", "coverage_type": "inpatient", "bill": 9000.0,
     "probability": 0.02, "context": {}},
    {"id": "dental", "label": "Emergency dental after an accident", "coverage_type": "dental_emergency",
     "bill": 600.0, "probability": 0.05, "context": {"accident": True}},
    {"id": "damage", "label": "Laptop damaged by accident", "coverage_type": "accidental_damage",
     "bill": 600.0, "probability": 0.10, "context": {}},
    {"id": "theft", "label": "Phone stolen (locked away or on you)", "coverage_type": "theft",
     "bill": 1200.0, "probability": 0.05, "context": {}},
]


def run_scenarios(policies, scenarios=None, emergency_fund: float = 1500.0, today: date | None = None) -> dict:
    today = today or date.today()
    by_id = {p.policy_id: p for p in policies}
    rows = []
    for s in (scenarios or DEFAULT_SCENARIOS):
        order = order_policies(policies, s["coverage_type"])
        bill = float(s["bill"])
        if order:
            ctx = dict(s.get("context") or {}, claim_date=today.isoformat())
            claim = ClaimInput(claim_id=f"SIM-{s['id']}", coverage_type=s["coverage_type"],
                               incident_date=today, bill_amount=bill, context=ctx)
            res = calc_payout(claim, [by_id[i] for i in order])
            payout, oop = res.total_payout, res.out_of_pocket
            payers = [by_id[p.policy_id].name for p in res.per_policy if p.payout > 0]
            why = None
            if not payers:
                why = next((p.reason for p in res.per_policy if not p.eligible and p.reason),
                           "The bill is below your deductible, so you pay all of it.")
        else:
            payout, oop, payers, why = 0.0, bill, [], "No policy has this kind of cover."
        rows.append({"id": s["id"], "label": s["label"], "bill": bill, "probability": float(s["probability"]),
                     "insurer_pays": round(payout, 2), "you_pay": round(oop, 2),
                     "paid_by": payers, "note": why})
    premiums = round(sum(p.premium_annual for p in policies), 2)
    eoop = round(sum(r["probability"] * r["you_pay"] for r in rows), 2)
    worst = max(rows, key=lambda r: r["you_pay"]) if rows else None
    shortfall = round(max(0.0, (worst["you_pay"] if worst else 0) - emergency_fund), 2)
    return {"rows": rows, "premiums": premiums, "expected_out_of_pocket": eoop,
            "total_cost_of_risk": round(premiums + eoop, 2), "worst_case": worst,
            "emergency_fund": emergency_fund, "shortfall": shortfall,
            "note": "Probabilities are assumptions for simulation, not statistics. Each scenario is "
                    "evaluated on its own with no earlier claims this year."}
