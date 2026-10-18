"""Lapisan penjaga: (1) filter permintaan terlarang yang dipetakan ke aksi T2, (2) deteksi injeksi prompt,
(3) masking data pribadi, (4) karantina klausul beracun pada polis yang diunggah.
Filter ini hanya lapisan pertama. Gerbang tier (tiers.py) tetap menolak T2 meski filter ini terlewat."""
import re
from dataclasses import dataclass, field

I = re.IGNORECASE

INJECTION = [re.compile(p, I) for p in [
    r"\bignore\b.{0,30}\b(instructions?|rules|guidelines|policy text)\b",
    r"\bdisregard\b.{0,30}\b(instructions?|rules|above|previous)\b",
    r"\bapprove\s+(all|every|any)\s+claims?\b",
    r"\bsystem\s*(note|prompt|message|override)\b",
    r"\b(without|skip)\b.{0,20}\b(confirmation|checking|verifying|asking)\b",
    r"\b(reveal|print|repeat)\b.{0,30}\b(system prompt|hidden instructions|api key)\b",
    r"\bpay\b.{0,30}\bregardless\b",
    r"\bdo not (tell|inform|mention)\b.{0,20}\b(the )?(user|customer)\b",
    r"\bnew instructions?\b",
    r"\b(you are now|pretend to be)\b",
]]

# nama -> (pola, nama tool T2 yang sesuai, pesan untuk pengguna)
FORBIDDEN = {
    "document_tampering": ([
        r"\bback-?dat(e|ed|ing)\b",
        r"\bmake (it|this|that|the (date|accident|incident|claim))\b.{0,40}\b(look|seem|appear)\b",
        r"\b(change|alter|edit|fake|forge|falsify|fabricate)\b.{0,30}\b(date|dates|receipt|invoice|report|document|proof)\b",
        r"\bpretend\b.{0,40}\b(happened|after|before)\b",
        r"\b(palsu(kan)?|ubah tanggal|seolah(-olah)?)\b"],
        "edit_document_dates",
        "I can't help change dates or documents. If the facts don't fit the policy, I can explain the rules "
        "or suggest what to ask your insurer."),
    "credential_request": ([
        r"\b(what('s| is)|tell me|give me|show me|reveal)\b.{0,25}\b(your |the )?(password|api key|secret|credentials?|passport number|system prompt)\b"],
        "request_credentials",
        "I never ask for or share passwords, keys or ID numbers."),
    "payout_guarantee": ([
        r"\b(guarantee|promise|assure)\b.{0,40}\b(paid|payout|pay out|approved|approval|reimburse\w*|get my money)\b"],
        "guarantee_payout",
        "I can only give an indicative estimate. Only your insurer can decide whether a claim is paid."),
    "real_submission": ([
        r"\b(submit|send|file|forward)\b.{0,30}\b(to|with)\b.{0,15}\b(my |the |our )?(real|actual|live)\b.{0,15}\b(insurer|insurance|company)\b"],
        "submit_to_real_insurer",
        "This demo can't contact a real insurer. I can prepare the claim and submit it to the sandbox portal."),
    "real_money": ([
        r"\b(transfer|wire)\b.{0,30}\b(money|funds|\$\s?\d[\d,]*|usd\s?\d|\d[\d,]*\s?(usd|dollars))\b"],
        "transfer_real_money",
        "I can't move real money. Everything here is a simulation."),
    "policy_change_real": ([
        r"\b(can|could|would|will) you\b.{0,20}\b(cancel|terminate|buy|purchase)\b.{0,25}\bpolic",
        r"^\s*(please\s+)?(cancel|terminate|buy|purchase)\b.{0,25}\bpolic"],
        "buy_or_cancel_policy_real",
        "I can't buy or cancel real policies. I can compare options and explain what to look for."),
}
_FORBIDDEN = {k: ([re.compile(p, I) for p in pats], tool, msg) for k, (pats, tool, msg) in FORBIDDEN.items()}
INJECTION_MESSAGE = ("That looks like an instruction to override my rules, so I won't follow it. "
                     "Ask me about your policy and I'll answer from its text.")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total, alt = total + d, not alt
    return total % 10 == 0


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{6,8}\b")
_LONGNUM = re.compile(r"(?<![\d+-])\d(?:[ -]?\d){12,18}(?![\d-])")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"(?<![\w.])(?:\+\d{1,3}[ -]?)?\d{3,4}[ -]\d{3,4}[ -]\d{3,5}(?![\w])")


def mask_pii(text: str) -> tuple[str, list[str]]:
    kinds = []

    def sub(pattern, tag, kind, check=None):
        nonlocal text
        def repl(m):
            if check and not check(m.group(0)):
                return m.group(0)
            kinds.append(kind)
            return tag
        text = pattern.sub(repl, text)

    sub(_EMAIL, "[EMAIL]", "email")
    sub(_SSN, "[ID_NUMBER]", "id_number")
    sub(_LONGNUM, "[CARD_OR_ID_NUMBER]", "card_or_id_number",
        lambda s: 13 <= len(re.sub(r"\D", "", s)) <= 19)
    sub(_PASSPORT, "[PASSPORT]", "passport")
    sub(_PHONE, "[PHONE]", "phone")
    return text, kinds


@dataclass
class GuardResult:
    flags: list[str] = field(default_factory=list)
    blocked: bool = False
    t2_tool: str | None = None
    message: str | None = None
    masked_text: str = ""
    pii: list[str] = field(default_factory=list)


def scan_document(text: str) -> list[str]:
    """Untuk teks dari dokumen (klausul polis, nama file). Hanya mendeteksi, tidak menolak."""
    text = (text or "").replace("_", " ")          # nama file seperti ignore_previous_instructions
    return ["prompt_injection"] if any(p.search(text) for p in INJECTION) else []


def check_message(text: str) -> GuardResult:
    text = text or ""
    masked, pii = mask_pii(text)
    g = GuardResult(masked_text=masked, pii=pii)
    for name, (pats, tool, msg) in _FORBIDDEN.items():
        if any(p.search(text) for p in pats):
            g.flags.append(name)
            if g.t2_tool is None:
                g.t2_tool, g.message = tool, msg
    if scan_document(text):
        g.flags.append("prompt_injection")
        g.message = g.message or INJECTION_MESSAGE
    g.blocked = bool(g.flags)
    return g


def quarantine_policy(policy):
    """Buang klausul yang berisi instruksi tersembunyi, beserta cakupan yang bersandar padanya."""
    findings, clean = [], {}
    for cid, text in policy.clauses.items():
        flags = scan_document(text)
        if flags:
            findings.append((f"clause {cid}", flags))
        else:
            clean[cid] = text
    coverages = [c for c in policy.coverages if c.source_clause in clean]
    return policy.model_copy(update={"clauses": clean, "coverages": coverages}), findings
