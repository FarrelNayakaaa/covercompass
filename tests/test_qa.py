import json
from pathlib import Path
from types import SimpleNamespace as NS
from src.audit import Audit
from src.data_loader import load_policies
from src.qa import answer_question
from src.tiers import Gate
from src.tool_registry import build_tools

DATA = Path(__file__).resolve().parent.parent / "data" / "golden"


def setup(tmp_path):
    pols = load_policies(DATA)
    audit = Audit(str(tmp_path / "a.db"))
    return Gate(build_tools(pols), audit), {p.policy_id: p for p in pols}, audit


def fake(script):
    it = iter(script)
    return lambda system, messages, tools: next(it)


def call(q):
    return NS(text=None, tool_calls=[NS(id="1", name="search_clauses", args={"query": q})],
              raw_message={"role": "assistant", "tool_calls": []})


def final(d):
    return NS(text=json.dumps(d), tool_calls=[], raw_message={})


GOOD = {"verdict": "depends", "plain_summary": "Dental starts after 90 days unless accident.",
        "conditions": ["90-day waiting period"], "confidence": "high", "ask_insurer_script": None,
        "citations": [{"policy_id": "P1_HEALTH", "clause": "6.2",
                      "quote": "Dental benefits begin 90 days after your cover start date"}]}
BAD = dict(GOOD, citations=[{"policy_id": "P1_HEALTH", "clause": "6.2", "quote": "Dental is covered from day one"}])


def test_f01_good_answer_passes(tmp_path):
    gate, by_id, audit = setup(tmp_path)
    ans, steps, _ = answer_question("dental?", gate, by_id, "s1", chat_fn=fake([call("dental waiting"), final(GOOD)]))
    assert ans.verdict == "depends" and steps[0]["tool"] == "search_clauses"
    assert audit.rows("s1")[-1]["decision"] == "passed"


def test_a01_fake_quote_retries_then_passes(tmp_path):
    gate, by_id, audit = setup(tmp_path)
    ans, _, _ = answer_question("dental?", gate, by_id, "s1", chat_fn=fake([final(BAD), final(GOOD)]))
    assert ans.verdict == "depends"
    assert [r["decision"] for r in audit.rows("s1") if r["event"] == "auditor_result"] == ["failed", "passed"]


def test_f05_persistent_fake_quote_abstains(tmp_path):
    gate, by_id, audit = setup(tmp_path)
    ans, _, _ = answer_question("dental?", gate, by_id, "s1", chat_fn=fake([final(BAD), final(BAD)]))
    assert ans.verdict == "cannot_confirm" and ans.ask_insurer_script
    assert audit.rows("s1")[-1]["decision"] == "abstained"


def test_invalid_json_retries(tmp_path):
    gate, by_id, _ = setup(tmp_path)
    junk = NS(text="Sure! Dental is probably fine.", tool_calls=[], raw_message={})
    ans, _, _ = answer_question("dental?", gate, by_id, "s1", chat_fn=fake([junk, final(GOOD)]))
    assert ans.verdict == "depends"
