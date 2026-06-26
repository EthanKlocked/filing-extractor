"""merge된 모델이 맥(MPS)에서 실제로 공시→JSON 추출하나 빠른 확인."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.schema import FilingExtract  # noqa: E402

MERGED = Path(__file__).resolve().parent / "merged"
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    tok = AutoTokenizer.from_pretrained(str(MERGED))
    model = AutoModelForCausalLM.from_pretrained(str(MERGED), dtype=torch.float16).to(DEVICE)
    model.eval()
    rows = [json.loads(l) for l in (ROOT / "data" / "sft_test.jsonl").open()][:n]
    print(f"device={DEVICE} | test {len(rows)}개\n")

    for i, r in enumerate(rows):
        prompt = tok.apply_chat_template(r["prompt"], tokenize=False, add_generation_prompt=True)
        inp = tok(prompt, return_tensors="pt").to(DEVICE)
        t0 = time.time()
        with torch.no_grad():
            out = model.generate(**inp, max_new_tokens=768, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        dt = time.time() - t0
        pred = tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True)
        m = re.search(r"\{.*\}", pred, re.DOTALL)
        valid = False
        if m:
            try:
                FilingExtract.model_validate_json(m.group(0)); valid = True
            except Exception:
                pass
        print(f"[{r['ticker']} {r['filingType']} {r['section']}] {dt:.1f}s | valid={valid}")
        print(pred[:280], "...\n")


if __name__ == "__main__":
    main()
