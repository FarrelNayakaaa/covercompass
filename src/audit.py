import sqlite3, json, hashlib, time


class Audit:
    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS audit(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, session_id TEXT, event TEXT, tool TEXT, tier TEXT,
                decision TEXT, user_confirmed INTEGER, summary TEXT,
                args_hash TEXT, outcome TEXT)""")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def log(self, session_id, event, tool=None, tier=None, decision=None,
            user_confirmed=False, summary="", outcome="ok", args=None):
        h = None
        if args is not None:
            h = hashlib.sha256(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()[:12]
        with self._conn() as c:
            c.execute(
                "INSERT INTO audit(ts, session_id, event, tool, tier, decision, user_confirmed,"
                " summary, args_hash, outcome) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), session_id, event, tool,
                 tier, decision, int(bool(user_confirmed)), summary, h, outcome))

    def rows(self, session_id=None):
        q, p = "SELECT * FROM audit", ()
        if session_id:
            q, p = q + " WHERE session_id=?", (session_id,)
        with self._conn() as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute(q + " ORDER BY id", p)]

    def export_jsonl(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            for r in self.rows():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
