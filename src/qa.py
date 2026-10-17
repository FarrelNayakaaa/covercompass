import json, re
from src.orchestrator import run_turn, SYSTEM_PROMPT
from src.schemas import QAAnswer
from src.tool_registry import SCHEMAS
from src.auditor import verify_answer

QA_PROMPT = SYSTEM_PROMPT + (
    " Answer coverage questions ONLY from the policy text returned by tools. Call search_clauses first "
    "(and get_coverage if you need numbers). Then reply with ONLY a JSON object, no markdown, with keys: "
    "verdict (covered | not_covered | depends | cannot_confirm), plain_summary, conditions (list of strings), "
    "citations (list of {policy_id, clause, quote}), confidence (high | medium | low), ask_insurer_script "
    "(string or null). Each quote must be copied EXACTLY from the clause text returned by the tool, as one "
    "contiguous phrase of at most 25 words. If the policy text does not support an answer, use cannot_confirm "
    "with no citations and write a question the user could ask the insurer."
)


def _parse(text: str) -> QAAnswer:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("No JSON object in reply.")
    return QAAnswer.model_validate(json.loads(m.group(0)))


def _abstain(question: str, why: str) -> QAAnswer:
    return QAAnswer(
        verdict="cannot_confirm", confidence="low",
        plain_summary="I couldn't verify an answer against the policy text, so I won't guess. " + why,
        ask_insurer_script=f"Could you confirm in writing whether this is covered, and under which clause: {question}")


def answer_question(question, gate, policies_by_id, session_id, chat_fn=None, history=None):
    """Mengembalikan (QAAnswer, steps, pending). Jawaban harus lolos verifikasi sitasi, maksimal 2 percobaan."""
    audit = gate.audit
    steps, pending, msgs = [], [], list(history or [])
    prompt = question
    last_problem = "Verification failed."
    for attempt in range(2):
        out = run_turn(prompt, msgs, session_id, gate, SCHEMAS, QA_PROMPT, chat_fn)
        steps += out["steps"]; pending += out["pending"]; msgs = out["messages"]
        try:
            ans = _parse(out["text"])
        except Exception as e:
            last_problem = f"Reply was not valid JSON ({type(e).__name__})."
            audit.log(session_id, "auditor_result", decision="failed", summary=last_problem, outcome="retry")
            prompt = f"Your reply was not valid JSON for the required schema ({last_problem}). Reply again with ONLY the JSON object."
            continue
        problems = verify_answer(ans, policies_by_id)
        if not problems:
            audit.log(session_id, "auditor_result", decision="passed", summary=f"verdict={ans.verdict}")
            return ans, steps, pending
        last_problem = " ".join(problems)
        audit.log(session_id, "auditor_result", decision="failed", summary=last_problem[:300], outcome="retry")
        prompt = ("Your answer failed citation verification: " + last_problem +
                  " Re-read the clauses with search_clauses and answer again with exact quotes, "
                  "or use cannot_confirm if the text does not support an answer.")
    audit.log(session_id, "auditor_result", decision="abstained", summary=last_problem[:300], outcome="abstain")
    return _abstain(question, ""), steps, pending
