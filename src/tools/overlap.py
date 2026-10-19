"""Deteksi premi ganda: jenis cakupan yang sama dimiliki lebih dari satu polis. Untuk tiap polis berikutnya
dihitung kapan ia benar-benar menambah uang yang dibayar, memakai mesin payout (bukan tebakan)."""
from datetime import date

from src.clock import today

from src.claims_flow import label, order_policies
from src.schemas import ClaimInput
from src.tools.payout import calc_payout

TYPICAL_BILL = 600.0
BILL_GRID = [float(b) for b in range(50, 5001, 50)]


def _payouts(policies, ordered_ids, ctype, bill):
    by_id = {p.policy_id: p for p in policies}
    claim = ClaimInput(claim_id="OVERLAP", coverage_type=ctype, incident_date=today(), bill_amount=bill,
                       context={"claim_date": today().isoformat()})
    res = calc_payout(claim, [by_id[i] for i in ordered_ids])
    return {p.policy_id: p.payout for p in res.per_policy}


def find_overlaps(policies, typical_bill: float = TYPICAL_BILL) -> dict:
    by_id = {p.policy_id: p for p in policies}
    overlaps, total_dup = [], 0.0
    for ctype in sorted({c.type for p in policies for c in p.coverages}):
        order = order_policies(policies, ctype)
        if len(order) < 2:
            continue
        typical = _payouts(policies, order, ctype, typical_bill)
        grid = {b: _payouts(policies, order, ctype, b) for b in BILL_GRID}
        items = []
        for i, pid in enumerate(order):
            cov = next(c for c in by_id[pid].coverages if c.type == ctype)
            above = None if i == 0 else next((b for b in BILL_GRID if grid[b][pid] > 0), None)
            items.append({"policy_id": pid, "name": by_id[pid].name, "pays_first": i == 0,
                          "deductible": cov.deductible, "limit_per_item": cov.limit_per_item,
                          "premium_portion": cov.premium_portion,
                          "typical_payout": typical[pid], "adds_money_above": above})
        dup = 0.0
        for it in items[1:]:
            if it["typical_payout"] == 0 and it["premium_portion"]:
                dup += it["premium_portion"]
                it["likely_duplicate"] = True
        total_dup += dup
        lines = []
        for it in items[1:]:
            if it["adds_money_above"] is None:
                lines.append(f"{it['name']} would pay nothing extra for any loss up to $5,000.")
            else:
                lines.append(f"{it['name']} only pays extra when the loss is above about ${it['adds_money_above']:,.0f}.")
        overlaps.append({"coverage_type": ctype, "label": label(ctype), "typical_bill": typical_bill,
                         "policies": items, "possible_duplicate_premium": dup,
                         "summary": f"{len(items)} policies cover this. {items[0]['name']} pays first. " + " ".join(lines)})
    return {"overlaps": overlaps, "possible_duplicate_premium": round(total_dup, 2),
            "note": "Order of payment is a simplification: the policy with the smallest deductible pays first. "
                    "A policy is flagged only when it adds nothing in a typical loss AND its premium is separate."}
