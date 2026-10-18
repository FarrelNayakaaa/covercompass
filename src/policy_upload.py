"""Unggah polis dari pengguna. Dianggap tidak tepercaya: divalidasi, dipindai, lalu dikarantina bila perlu."""
from src import guard
from src.schemas import Policy


def ingest_policy(raw: bytes, filename: str, existing_ids: set[str]):
    """Mengembalikan (policy_bersih | None, temuan, pesan_error | None).
    temuan = daftar (lokasi, [flag])."""
    try:
        policy = Policy.model_validate_json(raw)
    except Exception as e:
        return None, [], f"That file isn't a valid policy file ({type(e).__name__})."
    if policy.policy_id in existing_ids:
        return None, [], f"A policy with id {policy.policy_id} is already loaded."
    clean, findings = guard.quarantine_policy(policy)
    name_flags = guard.scan_document(filename)
    if name_flags:
        findings.append(("file name", name_flags))
    if not clean.clauses:
        return None, findings, "Nothing in that file could be used safely."
    return clean, findings, None
