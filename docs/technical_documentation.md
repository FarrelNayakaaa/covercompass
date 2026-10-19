# CoverCompass: Technical Documentation

FinTechathon 2026, International Track, Topic D (Insurance Assistant). Team: Farrel and Cath. October 2026.

## 1. Overview

CoverCompass helps international students deal with the insurance they already hold. A student can ask what a policy covers, see how much of their money is actually protected, and prepare a claim. The assistant acts, but only inside a sandbox, and only with the user's confirmation.

The financial idea behind it is simple. Insurance costs money (premiums), and some losses are still paid by the student (deductibles, co-insurance, exclusions, missed deadlines). We measure two things:

- **Total cost of risk (TCR)** = yearly premiums + expected yearly out-of-pocket cost. Lower is better.
- **Claim recovery**: how much of a loss comes back from the insurer.

Each feature is there to lower the first number or raise the second, and each shows its arithmetic so the user can check it.

## 2. Scope

**In scope:** question answering over policy text with citations; claim eligibility and payout estimates; claim preparation and a sandbox submission; what-if scenarios and TCR; overlap detection; proactive alerts; handling of untrusted input.

**Out of scope:** real insurers, real money, real personal data, regulated advice, and any decision on a claim. All outputs are labelled indicative.

**All data is synthetic.** Four fictional policies were written for this project (student health, travel, gadget, renters).

## 3. Architecture

```
User (Streamlit)
  |
  v
Guard            forbidden requests -> mapped to blocked (T2) actions
                 injection phrases -> blocked
                 personal numbers -> masked
  |
  +--> Ask mode:     Orchestrator (LLM tool loop, max 6 steps)
  |                       -> Citation checker -> answer (or decline)
  +--> Claim mode:   Claim form -> deterministic tools
  +--> Money mode:   Scenarios, overlaps, alerts -> deterministic tools
  |
  v
Permission gate (the only way to reach any tool)
  T0 read/calculate: runs, logged
  T1 simulated action: waits for a button click, then runs
  T2 forbidden: never runs, logged as a known risk
  |
  v
Tools -> synthetic policies, local demo insurer portal (SQLite)
  |
  v
Audit log (SQLite)  <- every tool call, decision, confirmation, guard event, checker result
```

Two design choices matter most:

1. **The model never touches money.** Amounts come from code. The model reads text and talks.
2. **The permission gate does not trust the model.** Confirmation for T1 actions can only come from a button in the interface, not from anything the model writes. T2 actions have no working function behind them, and are refused even if one were registered (tested).

## 4. Components

| Component | File | What it does |
|---|---|---|
| App | `src/app.py` | Three modes, confirmation card, audit view, policy upload |
| Orchestrator | `src/orchestrator.py` | Model tool loop, at most 6 steps, hands tool results back to the model |
| Q&A | `src/qa.py` | Asks for a JSON answer (verdict, summary, conditions, citations, confidence, a question for the insurer). Retries once if the checker rejects it, then declines |
| Citation checker | `src/auditor.py` | Clause must exist; quoted words must appear in that clause; a verdict needs at least one citation |
| Retrieval | `src/tools/retrieve.py` | BM25 keyword search over clauses (own implementation, no extra dependency) |
| Permission gate | `src/tiers.py` | Tool-to-tier table, default deny for unknown tools, pending actions for T1, error handling |
| Guard | `src/guard.py` | Six forbidden-request categories, injection phrases, personal-number masking, policy quarantine |
| Upload | `src/policy_upload.py` | Validates an uploaded policy, quarantines suspicious clauses, scans the file name |
| Payout engine | `src/tools/payout.py` | Eligibility and amounts, step by step |
| Claim flow | `src/claims_flow.py` | Reads a description into the form (output cleaned), documents list, letter template |
| Scenarios | `src/scenarios.py` | What-if events through the payout engine, TCR, emergency-fund check |
| Overlaps | `src/tools/overlap.py` | Finds cover held more than once and when each extra policy actually helps |
| Alerts | `src/tools/alerts.py` | Waiting periods, policy end dates, claim filing deadlines |
| Demo insurer | `src/sandbox/insurer_portal.py` | Local database; fixed status sequence |
| Audit | `src/audit.py` | SQLite log and JSONL export |
| Model adapter | `src/llm.py` | OpenAI-compatible client (used with Gemini), retry on rate limit, response cache |
| Clock | `src/clock.py` | Today's date, pinnable with `CC_TODAY` |

**The model is used in exactly two places:** answering policy questions, and reading a free-text incident description into form fields. Both outputs are checked or cleaned before use.

## 5. Data

Policies are JSON (`data/golden/`), validated by the schema in `src/schemas.py`. A policy has premium, start and end dates, a list of coverages and the clause text. Each coverage carries its numbers (per-item limit, annual limit, deductible and whether it is per claim or annual, co-insurance share, waiting period, whether accidents skip the waiting period, claim deadline, exclusions, an optional separate premium) and `source_clause`, the clause those numbers come from. The checker and the interface both rely on that link.

| Policy | Premium / year | Main cover |
|---|---|---|
| P1 Student Health | 720 | Hospital stay, doctor visits (80% after deductible), emergency dental only (90-day waiting period) |
| P2 Student Travel | 180 | Medical abroad, damage to baggage and electronics, trip cancellation |
| P3 Gadget Cover | 120 | Accidental damage and theft of devices |
| P4 Renters | 96 | Contents theft after forced entry, liability, an electronics rider (USD 60 of the premium) |

## 6. Payout rules

