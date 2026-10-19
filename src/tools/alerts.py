"""Peringatan proaktif yang deterministik: masa tunggu, akhir/pembaruan polis, dan tenggat klaim."""
from datetime import date, timedelta

from src.clock import today

from src.claims_flow import label


def _sev(days: int) -> str:
    return "urgent" if days <= 14 else "soon" if days <= 45 else "info"


def list_alerts(policies, on: date | None = None) -> list[dict]:
    on = on or today()
    alerts = []
    for p in policies:
        for c in p.coverages:
            if c.waiting_period_days and p.start_date:
                end = p.start_date + timedelta(days=c.waiting_period_days)
                left = (end - on).days
                if left > 0:
                    extra = " Accidents are covered during the wait." if c.emergency_waiver else ""
                    alerts.append({"kind": "waiting_period", "policy_id": p.policy_id, "date": end.isoformat(),
                                   "days_left": left, "severity": _sev(left),
                                   "title": f"{label(c.type)} is not fully active yet ({p.name})",
                                   "detail": f"The {c.waiting_period_days}-day waiting period ends on {end.isoformat()}.{extra}",
                                   "clause": c.source_clause})
        if p.end_date:
            left = (p.end_date - on).days
            if left < 0:
                alerts.append({"kind": "expired", "policy_id": p.policy_id, "date": p.end_date.isoformat(),
                               "days_left": left, "severity": "urgent", "title": f"{p.name} has ended",
                               "detail": f"Cover ended on {p.end_date.isoformat()}. New incidents are not covered.", "clause": None})
            elif left <= 60:
                alerts.append({"kind": "renewal", "policy_id": p.policy_id, "date": p.end_date.isoformat(),
                               "days_left": left, "severity": _sev(left), "title": f"{p.name} ends soon",
                               "detail": f"Cover ends on {p.end_date.isoformat()}. Decide whether to renew before then.", "clause": None})
    return sorted(alerts, key=lambda a: a["days_left"])


def list_deadlines(claim: dict, policies, on: date | None = None) -> list[dict]:
    """Tenggat pengajuan klaim untuk kejadian tertentu, per polis yang punya jenis cakupan itu."""
    on = on or today()
    incident = date.fromisoformat(str(claim["incident_date"]))
    out = []
    for p in policies:
        for c in p.coverages:
            if c.type == claim["coverage_type"] and c.claim_deadline_days is not None:
                dl = incident + timedelta(days=c.claim_deadline_days)
                left = (dl - on).days
                out.append({"policy_id": p.policy_id, "name": p.name, "deadline": dl.isoformat(),
                            "days_left": left, "severity": "urgent" if left <= 7 else "soon" if left <= 21 else "info",
                            "clause": c.source_clause})
    return sorted(out, key=lambda d: d["days_left"])
