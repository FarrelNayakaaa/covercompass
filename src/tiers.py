import uuid
from enum import Enum


class Tier(str, Enum):
    T0 = "T0"   # baca / hitung: otomatis
    T1 = "T1"   # aksi simulasi: wajib konfirmasi pengguna
    T2 = "T2"   # terlarang: selalu ditolak


TOOL_TIERS = {
    # T0
    "search_clauses": Tier.T0, "get_coverage": Tier.T0,
    "check_claim_eligibility": Tier.T0, "calc_payout": Tier.T0,
    "run_scenario": Tier.T0, "exposure_map": Tier.T0, "find_overlaps": Tier.T0,
    "list_deadlines": Tier.T0, "build_claim_pack": Tier.T0,
    # T1
    "submit_claim_sandbox": Tier.T1, "schedule_premium_payment": Tier.T1,
    "set_alert": Tier.T1, "apply_policy_change_sandbox": Tier.T1,
    # T2 (tidak punya implementasi, selalu ditolak)
    "submit_to_real_insurer": Tier.T2, "buy_or_cancel_policy_real": Tier.T2,
    "transfer_real_money": Tier.T2, "guarantee_payout": Tier.T2,
    "edit_document_dates": Tier.T2, "request_credentials": Tier.T2,
}


class Gate:
    """Gerbang tunggal ke semua tool. Konfirmasi T1 hanya lewat confirm(), yang
    dipanggil tombol UI, bukan argumen yang bisa diisi LLM."""

    def __init__(self, tools: dict, audit):
        self.tools = tools
        self.audit = audit
        self.pending: dict[str, tuple] = {}

    def execute(self, name: str, args: dict, session_id: str) -> dict:
        args = args or {}
        tier = TOOL_TIERS.get(name)
        if tier is None:  # default deny
            self.audit.log(session_id, "tier_decision", name, None, "blocked",
                           summary="unknown tool", outcome="blocked", args=args)
            return {"status": "blocked", "reason": "Unknown tool."}
        if tier == Tier.T2:
            self.audit.log(session_id, "tier_decision", name, "T2", "blocked",
                           summary="known risk: forbidden action", outcome="blocked", args=args)
            return {"status": "blocked", "reason": "This action is not allowed."}
        if tier == Tier.T0:
            return self._run(name, args, session_id, "T0", confirmed=False, event="tool_call")
        pid = str(uuid.uuid4())  # T1: tahan sampai pengguna konfirmasi
        self.pending[pid] = (name, args, session_id)
        self.audit.log(session_id, "tier_decision", name, "T1", "awaiting_confirmation",
                       summary="waiting for user confirmation", outcome="pending", args=args)
        return {"status": "awaiting_confirmation", "pending_id": pid, "tool": name, "args": args}

    def confirm(self, pending_id: str) -> dict:
        item = self.pending.pop(pending_id, None)
        if item is None:
            return {"status": "error", "reason": "No such pending action."}
        name, args, session_id = item
        return self._run(name, args, session_id, "T1", confirmed=True, event="confirmation")

    def reject(self, pending_id: str) -> dict:
        item = self.pending.pop(pending_id, None)
        if item is None:
            return {"status": "error", "reason": "No such pending action."}
        name, args, session_id = item
        self.audit.log(session_id, "confirmation", name, "T1", "rejected_by_user",
                       summary="user declined", outcome="cancelled", args=args)
        return {"status": "cancelled"}

    def _run(self, name, args, session_id, tier, confirmed, event):
        fn = self.tools.get(name)
        if fn is None:
            self.audit.log(session_id, event, name, tier, "error", user_confirmed=confirmed,
                           summary="tool not implemented", outcome="error", args=args)
            return {"status": "error", "reason": "Tool not implemented."}
        try:
            result = fn(**args)
        except Exception as e:
            self.audit.log(session_id, event, name, tier, "error", user_confirmed=confirmed,
                           summary=f"{type(e).__name__}: {e}", outcome="error", args=args)
            return {"status": "error", "reason": f"{type(e).__name__}: {e}"}
        self.audit.log(session_id, event, name, tier, "allowed", user_confirmed=confirmed,
                       summary="ok", outcome="ok", args=args)
        return {"status": "ok", "result": result}
