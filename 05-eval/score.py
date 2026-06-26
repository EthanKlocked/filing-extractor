"""예측(preds_*.jsonl)을 골드(teacher 라벨)와 비교 → 정량 지표. 어디서나 실행.

  python score.py            # preds_base.jsonl vs preds_tuned.jsonl 비교표

지표:
- JSON valid %     : 스키마(FilingExtract) 통과 비율
- 필드 정확도       : gold의 비-null 스칼라 필드를 맞춘 비율 (숫자=허용오차, enum/bool=정확)
- null 정확도       : gold가 null인 필드를 null로 뒀는지 (환각 안 했는지)
- 평균 지연         : 예제당 추론 시간

주의: 여기서 gold = teacher(Gemini) 라벨. 즉 "학생이 teacher 추출을 얼마나 재현하나".
사람 검수 골드는 별도(소량)로 추가 예정 — DATA_CARD 참고.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.schema import FilingExtract  # noqa: E402

DATA = ROOT / "data"

# 채점할 스칼라 필드 (경로, 타입)
NUM = "num"; EXACT = "exact"
FIELDS = [
    ("meta.ticker", EXACT), ("meta.filingType", EXACT), ("meta.market", EXACT),
    ("meta.periodEnd", EXACT), ("meta.currency", EXACT),
    ("revenue.valueReported", NUM), ("revenue.yoyGrowth", NUM), ("revenue.qoqGrowth", NUM),
    ("profitability.gaapNetIncome", NUM), ("profitability.isProfitable", EXACT),
    ("profitability.grossMarginTrend", EXACT), ("profitability.epsDiluted", NUM),
    ("profitability.epsAcceleration", EXACT),
    ("accounting.auditOpinion", EXACT), ("accounting.restatementMentioned", EXACT),
    ("accounting.goingConcernDoubt", EXACT),
]


def get(d: dict, path: str):
    cur = d
    for k in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def parse_pred(text: str):
    """모델 출력에서 JSON 추출 + 스키마 검증. 실패시 (None, False)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None, False
    try:
        obj = FilingExtract.model_validate_json(m.group(0))
        return obj.model_dump(mode="json"), True
    except Exception:
        # JSON은 되지만 스키마 위반 → invalid 처리하되 raw dict는 비교용 시도
        try:
            return json.loads(m.group(0)), False
        except Exception:
            return None, False


def num_match(a, b, rel=0.02, abs_=1e-6):
    try:
        a = float(a); b = float(b)
    except (TypeError, ValueError):
        return False
    if abs(a - b) <= abs_:
        return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= rel


def score_file(path: Path):
    rows = [json.loads(l) for l in path.open()]
    n = len(rows)
    valid = 0
    hit = tot = 0           # gold 비-null 필드 정확도
    null_hit = null_tot = 0 # gold null 필드 → pred도 null?
    lat = 0.0
    per_field = {f: [0, 0] for f, _ in FIELDS}  # [hit, tot]

    for r in rows:
        lat += r.get("latency_s", 0)
        gold, _ = parse_pred(r["gold"])      # gold는 항상 valid (teacher)
        pred, ok = parse_pred(r["pred"])
        if ok:
            valid += 1
        if gold is None:
            continue
        pred = pred or {}
        for path_, typ in FIELDS:
            g = get(gold, path_); p = get(pred, path_)
            if g is None:
                null_tot += 1
                if p is None:
                    null_hit += 1
                continue
            tot += 1
            per_field[path_][1] += 1
            match = num_match(g, p) if typ == NUM else (g == p)
            if match:
                hit += 1
                per_field[path_][0] += 1

    return {
        "n": n,
        "json_valid_pct": 100 * valid / n,
        "field_acc_pct": 100 * hit / max(tot, 1),
        "null_acc_pct": 100 * null_hit / max(null_tot, 1),
        "avg_latency_s": lat / n,
        "per_field": per_field,
    }


TAGS = [("base", "base"), ("tuned", "tuned(cloud)"), ("local_q4", "local Q4")]


def main():
    results = {}
    for tag, _ in TAGS:
        p = DATA / f"preds_{tag}.jsonl"
        if p.exists():
            results[tag] = score_file(p)

    if not results:
        print("preds_*.jsonl 없음 — 먼저 predict.py / bench.py 실행"); return

    cols = [(t, lbl) for t, lbl in TAGS if t in results]
    width = 60 + max(0, (len(cols) - 2)) * 14
    print("=" * width)
    print(f"{'지표':<22}" + "".join(f"{lbl:>14}" for _, lbl in cols))
    print("-" * width)
    keys = [("json_valid_pct", "JSON valid %"), ("field_acc_pct", "필드 정확도 %"),
            ("null_acc_pct", "null 정확도 %"), ("avg_latency_s", "평균 지연(s)")]
    for k, label in keys:
        row = f"{label:<22}" + "".join(f"{results[t][k]:>14.2f}" for t, _ in cols)
        print(row)
    print("=" * width)

    if "base" in results and "tuned" in results:
        d = results["tuned"]["field_acc_pct"] - results["base"]["field_acc_pct"]
        print(f"\n필드 정확도 개선: base→tuned {d:+.1f}%p")
        print("\n[필드별 tuned 정확도]")
        for f, (h, t) in results["tuned"]["per_field"].items():
            if t:
                print(f"  {f:<34} {100*h/t:5.1f}%  ({h}/{t})")

    (Path(__file__).resolve().parent / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nresults.json 저장")


if __name__ == "__main__":
    main()
