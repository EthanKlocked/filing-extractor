"""02 distillation 데이터셋 구축 오케스트레이터.

  python build_dataset.py label   # 청크 → Flash 라벨 (동시성+체크포인트, 재개 가능)
  python build_dataset.py split   # 라벨 → train/val/test (종목 단위 누수방지)
  python build_dataset.py card    # DATA_CARD.md 통계

설계: docs/00-design-filing-extraction.md
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chunk_filings import chunks_from_raw  # noqa: E402
from label import label_chunk             # noqa: E402
from universe import UNIVERSE             # noqa: E402

DATA = ROOT / "data"
LABELED = DATA / "labeled.jsonl"          # 체크포인트 (gitignore: data/raw만 무시, 이건 커밋 가능)
MODEL = "gemini-2.5-flash"
MAX_WORKERS = 8                            # Flash 동시 호출
MIN_TOKENS = 200                           # 너무 짧은 청크 제외
MAX_TOKENS = 28000                         # teacher 입력 상한 (비용/안정성)

TICKER_GROUP = {t: g for g, ts in UNIVERSE.items() for t in ts}


def chunk_id(c) -> str:
    return hashlib.sha1(f"{c.ticker}|{c.accession}|{c.section}".encode()).hexdigest()[:16]


def text_hash(c) -> str:
    return hashlib.sha1(c.text.encode()).hexdigest()


def load_done() -> set[str]:
    if not LABELED.exists():
        return set()
    return {json.loads(l)["id"] for l in LABELED.open() if l.strip()}


def cmd_label():
    chunks = chunks_from_raw()
    # dedup: 동일 텍스트 제거(보일러플레이트/중복 제출) + 길이 필터
    seen, uniq = set(), []
    for c in chunks:
        if not (MIN_TOKENS <= c.n_tokens <= MAX_TOKENS):
            continue
        h = text_hash(c)
        if h in seen:
            continue
        seen.add(h)
        uniq.append(c)

    done = load_done()
    todo = [c for c in uniq if chunk_id(c) not in done]
    est_in = sum(c.n_tokens for c in todo)
    print(f"청크 총 {len(chunks)} → 필터/dedup후 {len(uniq)} | 이미완료 {len(done)} | 라벨대상 {len(todo)}")
    print(f"예상 입력토큰 ~{est_in:,} → Flash 대략 ${est_in/1e6*0.30 + len(todo)*700/1e6*2.5:.2f}")
    if not todo:
        print("할 것 없음."); return

    out = LABELED.open("a", encoding="utf-8")
    t0 = time.time(); ok = err = 0

    def work(c):
        obj, m = label_chunk(c.text, model=MODEL, hint_ticker=c.ticker, hint_type=c.filingType)
        return c, obj, m

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(work, c): c for c in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            c = futs[fut]
            try:
                c, obj, m = fut.result()
                rec = {
                    "id": chunk_id(c),
                    "ticker": c.ticker, "group": TICKER_GROUP.get(c.ticker, "?"),
                    "filingType": c.filingType, "accession": c.accession, "section": c.section,
                    "input_text": c.text,
                    "output": obj.model_dump(mode="json", exclude_none=True),
                    "in_tok": m["_in"], "out_tok": m["_out"],
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
                ok += 1
            except Exception as e:
                err += 1
                print(f"  ! {c.ticker} {c.section} 실패: {str(e)[:80]}")
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}  ok={ok} err={err}  {time.time()-t0:.0f}s")
    out.close()
    print(f"완료: ok={ok} err={err} | 총 {time.time()-t0:.0f}s")


def cmd_split():
    recs = [json.loads(l) for l in LABELED.open() if l.strip()]
    # 종목 단위 분할: 같은 회사 공시는 한 split에만 (누수방지). 그룹별로 8:1:1 종목 배분.
    by_group = defaultdict(set)
    for r in recs:
        by_group[r["group"]].add(r["ticker"])
    split_of_ticker = {}
    for g, tickers in by_group.items():
        ts = sorted(tickers)
        n = len(ts)
        n_test = max(1, round(n * 0.1)); n_val = max(1, round(n * 0.1))
        for i, t in enumerate(ts):
            split_of_ticker[t] = "test" if i < n_test else ("val" if i < n_test + n_val else "train")
    buckets = defaultdict(list)
    for r in recs:
        buckets[split_of_ticker[r["ticker"]]].append(r)
    for name, rows in buckets.items():
        p = DATA / f"{name}.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name:5s} {len(rows):5d} examples  /  {len(set(r['ticker'] for r in rows))} tickers")
    # 누수 검증
    for a in ("train",):
        for b in ("val", "test"):
            overlap = {r["ticker"] for r in buckets[a]} & {r["ticker"] for r in buckets[b]}
            assert not overlap, f"누수! {a}∩{b} = {overlap}"
    print("누수검증 통과: train/val/test 종목 비중복 ✅")


def cmd_card():
    recs = [json.loads(l) for l in LABELED.open() if l.strip()]
    grp = Counter(r["group"] for r in recs)
    form = Counter(r["filingType"] for r in recs)
    sec = Counter(r["section"] for r in recs)
    prof = Counter(str(r["output"].get("profitability", {}).get("isProfitable")) for r in recs)
    has_rev = sum(1 for r in recs if r["output"].get("revenue", {}).get("yoyGrowth") is not None)
    in_tok = sum(r["in_tok"] for r in recs); out_tok = sum(r["out_tok"] for r in recs)
    card = f"""# DATA_CARD — Filing Extraction distillation set (v1)

- 총 예제: **{len(recs)}** (1 예제 = 공시 1섹션 → FilingExtract)
- teacher: `{MODEL}` (distillation 라벨)
- 토큰: 입력 {in_tok:,} / 출력 {out_tok:,}

## 분포
- 종목군: {dict(grp)}
- 공시타입: {dict(form)}
- 섹션: {dict(sec)}
- 수익성(isProfitable): {dict(prof)}  ← 흑/적자 다양성 확인
- revenue.yoyGrowth 존재: {has_rev}/{len(recs)}

## 출처/라이선스
- SEC EDGAR 공개 공시(US). 개인 비공개 데이터 없음.
- 라벨은 teacher 모델 distillation 산출물(검증 골드셋은 별도 수작업 예정).

## 누수 방지
- train/val/test는 **종목 단위**로 분할(같은 회사 공시가 두 split에 안 걸침).
"""
    (Path(__file__).resolve().parent / "DATA_CARD.md").write_text(card, encoding="utf-8")
    print(card)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "label"
    {"label": cmd_label, "split": cmd_split, "card": cmd_card}[cmd]()
