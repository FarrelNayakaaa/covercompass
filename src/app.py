import sys, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # supaya "from src..." jalan di streamlit

import streamlit as st
from dotenv import load_dotenv

from src.audit import Audit
from src.data_loader import load_policies
from src.qa import answer_question
from src.tiers import Gate
from src.tool_registry import build_tools

load_dotenv()
st.set_page_config(page_title="CoverCompass", page_icon="🧭", layout="wide")

VERDICT_STYLE = {
    "covered": ("Covered", st.success),
    "not_covered": ("Not covered", st.error),
    "depends": ("Depends", st.warning),
    "cannot_confirm": ("Can't confirm", st.info),
}


@st.cache_resource
def get_policies():
    return load_policies()


def init_state():
    if "session_id" not in st.session_state:
        policies = get_policies()
        audit = Audit("audit.db")
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.policies = policies
        st.session_state.by_id = {p.policy_id: p for p in policies}
        st.session_state.audit = audit
        st.session_state.gate = Gate(build_tools(policies), audit)
        st.session_state.turns = []


def render_answer(turn):
    ans, by_id = turn["answer"], st.session_state.by_id
    label, box = VERDICT_STYLE[ans["verdict"]]
    box(f"**{label}** (confidence: {ans['confidence']})")
    st.write(ans["plain_summary"])
    if ans["conditions"]:
        st.markdown("**Conditions**\n" + "\n".join(f"- {c}" for c in ans["conditions"]))
    for c in ans["citations"]:
        pol = by_id.get(c["policy_id"])
        with st.expander(f"Source: {pol.name if pol else c['policy_id']}, clause {c['clause']}"):
            st.write(pol.clauses.get(c["clause"], "") if pol else "")
            st.caption(f"Quoted: \u201c{c['quote']}\u201d")
    if ans.get("ask_insurer_script"):
        st.markdown("**Ask your insurer:** " + ans["ask_insurer_script"])
    st.caption(ans["disclaimer"])
    if turn["steps"]:
        st.caption("Steps: " + " \u2192 ".join(f"{s['tool']} ({s['status']})" for s in turn["steps"]))


def render_pending():
    gate = st.session_state.gate
    for pid, (name, args, _sid) in list(gate.pending.items()):
        with st.container(border=True):
            st.markdown(f"**Action waiting for your confirmation:** `{name}`")
            st.json(args)
            c1, c2 = st.columns(2)
            if c1.button("Confirm", key=f"ok_{pid}"):
                st.session_state.last_result = gate.confirm(pid)
                st.rerun()
            if c2.button("Cancel", key=f"no_{pid}"):
                st.session_state.last_result = gate.reject(pid)
                st.rerun()


init_state()
st.title("CoverCompass")
st.caption("Ask about your insurance policies. Answers cite the policy clause. "
           "Indicative only, not a coverage decision. Demo uses synthetic policies.")

with st.sidebar:
    st.subheader("Policies loaded")
    for p in st.session_state.policies:
        st.write(f"- {p.name} (`{p.policy_id}`)")
    if st.toggle("Show audit log"):
        st.dataframe(st.session_state.audit.rows(st.session_state.session_id), use_container_width=True)

for t in st.session_state.turns:
    with st.chat_message("user"):
        st.write(t["question"])
    with st.chat_message("assistant"):
        render_answer(t)

render_pending()
if "last_result" in st.session_state:
    st.info(f"Result: {st.session_state.pop('last_result')}")

q = st.chat_input("e.g. Am I covered for a dental emergency?")
if q:
    with st.spinner("Checking the policy text..."):
        try:
            ans, steps, _ = answer_question(q, st.session_state.gate, st.session_state.by_id,
                                            st.session_state.session_id)
            st.session_state.turns.append({"question": q, "answer": ans.model_dump(), "steps": steps})
        except Exception as e:
            st.error(f"Something went wrong: {type(e).__name__}: {e}")
    st.rerun()
