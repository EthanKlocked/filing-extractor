"""02 split(train/val/test.jsonl) → SFT chat 포맷(sft_*.jsonl).

각 예제 = system(추출지시) + user(공시 섹션 텍스트) → assistant(FilingExtract JSON).
teacher가 만든 라벨을 정답 completion으로. 학습은 assistant 부분에만 loss(03 train.py).

★ 핵심: 정답(completion)은 절대 자르지 않는다. 입력(공시)을 토큰 기준으로 잘라
   system+공시+정답이 항상 MAX_LEN 안에 들게 → 긴 예제도 채점 토큰 0 방지(NaN 차단).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.prompts import EXTRACTION_SYSTEM  # noqa: E402

DATA = ROOT / "data"
MODEL = "Qwen/Qwen2.5-3B-Instruct"   # train.py와 동일 토크나이저
MAX_LEN = 8192                        # train.py max_len과 일치
MARGIN = 96                           # 템플릿 토큰 등 여유

_tok = AutoTokenizer.from_pretrained(MODEL)


def _ntok(text: str) -> int:
    return len(_tok(text)["input_ids"])


def to_example(rec: dict) -> tuple[dict, bool]:
    """입력 공시를 토큰 예산만큼만 남기고 잘라 정답을 항상 보존."""
    completion = json.dumps(rec["output"], ensure_ascii=False)
    # system + completion + 템플릿이 차지하는 토큰 → 나머지가 공시(user) 예산
    fixed = _ntok(EXTRACTION_SYSTEM) + _ntok(completion) + MARGIN
    user_budget = MAX_LEN - fixed

    user = rec["input_text"]
    truncated = False
    if _ntok(user) > user_budget:
        # 앞부분 유지(손익계산서·매출은 상단) — 토큰 단위로 정확히 컷
        ids = _tok(user)["input_ids"][:user_budget]
        user = _tok.decode(ids)
        truncated = True

    ex = {
        "prompt": [
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": user},
        ],
        "completion": [
            {"role": "assistant", "content": completion},
        ],
        "ticker": rec["ticker"], "filingType": rec["filingType"], "section": rec["section"],
    }
    return ex, truncated


def main():
    for split in ("train", "val", "test"):
        src = DATA / f"{split}.jsonl"
        if not src.exists():
            print(f"skip {split} (없음 — 먼저 build_dataset.py split)"); continue
        n = trunc = 0
        with (DATA / f"sft_{split}.jsonl").open("w", encoding="utf-8") as out:
            for line in src.open():
                if not line.strip():
                    continue
                ex, t = to_example(json.loads(line))
                trunc += t
                out.write(json.dumps(ex, ensure_ascii=False) + "\n")
                n += 1
        print(f"sft_{split}.jsonl: {n} examples ({trunc} 입력 truncated, 정답은 전부 보존)")


if __name__ == "__main__":
    main()
