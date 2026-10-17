import math, re
from collections import Counter

STOP = {"a", "an", "the", "of", "to", "and", "or", "in", "on", "for", "is", "are", "be", "do",
        "does", "my", "me", "i", "it", "we", "you", "your", "our", "if", "any", "this", "that",
        "can", "with", "at", "by", "as", "am", "was", "will", "what", "how", "get"}


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


class ClauseIndex:
    """BM25 sederhana atas klausul polis (tanpa dependensi tambahan)."""

    def __init__(self, policies, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = []
        for p in policies:
            name_tokens = tokenize(p.name)
            for cid, text in p.clauses.items():
                toks = tokenize(text) + name_tokens
                self.docs.append({"policy_id": p.policy_id, "clause": cid, "text": text,
                                  "tokens": toks, "tf": Counter(toks)})
        n = len(self.docs)
        self.avg_len = (sum(len(d["tokens"]) for d in self.docs) / n) if n else 0
        df = Counter(t for d in self.docs for t in set(d["tokens"]))
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, policy_id: str | None = None, top_k: int = 4) -> list[dict]:
        q = tokenize(query)
        results = []
        for d in self.docs:
            if policy_id and d["policy_id"] != policy_id:
                continue
            score = 0.0
            dl = len(d["tokens"])
            for t in q:
                f = d["tf"].get(t, 0)
                if f:
                    score += self.idf.get(t, 0) * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * dl / (self.avg_len or 1)))
            if score > 0:
                results.append({"policy_id": d["policy_id"], "clause": d["clause"],
                                "text": d["text"], "score": round(score, 3)})
        return sorted(results, key=lambda r: -r["score"])[:top_k]
