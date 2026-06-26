"""02 split(train/val/test.jsonl) → SFT chat 포맷(sft_*.jsonl).

각 예제 = system(추출지시) + user(공시 섹션 텍스트) → assistant(FilingExtract JSON).
teacher가 만든 라벨을 정답 completion으로. 학습은 assistant 부분에만 loss(03 train.py).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.prompts import EXTRACTION_SYSTEM  # noqa: E402

DATA = ROOT / "data"
# 너무 긴 입력은 학습 시퀀스 폭증 → 문자수 상한(대략 토큰*4). 8192토큰 ≈ ~32k자.
MAX_CHARS = 32000


def to_example(rec: dict) -> dict:
    """TRL prompt/completion 포맷 — completion_only_loss=True가 prompt를 자동 마스킹."""
    user = rec["input_text"]
    if len(user) > MAX_CHARS:
        user = user[:MAX_CHARS]  # 앞부분 유지(손익계산서·매출은 보통 상단)
    completion = json.dumps(rec["output"], ensure_ascii=False)
    return {
        "prompt": [
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": user},
        ],
        "completion": [
            {"role": "assistant", "content": completion},
        ],
        # 메타(학습엔 안 쓰지만 추적용)
        "ticker": rec["ticker"], "filingType": rec["filingType"], "section": rec["section"],
    }


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
                rec = json.loads(line)
                if len(rec["input_text"]) > MAX_CHARS:
                    trunc += 1
                out.write(json.dumps(to_example(rec), ensure_ascii=False) + "\n")
                n += 1
        print(f"sft_{split}.jsonl: {n} examples ({trunc} truncated to {MAX_CHARS}자)")


if __name__ == "__main__":
    main()
