"""Which radar source predicts real growth? (Renaissance-style: weigh each weak signal by its track record.)

For every pair of radar weeks (t, t+h): rank categories by each source at week t, and by the change in Basalam
weekly sales from t to t+h. The rank agreement (Spearman) per source, averaged over all pairs, is that source's
skill. Weights = skill clipped at 0, normalised. Used only after MIN_WEEKS weeks; until then all sources weigh 1."""
from __future__ import annotations

import json

from . import config as C

MIN_WEEKS = 8
HORIZON = 4          # weeks ahead
KEYS = ["week", "dk_reviews", "ads", "ig"]


def _rank(vals: dict) -> dict:
    order = sorted(vals, key=lambda k: vals[k])
    return {k: i for i, k in enumerate(order)}


def spearman(a: dict, b: dict) -> float | None:
    ks = [k for k in a if k in b]
    n = len(ks)
    if n < 10:
        return None
    ra, rb = _rank({k: a[k] for k in ks}), _rank({k: b[k] for k in ks})
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in ks) / (n * (n * n - 1))


def learn(hist: list[dict], horizon: int = HORIZON) -> dict:
    skill: dict[str, list[float]] = {k: [] for k in KEYS}
    for i in range(len(hist) - horizon):
        now, later = hist[i]["cats"], hist[i + horizon]["cats"]
        growth = {q: (later[q]["week"] - r["week"]) / max(r["week"], 1) for q, r in now.items()
                  if q in later and r.get("week") is not None and later[q].get("week") is not None}
        for k in KEYS:
            s = spearman({q: r[k] for q, r in now.items() if r.get(k) is not None}, growth)
            if s is not None:
                skill[k].append(s)
    avg = {k: sum(v) / len(v) for k, v in skill.items() if v}
    pos = {k: max(0.0, v) for k, v in avg.items()}
    tot = sum(pos.values())
    return {"weeks": len(hist), "pairs": max(0, len(hist) - horizon), "skill": avg,
            "weights": {k: v / tot * len(pos) for k, v in pos.items()} if tot else {},
            "active": len(hist) >= MIN_WEEKS and tot > 0}


def save(res: dict) -> None:
    d = C.DATA_DIR / "radar"
    d.mkdir(parents=True, exist_ok=True)
    (d / "weights.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def load() -> dict:
    f = C.DATA_DIR / "radar" / "weights.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
