from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


# ---------- Coverage Graph (Cath mengisi golden JSON dengan skema ini) ----------
class Coverage(BaseModel):
    id: str
    type: str                                   # "inpatient", "outpatient", "accidental_damage", ...
    limit_per_item: float | None = None
    limit_annual: float | None = None
    sub_limit: float | None = None
    deductible: float = 0
    deductible_scope: Literal["per_claim", "annual"] = "per_claim"
    coinsurance: float = 1.0                    # bagian yang dibayar insurer (0.8 = 80%)
    waiting_period_days: int = 0
    emergency_waiver: bool = False              # True = masa tunggu tidak berlaku untuk kasus darurat
    claim_deadline_days: int | None = None
    exclusions: list[str] = Field(default_factory=list)
    source_clause: str                          # wajib, dipakai Auditor


class Policy(BaseModel):
    policy_id: str
    name: str
    premium_annual: float
    currency: str = "USD"
    start_date: date | None = None
    coverages: list[Coverage]
    clauses: dict[str, str]                     # clause_id -> teks klausul


# ---------- Q&A ----------
class Citation(BaseModel):
    policy_id: str
    clause: str
    quote: str


class QAAnswer(BaseModel):
    verdict: Literal["covered", "not_covered", "depends", "cannot_confirm"]
    plain_summary: str
    conditions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    ask_insurer_script: str | None = None
    disclaimer: str = "Indicative only, not a coverage decision."


# ---------- Klaim dan payout (kontrak antara payout.py dan sisanya) ----------
class ClaimInput(BaseModel):
    claim_id: str
    coverage_type: str                          # harus cocok dengan Coverage.type
    incident_date: date
    bill_amount: float
    currency: str = "USD"
    description: str = ""
    documents: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)  # mis. {"emergency": True, "during_trip": True}


class PayoutStep(BaseModel):
    step: str                                   # "eligibility", "deductible", "coinsurance", ...
    amount: float | None = None
    note: str = ""
    clause: str | None = None


class PolicyPayout(BaseModel):
    policy_id: str
    eligible: bool
    reason: str | None = None
    payout: float = 0.0
    steps: list[PayoutStep] = Field(default_factory=list)


class PayoutResult(BaseModel):
    claim_id: str
    total_bill: float
    total_payout: float
    out_of_pocket: float
    per_policy: list[PolicyPayout]
    disclaimer: str = "Indicative estimate, not a coverage decision."
