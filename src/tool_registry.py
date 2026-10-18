from src.tools.retrieve import ClauseIndex
from src.tools.coverage import get_coverage, list_policies
from src.tools.payout import calc_payout, check_claim_eligibility
from src.sandbox import insurer_portal
from src.schemas import ClaimInput

SCHEMAS = [
    {"name": "search_clauses",
     "description": "Search the policy clauses. Returns the most relevant clauses with policy_id, "
                    "clause number and exact text. Always call this before answering a coverage question.",
     "parameters": {"type": "object",
                    "properties": {"query": {"type": "string", "description": "Short search query in English"},
                                   "policy_id": {"type": "string", "description": "Optional: limit to one policy"}},
                    "required": ["query"]}},
    {"name": "get_coverage",
     "description": "Get the structured coverage numbers (limits, deductible, co-insurance, waiting period, "
                    "claim deadline, exclusions) of one policy.",
     "parameters": {"type": "object",
                    "properties": {"policy_id": {"type": "string"}},
                    "required": ["policy_id"]}},
]


_CLAIM_PROPS = {
    "claim_id": {"type": "string"},
    "coverage_type": {"type": "string", "description": "e.g. outpatient, inpatient, dental_emergency, accidental_damage, theft"},
    "incident_date": {"type": "string", "description": "YYYY-MM-DD"},
    "bill_amount": {"type": "number"},
    "description": {"type": "string"},
    "context": {"type": "object", "description": "Optional flags: accident, emergency (booleans), exclusion_flags (list), claim_date (YYYY-MM-DD)"},
}
_CLAIM_OBJ = {"type": "object", "properties": _CLAIM_PROPS, "required": ["claim_id", "coverage_type", "incident_date", "bill_amount"]}

CLAIM_SCHEMAS = [
    {"name": "check_claim_eligibility",
     "description": "Check waiting period, exclusions and claim deadline for a claim against the policies.",
     "parameters": {"type": "object", "properties": {"claim": _CLAIM_OBJ}, "required": ["claim"]}},
    {"name": "calc_payout",
     "description": "Estimate the payout and out-of-pocket amount for a claim. The first policy in policy_ids pays first.",
     "parameters": {"type": "object", "properties": {
         "claim": _CLAIM_OBJ,
         "policy_ids": {"type": "array", "items": {"type": "string"}},
         "usage": {"type": "object"}}, "required": ["claim"]}},
    {"name": "submit_claim_sandbox",
     "description": "Submit a claim to the SANDBOX insurer portal. The payout estimate is computed by the system, "
                    "never taken from the caller. Requires user confirmation in the app.",
     "parameters": {"type": "object", "properties": {
         "claim": _CLAIM_OBJ,
         "policy_ids": {"type": "array", "items": {"type": "string"}},
         "usage": {"type": "object"}}, "required": ["claim"]}},
    {"name": "get_claim_status",
     "description": "Get the status of a claim in the sandbox portal.",
     "parameters": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
]


def _select(policies, policy_ids):
    if not policy_ids:
        return policies
    by_id = {p.policy_id: p for p in policies}
    missing = [i for i in policy_ids if i not in by_id]
    if missing:
        raise ValueError(f"Unknown policy_id: {missing}")
    return [by_id[i] for i in policy_ids]


def build_tools(policies, sandbox_db: str = "sandbox.db") -> dict:
    """Peta nama tool -> fungsi."""
    index = ClauseIndex(policies)

    def _submit(claim, policy_ids=None, usage=None):
        """Estimasi dihitung ulang di sini dari data klaim. Angka dari model tidak pernah dipercaya."""
        c = ClaimInput.model_validate(claim)
        res = calc_payout(c, _select(policies, policy_ids), usage)
        if not res.per_policy:
            raise ValueError("No policy covers this type of claim.")
        payer = next((p.policy_id for p in res.per_policy if p.payout > 0), res.per_policy[0].policy_id)
        out = insurer_portal.submit_claim(c.claim_id, payer, c.bill_amount, res.total_payout,
                                          c.description or c.coverage_type, sandbox_db)
        return {**out, "policy_id": payer, "estimated_payout": res.total_payout}

    return {
        "calc_payout": lambda claim, policy_ids=None, usage=None: calc_payout(
            ClaimInput.model_validate(claim), _select(policies, policy_ids), usage).model_dump(mode="json"),
        "check_claim_eligibility": lambda claim, policy_ids=None: check_claim_eligibility(
            ClaimInput.model_validate(claim), _select(policies, policy_ids)),
        "submit_claim_sandbox": _submit,
        "get_claim_status": lambda reference: insurer_portal.get_status(reference, sandbox_db),
        "search_clauses": lambda query, policy_id=None: index.search(query, policy_id),
        "get_coverage": lambda policy_id: get_coverage(policies, policy_id),
        "list_policies": lambda: list_policies(policies),
    }
