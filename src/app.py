import os, sys, uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # supaya "from src..." jalan di streamlit

import streamlit as st
from dotenv import load_dotenv

from src import claims_flow as cf
from src import guard
from src.policy_upload import ingest_policy
from src.audit import Audit
from src.data_loader import load_policies
from src.qa import answer_question
from src.tiers import Gate
from src.tool_registry import build_tools

load_dotenv()
SANDBOX_DB = os.getenv("CC_SANDBOX_DB", "sandbox.db")
st.set_page_config(page_title="CoverCompass", page_icon="🧭", layout="wide")

VERDICT_STYLE = {
    "covered": ("Covered", st.success), "not_covered": ("Not covered", st.error),
    "depends": ("Depends", st.warning), "cannot_confirm": ("Can't confirm", st.info),
}
STEP_NAMES = {"eligibility": "Eligibility check", "limit": "Per-item limit", "deductible": "Deductible",
              "coinsurance": "Insurer's share", "annual_cap": "Annual limit", "final": "Estimated payout"}


@st.cache_resource
def get_policies():
    return load_policies()


def init_state():
    if "session_id" in st.session_state:
        return
    policies = get_policies()
    audit = Audit(os.getenv("CC_AUDIT_DB", "audit.db"))
    ss = st.session_state
    ss.session_id = str(uuid.uuid4())[:8]
    ss.policies, ss.by_id, ss.audit = policies, {p.policy_id: p for p in policies}, audit
    ss.gate = Gate(build_tools(policies, SANDBOX_DB), audit)
    ss.turns = []
    types = cf.known_types(policies)
    ss.f_cov = types[0] if types else ""
    ss.f_date, ss.f_claimdate = date.today(), date.today()
    ss.f_bill, ss.f_desc = 0.0, ""
    ss.f_accident = ss.f_emergency = False
    ss.f_excl = []



# ---------------------------------------------------------------- Penjaga
def screen(text, source):
    """Periksa pesan pengguna, catat ke audit, dan tolak aksi terlarang lewat Gate (T2)."""
    ss = st.session_state
    g = guard.check_message(text)
    for kind in g.pii:
        ss.audit.log(ss.session_id, "guard_flag", decision="masked", summary=f"{source}: pii={kind}")
    if g.flags:
        ss.audit.log(ss.session_id, "guard_flag", decision="blocked", summary=f"{source}: {', '.join(g.flags)}",
                     outcome="blocked")
    if g.t2_tool:
        ss.gate.execute(g.t2_tool, {}, ss.session_id)     # ditolak dan dicatat sebagai known risk
    return g


def handle_upload(file):
    ss = st.session_state
    sig = (file.name, file.size)
    if ss.get("last_upload") == sig:
        return
    ss.last_upload = sig
    policy, findings, error = ingest_policy(file.getvalue(), file.name, set(ss.by_id))
    for where, flags in findings:
        ss.audit.log(ss.session_id, "guard_flag", decision="quarantined",
                     summary=f"upload {file.name}: {where}: {', '.join(flags)}", outcome="blocked")
    if error:
        ss.upload_msg = ("error", error)
        return
    ss.policies = ss.policies + [policy]
    ss.by_id[policy.policy_id] = policy
    ss.gate.tools = build_tools(ss.policies, SANDBOX_DB)
    if findings:
        ss.upload_msg = ("warning", f"Loaded {policy.name}, but I removed {len(findings)} suspicious part(s) "
                                    "that tried to give me instructions: " + "; ".join(w for w, _ in findings) + ".")
    else:
        ss.upload_msg = ("success", f"Loaded {policy.name}.")


# ---------------------------------------------------------------- Q&A
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


def qa_mode():
    st.caption("Ask about your insurance policies. Answers cite the policy clause. "
               "Indicative only, not a coverage decision. Demo uses synthetic policies.")
    for t in st.session_state.turns:
        with st.chat_message("user"):
            st.write(t["question"])
        with st.chat_message("assistant"):
            if "refusal" in t:
                st.error(t["refusal"])
                st.caption("Request refused and logged.")
            else:
                render_answer(t)
    q = st.chat_input("e.g. Am I covered for a dental emergency?")
    if q:
        g = screen(q, "chat")
        if g.blocked:
            st.session_state.turns.append({"question": g.masked_text, "refusal": g.message})
        else:
            with st.spinner("Checking the policy text..."):
                try:
                    ans, steps, _ = answer_question(g.masked_text, st.session_state.gate, st.session_state.by_id,
                                                    st.session_state.session_id)
                    st.session_state.turns.append({"question": g.masked_text, "answer": ans.model_dump(), "steps": steps})
                except Exception as e:
                    st.error(f"Something went wrong: {type(e).__name__}: {e}")
        st.rerun()


