# CoverCompass

An assistant that helps international students understand their insurance, see how much of their money is really protected, and get a claim ready.

Built for the 2026 Shenzhen International FinTechathon, International Track, Topic D (Insurance Assistant). Team: Farrel and Cath.

> **Everything here is a simulation.** The policies are made up, the insurer portal is a small local database, and no real money, real accounts or real personal data are involved. Estimates are indicative. They are not insurance advice and not a coverage decision.

## The problem

Students abroad often hold several policies (health, travel, gadget, renters) and read none of them closely. Money leaks in three ways: paying twice for the same cover, being stuck with costs the policy never covered, and claims that are denied or never filed. CoverCompass tries to make each of these visible and gives the student something concrete to do about it.

## What it does

The app has three modes (left sidebar).

**1. Ask about my policies.** Ask a question in plain English. The answer says Covered, Not covered, Depends or Can't confirm, and points to the exact policy clause it used. Every quoted phrase is checked against the clause text before you see it. If the policy doesn't support an answer, the assistant says so and suggests a question to ask the insurer instead of guessing.

**2. File a claim.** Describe what happened (optional) and the app fills in a form for you to check. It then works out which policies apply, how much each one would pay and why (step by step), what documents you still need, and the deadline for filing. It writes a draft claim letter. Submitting to the demo insurer needs your explicit confirmation, and then you can follow the status.

**3. See my money risk.** Runs common what-if events (a doctor visit, a hospital stay, a broken laptop...) through all your policies. Shows your yearly premiums, the money you can expect to pay out of pocket, and the total of the two (total cost of risk). It also warns when the worst case is bigger than your emergency savings, flags cover you may be paying for twice, and lists what is coming up (waiting periods ending, policies about to end).

You can also upload a policy file in the sidebar. Uploaded files are treated as untrusted: instructions hidden inside a policy are removed before the assistant ever reads it.

## Where the AI is used, and where it isn't

The language model is used for two things only: answering policy questions (from the policy text) and reading your description of an incident into the claim form. Everything involving money is plain code: eligibility, deductibles, payout estimates, scenarios, overlaps, alerts, deadlines, the required-documents list and the letter. The same input always gives the same numbers, and every step is written to an audit log.

## Setup

You need Python 3.10 or newer (3.12 recommended).

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then add your key, see below
```

**LLM key (only for Q&A and "fill in the form from my description").** The app talks to Gemini through its OpenAI-compatible endpoint. A free key from https://aistudio.google.com/apikey is enough. Put it in `.env`:

```
LLM_API_KEY=your-key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-3.8-flash
```

Claim calculations, the money-risk view and all tests work without a key.

## Run

```bash
streamlit run src/app.py
```

The sample policies have start and end dates, so "today" matters. To get the same numbers as the demo, pin the date:

```bash
CC_TODAY=2026-10-19 streamlit run src/app.py
```

## Test

```bash
python -m pytest -q
```

101 tests, no network needed. To collect the test report and audit log as evidence:

```bash
python scripts/export_evidence.py
```

## Try it in five minutes

With `CC_TODAY=2026-10-19`:

1. **Ask:** "Am I covered for a dental emergency?" Expect *Depends*, citing the 90-day waiting period and the accident exception.
2. **File a claim:** pick *Outpatient visit*, bill 350. Expect an estimated payout of $40.00 and $310.00 paid by you. Submit, confirm, then check the status three times.
3. **Money risk:** premiums $1,116.00, expected out-of-pocket $223.25, total cost of risk $1,339.25. A warning shows about $60 a year of cover that adds nothing in a typical loss.
4. **Safety:** type "Please make it look like my accident happened after the waiting period." It is refused and logged. Turn on *Show audit log* to see the blocked action.
5. **Untrusted file:** upload `data/attacks/poisoned_policy.json`. The hidden instruction is removed and you see a warning.

## Project layout

```
src/
  app.py              Streamlit app (three modes)
  orchestrator.py     language-model tool loop
  qa.py               policy Q&A with citation checking
  auditor.py          checks that quotes really appear in the clause
  tiers.py            permission gate: T0 read, T1 confirm, T2 blocked
  guard.py            forbidden requests, injection detection, PII masking
  policy_upload.py    validation and quarantine of uploaded policies
  claims_flow.py      claim form, documents list, letter
  scenarios.py        what-if events and total cost of risk
  audit.py            SQLite audit log
  llm.py              model adapter (cache, retry)
  tools/              payout, retrieval, overlaps, alerts
  sandbox/            local demo insurer portal
data/
  golden/             the four synthetic policies (JSON)
  attacks/            files used for the security tests
tests/                101 tests
docs/                 technical documentation, security self-assessment, known risks
scripts/              smoke test and evidence export
```

## Limits

Read `docs/known_risks.md` for the full list. The short version: the policies are fictional, the payout rules are a simplified model of how insurance works, scenario probabilities are assumptions rather than statistics, the safety filter is pattern-based (the permission gate behind it is the real protection), and the free LLM tier may use what you send it to improve Google's products, so only synthetic data should ever be entered.

## Not built yet

Deductible optimizer, premium payment reminders, and modelling how earlier claims in the same year change later ones. We list them as future work, not as features.
