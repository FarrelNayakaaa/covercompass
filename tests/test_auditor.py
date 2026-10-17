from pathlib import Path
from src.auditor import verify_answer
from src.data_loader import load_policies
from src.schemas import QAAnswer, Citation

DATA = Path(__file__).resolve().parent.parent / "data" / "golden"
BY_ID = {p.policy_id: p for p in load_policies(DATA)}


def ans(verdict="depends", cites=()):
    return QAAnswer(verdict=verdict, plain_summary="x", confidence="medium", citations=list(cites))


def test_a00_valid_quote_passes():
    c = Citation(policy_id="P1_HEALTH", clause="6.2", quote="Dental benefits begin 90 days after your cover start date")
    assert verify_answer(ans(cites=[c]), BY_ID) == []


def test_a01_fake_quote_blocked():
    c = Citation(policy_id="P1_HEALTH", clause="6.2", quote="Dental is covered from day one")
    assert verify_answer(ans(cites=[c]), BY_ID)


def test_missing_clause_blocked():
    c = Citation(policy_id="P1_HEALTH", clause="99.9", quote="anything")
    assert verify_answer(ans(cites=[c]), BY_ID)


def test_unknown_policy_blocked():
    c = Citation(policy_id="NOPE", clause="1.1", quote="anything")
    assert verify_answer(ans(cites=[c]), BY_ID)


def test_verdict_without_citation_blocked_but_abstain_ok():
    assert verify_answer(ans("covered"), BY_ID)
    assert verify_answer(ans("cannot_confirm"), BY_ID) == []
