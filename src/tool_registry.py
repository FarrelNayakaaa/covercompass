from src.tools.retrieve import ClauseIndex
from src.tools.coverage import get_coverage, list_policies

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


def build_tools(policies) -> dict:
    """Peta nama tool -> fungsi. Tool baru (payout, klaim, dll.) ditambahkan di sini."""
    index = ClauseIndex(policies)
    return {
        "search_clauses": lambda query, policy_id=None: index.search(query, policy_id),
        "get_coverage": lambda policy_id: get_coverage(policies, policy_id),
        "list_policies": lambda: list_policies(policies),
    }
