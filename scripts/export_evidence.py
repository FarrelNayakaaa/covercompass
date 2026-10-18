"""Kumpulkan Execution Evidence: hasil test dan audit log. Jalankan dari root repo:
    python scripts/export_evidence.py"""
import os, subprocess, sys, time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.audit import Audit

out = Path("docs/evidence"); out.mkdir(parents=True, exist_ok=True)
stamp = time.strftime("%Y%m%d_%H%M")

res = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True)
(out / f"pytest_report_{stamp}.txt").write_text(res.stdout + res.stderr)
print("pytest:", (res.stdout.strip().splitlines() or ["(no output)"])[-1])

db = os.getenv("CC_AUDIT_DB", "audit.db")
if Path(db).exists():
    audit = Audit(db)
    audit.export_jsonl(str(out / f"audit_log_{stamp}.jsonl"))
    rows = audit.rows()
    print(f"audit log: {len(rows)} entries")
    print("  by tier/decision:", dict(Counter((r["tier"], r["decision"]) for r in rows if r["tier"])))
    print("  guard events:", dict(Counter(r["decision"] for r in rows if r["event"] == "guard_flag")))
    print("  auditor results:", dict(Counter(r["decision"] for r in rows if r["event"] == "auditor_result")))
else:
    print("audit.db belum ada. Jalankan aplikasi dan lakukan demo dulu.")
print("Saved to", out)
