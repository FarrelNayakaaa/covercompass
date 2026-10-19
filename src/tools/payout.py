"""Mesin hitung payout. Deterministik, tanpa LLM.
Aturan ringkas (setiap langkah dicatat sebagai PayoutStep):
1 kelayakan -> 2 batas per barang -> 3 deductible -> 4 co-insurance -> 5 batas tahunan.
Polis kedua dst. hanya menghitung sisa kerugian (koordinasi disederhanakan)."""
from datetime import date, datetime

from src.schemas import ClaimInput, Coverage, Policy, PayoutResult, PayoutStep, PolicyPayout


def _to_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _money(x: float) -> float:
    return round(float(x) + 1e-9, 2)


def check_eligibility(claim: ClaimInput, policy: Policy, cov: Coverage) -> tuple[bool, str | None]:
    ctx = claim.context or {}
    hit = set(ctx.get("exclusion_flags", [])) & set(cov.exclusions)
    if hit:
        return False, f"Excluded: {', '.join(sorted(hit))}."
    if policy.start_date:
        days = (claim.incident_date - policy.start_date).days
        if days < 0:
            return False, "The incident happened before the cover start date."
        if cov.waiting_period_days and days < cov.waiting_period_days:
            waived = cov.emergency_waiver and (ctx.get("accident") or ctx.get("emergency"))
            if not waived:
                return False, (f"Waiting period of {cov.waiting_period_days} days is not over "
                               f"({days} days since cover start).")
    if policy.end_date and claim.incident_date > policy.end_date:
        return False, "The incident happened after the cover ended."
    if cov.claim_deadline_days is not None:
        claim_date = _to_date(ctx.get("claim_date")) or claim.incident_date
        late = (claim_date - claim.incident_date).days
        if late > cov.claim_deadline_days:
            return False, (f"Claim filed {late} days after the incident; "
                           f"the deadline is {cov.claim_deadline_days} days.")
    return True, None


def _calc_one(claim: ClaimInput, policy: Policy, cov: Coverage, loss: float, used: dict) -> PolicyPayout:
    clause = cov.source_clause
    steps: list[PayoutStep] = []
    ok, reason = check_eligibility(claim, policy, cov)
    if not ok:
        steps.append(PayoutStep(step="eligibility", amount=0.0, note=reason or "", clause=clause))
        return PolicyPayout(policy_id=policy.policy_id, eligible=False, reason=reason, payout=0.0, steps=steps)
    steps.append(PayoutStep(step="eligibility", note="Eligible.", clause=clause))

    eligible = loss
    if cov.limit_per_item is not None:
        eligible = min(eligible, cov.limit_per_item)
    eligible = max(0.0, eligible)
    steps.append(PayoutStep(step="limit", amount=_money(eligible),
                            note=f"Eligible amount after per-item limit ({cov.limit_per_item}).", clause=clause))

    if cov.deductible_scope == "annual":
        remaining = max(0.0, cov.deductible - float(used.get("deductible_met", 0)))
    else:
        remaining = cov.deductible
    cut = min(eligible, remaining)
    after = eligible - cut
    steps.append(PayoutStep(step="deductible", amount=_money(-cut),
                            note=f"Deductible applied: {_money(cut)} (remaining deductible was {_money(remaining)}).",
                            clause=clause))

    pay = after * cov.coinsurance
    steps.append(PayoutStep(step="coinsurance", amount=_money(pay),
                            note=f"Insurer pays {int(round(cov.coinsurance * 100))}% of {_money(after)}.", clause=clause))

    if cov.limit_annual is not None:
        cap = max(0.0, cov.limit_annual - float(used.get("annual_used", 0)))
        if pay > cap:
            steps.append(PayoutStep(step="annual_cap", amount=_money(cap),
                                    note=f"Reduced to the remaining annual limit ({_money(cap)}).", clause=clause))
        pay = min(pay, cap)

    pay = _money(pay)
    steps.append(PayoutStep(step="final", amount=pay, note="Estimated payout from this policy.", clause=clause))
    return PolicyPayout(policy_id=policy.policy_id, eligible=True, payout=pay, steps=steps)


def calc_payout(claim: ClaimInput, policies: list[Policy], usage: dict | None = None) -> PayoutResult:
    """policies = urutan siapa membayar duluan.
    usage = pemakaian tahun ini per coverage id, mis. {"cov_outpatient": {"deductible_met": 0, "annual_used": 0}}"""
    usage = usage or {}
    remaining_loss = float(claim.bill_amount)
    per_policy: list[PolicyPayout] = []
    for policy in policies:
        cov = next((c for c in policy.coverages if c.type == claim.coverage_type), None)
        if cov is None:
            continue
        res = _calc_one(claim, policy, cov, remaining_loss, usage.get(cov.id, {}))
        remaining_loss = max(0.0, remaining_loss - res.payout)
        per_policy.append(res)
    total = _money(sum(p.payout for p in per_policy))
    return PayoutResult(claim_id=claim.claim_id, total_bill=float(claim.bill_amount), total_payout=total,
                        out_of_pocket=_money(claim.bill_amount - total), per_policy=per_policy)


def check_claim_eligibility(claim: ClaimInput, policies: list[Policy]) -> list[dict]:
    out = []
    for policy in policies:
        cov = next((c for c in policy.coverages if c.type == claim.coverage_type), None)
        if cov is None:
            continue
        ok, reason = check_eligibility(claim, policy, cov)
        out.append({"policy_id": policy.policy_id, "eligible": ok, "reason": reason,
                    "clause": cov.source_clause, "claim_deadline_days": cov.claim_deadline_days})
    return out
