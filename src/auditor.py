import re
from src.schemas import QAAnswer


def _norm(s: str) -> str:
    s = s.lower().replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"\.\.\.|\u2026", " ", s)
    s = re.sub(r"[^a-z0-9$%.,' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip(" .,'\"")


def verify_answer(answer: QAAnswer, policies_by_id: dict) -> list[str]:
    """Mengembalikan daftar masalah. Kosong = lolos."""
    problems = []
    if answer.verdict != "cannot_confirm" and not answer.citations:
        problems.append("A coverage verdict needs at least one citation.")
    for c in answer.citations:
        p = policies_by_id.get(c.policy_id)
        if p is None:
            problems.append(f"Unknown policy_id '{c.policy_id}'.")
            continue
        text = p.clauses.get(c.clause)
        if text is None:
            problems.append(f"Clause {c.clause} does not exist in {c.policy_id}.")
            continue
        q = _norm(c.quote)
        if not q or q not in _norm(text):
            problems.append(f"Quote not found in {c.policy_id} clause {c.clause}: '{c.quote[:60]}'.")
    return problems