# ---------------------------------------------------------------- Klaim
def do_extract():
    ss = st.session_state
    text = (ss.get("claim_text") or "").strip()
    if not text:
        ss.claim_msg = ("warning", "Please describe what happened first.")
        return
    g = screen(text, "claim_text")
    if g.blocked:
        ss.claim_msg = ("error", g.message)
        return
    try:
        d = cf.extract_claim(g.masked_text, ss.policies, date.today())
    except Exception as e:
        ss.claim_msg = ("error", f"I couldn't read that description ({type(e).__name__}). Please fill in the form yourself.")
        return
    if d.coverage_type:
        ss.f_cov = d.coverage_type
    if d.incident_date:
        ss.f_date = d.incident_date
    if d.bill_amount:
        ss.f_bill = d.bill_amount
    if d.claim_date:
        ss.f_claimdate = d.claim_date
    ss.f_desc, ss.f_accident, ss.f_emergency, ss.f_excl = d.description, d.accident, d.emergency, d.exclusion_flags
    ss.claim_msg = ("success", "I filled in the form from your description. Please check every field before you continue.")


def run_check():
    ss = st.session_state
    g = screen(ss.f_desc, "claim_description")
    if g.blocked:
        ss.claim_msg = ("error", g.message)
        return
    claim = {"claim_id": "C-" + uuid.uuid4().hex[:6].upper(), "coverage_type": ss.f_cov,
             "incident_date": ss.f_date.isoformat(), "bill_amount": float(ss.f_bill), "description": g.masked_text,
             "context": {"accident": ss.f_accident, "emergency": ss.f_emergency,
                         "exclusion_flags": list(ss.f_excl), "claim_date": ss.f_claimdate.isoformat()}}
    order = cf.order_policies(ss.policies, ss.f_cov)
    args = {"claim": claim, "policy_ids": order}
    elig = ss.gate.execute("check_claim_eligibility", args, ss.session_id)
    pay = ss.gate.execute("calc_payout", args, ss.session_id)
    if elig["status"] != "ok" or pay["status"] != "ok":
        ss.claim_msg = ("error", "I couldn't calculate this claim. " + str(pay.get("reason") or elig.get("reason") or ""))
        return
    ss.claim_result = {"claim": claim, "order": order, "elig": elig["result"], "pay": pay["result"]}
    ss.pop("claim_ref", None); ss.pop("claim_status", None)


def do_submit():
    ss, r = st.session_state, st.session_state.claim_result
    out = ss.gate.execute("submit_claim_sandbox", {"claim": r["claim"], "policy_ids": r["order"]}, ss.session_id)
    if out["status"] != "awaiting_confirmation":
        ss.claim_msg = ("error", "The submission could not be prepared: " + str(out.get("reason", out["status"])))


def do_status():
    ss = st.session_state
    out = ss.gate.execute("get_claim_status", {"reference": ss.claim_ref}, ss.session_id)
    ss.claim_status = out.get("result", {"error": out.get("reason")})


