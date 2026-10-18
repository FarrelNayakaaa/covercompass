"""Portal asuransi tiruan (sandbox). Deterministik, tanpa angka acak."""
import sqlite3

STAGES = ["received", "in_review"]


def _conn(db_path: str):
    c = sqlite3.connect(db_path)
    c.execute("""CREATE TABLE IF NOT EXISTS claims(
        id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT, policy_id TEXT,
        amount_claimed REAL, estimated_payout REAL, summary TEXT, polls INTEGER DEFAULT 0)""")
    return c


def submit_claim(claim_id: str, policy_id: str, amount_claimed: float, estimated_payout: float,
                 summary: str, db_path: str = "sandbox.db") -> dict:
    with _conn(db_path) as c:
        cur = c.execute("INSERT INTO claims(claim_id, policy_id, amount_claimed, estimated_payout, summary)"
                        " VALUES (?,?,?,?,?)", (claim_id, policy_id, amount_claimed, estimated_payout, summary))
        ref = f"CLM-{cur.lastrowid:04d}"
    return {"reference": ref, "status": "received"}


def get_status(reference: str, db_path: str = "sandbox.db") -> dict:
    try:
        rid = int(str(reference).split("-")[1])
    except (IndexError, ValueError):
        return {"error": "unknown reference"}
    with _conn(db_path) as c:
        row = c.execute("SELECT estimated_payout, polls FROM claims WHERE id=?", (rid,)).fetchone()
        if row is None:
            return {"error": "unknown reference"}
        estimated, polls = row
        c.execute("UPDATE claims SET polls = polls + 1 WHERE id=?", (rid,))
    if polls < len(STAGES):
        return {"reference": reference, "status": STAGES[polls], "approved_amount": 0.0}
    if estimated and estimated > 0:
        return {"reference": reference, "status": "approved", "approved_amount": float(estimated)}
    return {"reference": reference, "status": "denied", "approved_amount": 0.0}
