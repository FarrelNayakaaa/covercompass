# Known risks and limits

Written by the team during development. We would rather list what can go wrong than hide it. Each item says what we did about it and what is still left.

| ID | Risk | What we did | What is left |
|---|---|---|---|
| KR-01 | **The model invents a policy clause or misquotes one.** | Answers must cite a clause. A checker confirms the clause exists and that the quoted words really appear in it. A coverage verdict with no citation is rejected. One retry, then the assistant declines and suggests a question for the insurer. | The checker confirms the quote is real, not that the model *interpreted* it correctly. A real quote can still be read wrongly. |
| KR-02 | **Prompt injection** hidden in a policy file, a file name, or a claim description. | Uploaded policies are scanned and suspicious clauses are removed before indexing. Claim descriptions and chat messages are scanned and blocked. The model's claim output is cleaned (values outside allowed lists are dropped) and the user reviews the form. Most important: even if the model were fooled, the permission gate still needs a human click for any action. | The scanner is pattern-based and can be bypassed by unusual wording. |
| KR-03 | **The safety filter blocks a normal message** (false positive) or **misses an attack** (false negative). | Six categories of forbidden requests map to blocked actions. A set of normal questions is tested to make sure they pass. | Coverage of phrasing is limited, mostly English (a few Indonesian terms). Not a substitute for the permission gate. |
| KR-04 | **The model misreads a claim description** (wrong date, amount or type). | Output is cleaned and shown in an editable form. Nothing is calculated until the user presses *Check my claim*. | A user who doesn't check the form can submit wrong details. |
| KR-05 | **The payout model is simplified.** | Rules are explicit, deterministic and tested (see technical documentation, section 6). Every step is shown to the user. | Not modelled: per-night sub-limits (such as the hospital room limit), claims earlier in the year using up limits (unless supplied), partial-year pro-rating, taxes, currency conversion, and insurers' real coordination-of-benefits rules. |
| KR-06 | **Which policy pays first** is a guess. | We assume the policy with the smallest deductible pays first, and say so in the interface. | Real contracts have their own "other insurance" rules. Totals can differ. |
| KR-07 | **Scenario probabilities are invented.** | Labelled as assumptions everywhere they appear. The user can change them. | They are not statistics or actuarial estimates. Total cost of risk is only as good as these inputs. |
| KR-08 | **Duplicate-premium warnings could be wrong.** | A policy is flagged only if it adds nothing in a typical $600 loss *and* its premium is separate (a rider). Travel overlaps with the gadget policy but is not flagged, because its premium is not separable. | The typical loss is a fixed assumption. The flag says "may", not "does". |
| KR-09 | **The policies are made up.** | All four were written by us. We did not copy any real insurer's wording. | Real policies are longer, vaguer and contradict themselves more. Results on real documents are untested. |
| KR-10 | **The free LLM tier may use inputs to improve the provider's products, and has rate limits.** | We only ever use synthetic data. Personal numbers (passport, card, email, phone) are masked before they reach the model or the log. Responses are cached to save quota. | Masking recognises common formats only. Real users should not use a free tier with real documents. |
| KR-11 | **Masking misses an unusual personal number.** | Patterns for passport, card or long ID numbers, email, phone, SSN-style numbers. | Other formats pass through. |
| KR-12 | **The insurer portal is not an insurer.** | It is a local database with a fixed rule: received, then in review, then approved (amount = our estimate) or denied (if the estimate is zero). | Real insurers decide differently and slowly. Status in the demo says nothing about real outcomes. |
| KR-13 | **No users, no login, no access control.** | Not needed for a single-user demo. Confirmation happens through a button, never through model output. | Anyone with access to the running app can confirm actions. |
| KR-14 | **The audit log can be edited.** | It is a local SQLite file. Raw inputs are not stored, only a short hash of the arguments and a one-line summary. | Not tamper-proof. |
| KR-15 | **Retrieval is keyword-based (BM25).** | Fine for four short policies, and every answer is checked against the text anyway. | Would need semantic search for long real documents. |
| KR-16 | **Dates change the answer.** | Policies have start and end dates. `CC_TODAY` pins the date for demos and tests. | After the sample policies end (the gadget policy ends on 2026-12-01), the live app treats them as expired unless the date is pinned. |
| KR-17 | **English only.** | The submission language is English. | Not tested in other languages. |

## Not implemented (future work)

- Deductible optimizer (needs a real premium table, which we would have had to invent).
- Reminders for premium payments.
- Carrying used-up limits from earlier claims across a year.
- Semantic retrieval and support for scanned documents.
- Login and per-user data.