def claim_mode():
    ss = st.session_state
    st.caption("File a claim in the demo insurer portal (sandbox). Nothing real is sent. "
               "Estimates are indicative, not a coverage decision.")
    st.text_area("Tell me what happened (optional). I'll try to fill in the form for you.", key="claim_text", height=90)
    st.button("Fill in the form from my description", key="btn_extract", on_click=do_extract)
    if "claim_msg" in ss:
        kind, text = ss.pop("claim_msg")
        getattr(st, kind)(text)

    types = cf.known_types(ss.policies)
    with st.form("claim_form"):
        st.selectbox("What kind of claim is it?", types, key="f_cov", format_func=cf.label)
        st.date_input("Date of the incident", key="f_date", max_value=date.today())
        st.number_input("Total bill (USD)", min_value=0.0, step=10.0, key="f_bill")
        st.date_input("Date you are filing the claim", key="f_claimdate")
        st.checkbox("It was an accident", key="f_accident")
        st.checkbox("It was an emergency", key="f_emergency")
        st.multiselect("Does anything on this list apply?", cf.known_exclusions(ss.policies),
                       key="f_excl", format_func=cf.label)
        st.text_input("Short description", key="f_desc")
        st.form_submit_button("Check my claim", on_click=run_check)

    r = ss.get("claim_result")
    if not r:
        return
    pay, claim = r["pay"], r["claim"]
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated payout", f"${pay['total_payout']:,.2f}")
    c2.metric("You would pay yourself", f"${pay['out_of_pocket']:,.2f}")
    c3.metric("Total bill", f"${pay['total_bill']:,.2f}")
    if not r["elig"]:
        st.warning("None of your policies has this kind of cover. Ask your insurer before spending more money.")
    for e in r["elig"]:
        name = ss.by_id[e["policy_id"]].name
        (st.success if e["eligible"] else st.error)(
            f"**{name}**: " + ("eligible." if e["eligible"] else e["reason"]) + f" (clause {e['clause']})")
    for p in pay["per_policy"]:
        with st.expander(f"How {ss.by_id[p['policy_id']].name} was calculated (pays ${p['payout']:,.2f})"):
            st.table([{"Step": STEP_NAMES.get(s["step"], s["step"]), "Amount": "" if s["amount"] is None else f"{s['amount']:,.2f}",
                       "Note": s["note"], "Clause": s["clause"]} for s in p["steps"]])

    st.subheader("Documents")
    available = [d for i, d in enumerate(cf.required_docs(claim["coverage_type"]))
                 if st.checkbox(d, key=f"doc_{claim['coverage_type']}_{i}")]
    missing = cf.missing_documents(claim["coverage_type"], available)
    (st.warning if missing else st.success)("Still missing: " + "; ".join(missing) if missing else "You have everything on the list.")

    st.subheader("Draft claim letter")
    payers = [ss.by_id[p["policy_id"]].name for p in pay["per_policy"] if p["payout"] > 0] or \
             [ss.by_id[p["policy_id"]].name for p in pay["per_policy"]]
    st.code(cf.draft_letter(claim, pay, available, payers), language=None)

    st.subheader("Submit")
    waiting = bool(ss.gate.pending)
    if pay["total_payout"] <= 0:
        st.warning("The estimate is $0, so the insurer will probably deny this claim. You can still submit it in the demo.")
    st.button("Submit to the sandbox insurer", key="btn_submit", on_click=do_submit,
              disabled=waiting or "claim_ref" in ss)
    if "claim_ref" in ss:
        st.success(f"Submitted. Reference: **{ss.claim_ref}**")
        st.button("Check status", key="btn_status", on_click=do_status)
        if "claim_status" in ss:
            s = ss.claim_status
            st.info(f"Status: **{s.get('status', 'unknown')}**" +
                    (f", approved amount ${s['approved_amount']:,.2f}" if s.get("status") == "approved" else ""))


# ---------------------------------------------------------------- Konfirmasi T1
def render_pending():
    ss, gate = st.session_state, st.session_state.gate
    for pid, (name, args, _sid) in list(gate.pending.items()):
        with st.container(border=True):
            st.markdown(f"**Please confirm this action:** `{name}`")
            if name == "submit_claim_sandbox":
                pay = ss.get("claim_result", {}).get("pay")
                if pay:
                    st.write(f"Claim `{args['claim']['claim_id']}`: bill ${pay['total_bill']:,.2f}, "
                             f"estimated payout ${pay['total_payout']:,.2f}. This goes to the sandbox portal only.")
            else:
                st.json(args)
            c1, c2 = st.columns(2)
            if c1.button("Confirm", key=f"ok_{pid}"):
                res = gate.confirm(pid)
                ss.last_result = res
                if res.get("status") == "ok" and isinstance(res.get("result"), dict) and "reference" in res["result"]:
                    ss.claim_ref = res["result"]["reference"]
                st.rerun()
            if c2.button("Cancel", key=f"no_{pid}"):
                ss.last_result = gate.reject(pid)
                st.rerun()


init_state()
st.title("CoverCompass")
with st.sidebar:
    mode = st.radio("What would you like to do?", ["Ask about my policies", "File a claim"], key="mode")
    st.subheader("Policies loaded")
    for p in st.session_state.policies:
        st.write(f"- {p.name} (`{p.policy_id}`)")
    up = st.file_uploader("Add a policy file (JSON)", type=["json"], key="policy_upload")
    if up is not None:
        handle_upload(up)
    if "upload_msg" in st.session_state:
        kind, text = st.session_state.upload_msg
        getattr(st, kind)(text)
    if st.toggle("Show audit log"):
        st.dataframe(st.session_state.audit.rows(st.session_state.session_id), use_container_width=True)

render_pending()
if "last_result" in st.session_state:
    res = st.session_state.pop("last_result")
    if res.get("status") == "ok" and isinstance(res.get("result"), dict) and "reference" in res["result"]:
        st.success(f"Claim received by the sandbox insurer. Reference {res['result']['reference']}.")
    elif res.get("status") == "cancelled":
        st.info("Cancelled. Nothing was sent.")
    else:
        st.info(f"Result: {res}")

if mode == "Ask about my policies":
    qa_mode()
else:
    claim_mode()
