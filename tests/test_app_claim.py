"""Uji tampilan: alur klaim dari formulir sampai tombol Confirm dan status."""
import json
from pathlib import Path
import sys
import types
from types import SimpleNamespace as NS

import pytest
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parent.parent / "src" / "app.py"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_AUDIT_DB", str(tmp_path / "audit.db"))
    monkeypatch.setenv("CC_SANDBOX_DB", str(tmp_path / "sandbox.db"))
    monkeypatch.setenv("LLM_API_KEY", "x"); monkeypatch.setenv("LLM_BASE_URL", "http://x"); monkeypatch.setenv("LLM_MODEL", "x")
    reply = json.dumps({"coverage_type": "outpatient", "incident_date": "2026-10-01", "bill_amount": 350,
                        "description": "I saw a doctor.", "accident": False, "emergency": False,
                        "exclusion_flags": [], "claim_date": None})
    fake = types.ModuleType("src.llm")
    fake.chat = lambda system, messages, tools=None, use_cache=True: NS(text=reply, tool_calls=[], raw_message={})
    monkeypatch.setitem(sys.modules, "src.llm", fake)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.sidebar.radio(key="mode").set_value("File a claim").run()
    return at


def test_w03_full_claim_flow_through_confirm(app):
    at = app
    assert not at.exception
    at.text_area(key="claim_text").set_value("I saw a doctor, it cost 350").run()
    at.button(key="btn_extract").click().run()
    assert at.number_input(key="f_bill").value == 350
    assert at.selectbox(key="f_cov").value == "outpatient"

    at.button[[b.label for b in at.button].index("Check my claim")].click().run()
    assert not at.exception
    assert [m.value for m in at.metric][:2] == ["$40.00", "$310.00"]

    at.button(key="btn_submit").click().run()
    assert any("Please confirm" in m.value for m in at.markdown)      # menunggu konfirmasi, belum terkirim
    assert not [s for s in at.success if "Submitted" in s.value]

    confirm = next(b for b in at.button if b.key and b.key.startswith("ok_"))
    confirm.click().run()
    assert any("CLM-0001" in s.value for s in at.success)

    at.button(key="btn_status").click().run()
    assert any("received" in i.value for i in at.info)


def test_cancel_sends_nothing(app):
    at = app
    at.number_input(key="f_bill").set_value(350).run()
    at.selectbox(key="f_cov").set_value("outpatient").run()
    at.button[[b.label for b in at.button].index("Check my claim")].click().run()
    at.button(key="btn_submit").click().run()
    next(b for b in at.button if b.key and b.key.startswith("no_")).click().run()
    assert any("Nothing was sent" in i.value for i in at.info)
    assert not [s for s in at.success if "CLM-" in s.value]


def test_qa_mode_still_loads(app):
    at = app.sidebar.radio(key="mode").set_value("Ask about my policies").run()
    assert not at.exception
    assert len(at.chat_input) == 1


def test_money_mode_shows_total_cost_of_risk(app):
    at = app.sidebar.radio(key="mode").set_value("See my money risk").run()
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert labels[:3] == ["Premiums per year", "Expected out-of-pocket per year", "Total cost of risk"]
    assert at.metric[0].value == "$1,116.00"
    at.number_input(key="m_fund").set_value(500.0)
    [b for b in at.button if b.label == "Recalculate"][0].click().run()
    assert any("more than your emergency savings" in e.value for e in at.error)


def test_money_mode_shows_overlap_and_alerts(app):
    at = app.sidebar.radio(key="mode").set_value("See my money risk").run()
    assert any("may be paying about $60" in w.value for w in at.warning)
    assert any("waiting period ends on 2026-11-13" in w.value for w in at.warning)
    assert any("Gadget Cover" in w.value and "ends soon" in w.value for w in at.warning)


def test_claim_result_shows_filing_deadline(app):
    at = app
    at.number_input(key="f_bill").set_value(600.0).run()
    at.selectbox(key="f_cov").set_value("accidental_damage").run()
    at.button[[b.label for b in at.button].index("Check my claim")].click().run()
    assert not at.exception
    assert any("file this claim by" in (w.value) for w in list(at.info) + list(at.warning))