For each claim, policies are processed in order. A policy only takes part if it has a coverage of the claimed type. For one policy:

1. **Eligibility.** Not eligible if any of these holds (payout is zero and the reason and clause are shown):
   - an exclusion flag on the claim matches an exclusion of the coverage;
   - the incident is before the start date;
   - the waiting period is not over, unless the coverage allows it for accidents or emergencies and the claim says so;
   - the incident is after the end date;
   - the claim is filed later than the claim deadline.
2. **Per-item limit.** Eligible amount = the remaining loss, capped at the per-item limit if there is one.
3. **Deductible.** Subtract what is left of the deductible (a fresh amount for "per claim", or the annual amount minus what is already used).
4. **Co-insurance.** Multiply by the insurer's share (for example 0.8).
5. **Annual limit.** Cap at what is left of the annual limit.
6. **Several policies.** The next policy only handles the loss the previous ones did not pay. Total payout can never exceed the bill. By assumption the policy with the smallest deductible pays first.

**Worked example 1: a doctor visit.** Bill 350, annual deductible 300 not yet used, insurer share 80%. 350 - 300 = 50; 50 x 0.8 = **40** paid by the insurer, **310** by the student.

**Worked example 2: a broken laptop.** Bill 600, gadget policy with a USD 75 deductible per claim. 600 - 75 = **525** paid, **75** by the student. The travel policy then sees a remaining loss of 75, which is below its own USD 100 deductible, so it pays nothing.

## 7. Money-risk view

Seven events are run through all policies: doctor visit, emergency room, three-day hospital stay, emergency dental after an accident, medical care during a trip abroad, broken laptop, stolen phone. Each has a cost and a yearly chance, both editable. For each event the interface shows what the insurer pays and what the student pays.

- Expected out-of-pocket = sum of (chance x amount the student pays).
- TCR = yearly premiums + expected out-of-pocket.
- The worst single event is compared with the student's emergency savings (default 1,500).

With the four sample policies and the default assumptions: premiums **1,116.00**, expected out-of-pocket **223.25**, TCR **1,339.25**. A doctor visit of 250 is paid **0** by the insurer (below the deductible) and is the clearest example of money that looks protected but isn't.

**The chances are assumptions, not statistics.** The interface says so, and each event is treated on its own, as if no earlier claim had been made that year.

## 8. Overlaps and alerts

**Overlaps.** For each coverage type held in more than one policy, the engine runs a typical loss (600) and a grid of losses (50 to 5,000) through the policies in payment order. It reports what each extra policy adds and the smallest loss at which it starts to pay. A policy is flagged as a possible duplicate only if it adds nothing at the typical loss **and** has a separate premium. In the sample data, the electronics rider in P4 is flagged (about USD 60 a year). It only pays extra for losses above about USD 2,100. The travel policy overlaps with the gadget policy but is not flagged, since its premium cannot be separated.

**Alerts.** Waiting periods that have not ended, policies ending within 60 days, and policies that have already ended. For a claim, the filing deadline for each policy. Colours follow urgency.

## 9. Claim flow

1. The user describes the incident (optional). The model fills a form; any value outside the allowed lists, any future date or an implausible amount is dropped. Text containing injection phrases or forbidden requests is blocked before reaching the model.
2. The user checks and edits the form, then presses *Check my claim*.
3. The gate runs eligibility, payout and deadlines (T0, all logged). The interface shows who pays what and why.
4. The user ticks the documents they have. Missing ones are listed. The letter is generated from a template.
5. *Submit* asks the gate for `submit_claim_sandbox` (T1). A confirmation card shows the amounts. Only the **Confirm** button runs it.
6. The estimate sent to the demo insurer is **recomputed on the server** from the claim. If the model tried to pass its own amount, the call is rejected (tested).
7. The portal returns a reference. Checking status moves it through received, in review, then approved or denied.

## 10. Running and configuration

See the README for setup. Key points: Python 3.10+, a Gemini key (free tier is enough) for Q&A and form-filling only, `CC_TODAY` to pin the date, `CC_AUDIT_DB` and `CC_SANDBOX_DB` to relocate the databases.

## 11. Testing

101 automated tests, no network access needed (the model is replaced by a stub). Run with `python -m pytest -q`.

| Area | File | Tests |
|---|---|---|
| Permission gate | `test_tiers.py` | 7 |
| Orchestrator loop | `test_orchestrator.py` | 4 |
| Retrieval | `test_retrieve.py` | 5 |
| Citation checker | `test_auditor.py` | 5 |
| Q&A flow | `test_qa.py` | 4 |
| Payout engine | `test_payout.py` | 13 |
| Demo insurer | `test_portal.py` | 4 |
| Tool registry and server-side estimate | `test_registry.py` | 5 |
| Policy data validity | `test_policies_valid.py` | 2 |
| Claim flow helpers | `test_claims_flow.py` | 6 |
| Scenarios and TCR | `test_scenarios.py` | 5 |
| Overlaps and alerts | `test_overlap_alerts.py` | 7 |
| Guard (attacks, normal messages, masking) | `test_guard.py` | 20 |
| Policy upload and quarantine | `test_policy_upload.py` | 4 |
| Interface flows (claim to confirm, money view, cancel) | `test_app_claim.py` | 6 |
| Security through the interface | `test_security_app.py` | 4 |

`scripts/export_evidence.py` saves the test report and the audit log to `docs/evidence/`.

## 12. Limits and future work

See `docs/known_risks.md`. Not built: deductible optimizer, premium payment reminders, carrying used-up limits across claims, semantic search, login.
