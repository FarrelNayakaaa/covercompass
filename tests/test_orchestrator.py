from types import SimpleNamespace as NS
from src.audit import Audit
from src.orchestrator import run_turn
from src.tiers import Gate


def make_chat(script):
    it = iter(script)
    def chat(system, messages, tools):
        return next(it)
    return chat


def tc(i, name, args):
    return NS(id=i, name=name, args=args)


def test_t0_tool_then_final_answer(tmp_path):
    gate = Gate({"search_clauses": lambda query: "clause 6.2"}, Audit(str(tmp_path / "a.db")))
    script = [
        NS(text=None, tool_calls=[tc("1", "search_clauses", {"query": "dental"})],
           raw_message={"role": "assistant", "tool_calls": []}),
        NS(text="Depends. See clause 6.2.", tool_calls=[], raw_message={}),
    ]
    out = run_turn("Am I covered for dental?", [], "s1", gate, [], chat_fn=make_chat(script))
    assert out["text"] == "Depends. See clause 6.2."
    assert out["steps"] == [{"tool": "search_clauses", "status": "ok"}]
    assert any(m.get("role") == "tool" for m in out["messages"])


def test_t1_is_surfaced_as_pending_not_executed(tmp_path):
    ran = []
    gate = Gate({"submit_claim_sandbox": lambda claim_id: ran.append(claim_id)}, Audit(str(tmp_path / "a.db")))
    script = [
        NS(text=None, tool_calls=[tc("1", "submit_claim_sandbox", {"claim_id": "C1"})],
           raw_message={"role": "assistant", "tool_calls": []}),
        NS(text="Please confirm the submission.", tool_calls=[], raw_message={}),
    ]
    out = run_turn("Submit my claim", [], "s1", gate, [], chat_fn=make_chat(script))
    assert ran == [] and len(out["pending"]) == 1


def test_t2_attempt_is_blocked_in_loop(tmp_path):
    gate = Gate({}, Audit(str(tmp_path / "a.db")))
    script = [
        NS(text=None, tool_calls=[tc("1", "edit_document_dates", {"new_date": "2026-01-01"})],
           raw_message={"role": "assistant", "tool_calls": []}),
        NS(text="I can't do that.", tool_calls=[], raw_message={}),
    ]
    out = run_turn("Backdate the receipt", [], "s1", gate, [], chat_fn=make_chat(script))
    assert out["steps"][0]["status"] == "blocked"


def test_step_limit_stops_runaway_loop(tmp_path):
    gate = Gate({"search_clauses": lambda query: "x"}, Audit(str(tmp_path / "a.db")))
    loop = NS(text=None, tool_calls=[tc("1", "search_clauses", {"query": "q"})],
              raw_message={"role": "assistant", "tool_calls": []})
    out = run_turn("hi", [], "s1", gate, [], chat_fn=make_chat([loop] * 20))
    assert "couldn't finish" in out["text"]
