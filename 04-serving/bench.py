"""로컬 llama-server(Q4 GGUF) 벤치 — test셋으로 valid JSON % + 지연 측정.

서버: llama-server -m filing-extractor-q4_k_m.gguf -c 12288 -ngl 99 --port 8080
결과: data/preds_local_q4.jsonl (score.py로 클라우드 결과와 동일 채점 가능).
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.schema import FilingExtract  # noqa: E402
sys.path.insert(0, str(ROOT / "08-constrained-decoding"))
from schema_grammar import bounded_schema  # noqa: E402

# raw /completion + HF 동일 프롬프트 + JSON 스키마 제약 디코딩(grammar).
# 서버 chat 템플릿 불일치 회피 + 항상 유효/완결 JSON 보장. MCP도 이 방식.
URL = "http://127.0.0.1:8080/completion"
DATA = ROOT / "data"
_tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct")
_SCHEMA = bounded_schema()


def call(messages, max_tokens=1024):
    prompt = _tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    body = json.dumps({
        "prompt": prompt, "n_predict": max_tokens, "temperature": 0,
        "json_schema": _SCHEMA,
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return out["content"], time.time() - t0


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 47
    rows = [json.loads(l) for l in (DATA / "sft_test.jsonl").open()][:n]
    out_path = DATA / "preds_local_q4.jsonl"
    valid = 0; lat = 0.0
    with out_path.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            pred, dt = call(r["prompt"])
            lat += dt
            m = re.search(r"\{.*\}", pred, re.DOTALL)
            ok = False
            if m:
                try:
                    FilingExtract.model_validate_json(m.group(0)); ok = True
                except Exception:
                    pass
            valid += ok
            f.write(json.dumps({
                "ticker": r["ticker"], "filingType": r["filingType"], "section": r["section"],
                "gold": r["completion"][0]["content"], "pred": pred, "latency_s": round(dt, 3),
            }, ensure_ascii=False) + "\n")
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(rows)}  valid={valid}  avg {lat/(i+1):.1f}s")
    print(f"\n로컬 Q4 서빙: valid {100*valid/len(rows):.1f}% | 평균 지연 {lat/len(rows):.2f}s/예제")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
