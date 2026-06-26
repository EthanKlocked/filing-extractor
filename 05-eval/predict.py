"""베이스 vs 튠 모델로 test셋 추론 → 예측 저장 (pod/GPU에서, 학습 직후).

  python predict.py --base                          # 튠 전 베이스
  python predict.py --adapter ../03-finetune-qlora/outputs/adapter   # 튠 후

각 예제의 prompt(system+공시)로 생성 → completion(JSON) 텍스트를 예측으로 저장.
gold(teacher 라벨)도 같이 저장 → score.py가 비교.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BASE = "Qwen/Qwen2.5-3B-Instruct"


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", default=None, help="LoRA 어댑터 경로 (없으면 베이스)")
    p.add_argument("--base", action="store_true", help="베이스 모델로 추론")
    p.add_argument("--out", default=None, help="출력 파일 (기본: preds_base/preds_tuned)")
    p.add_argument("--max_new", type=int, default=1024)
    return p.parse_args()


def main():
    a = parse()
    tag = "base" if (a.base or not a.adapter) else "tuned"
    out_path = Path(a.out) if a.out else DATA / f"preds_{tag}.jsonl"

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, dtype=torch.bfloat16, device_map="auto")
    if a.adapter and not a.base:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, a.adapter)
        print("어댑터 로드:", a.adapter)
    model.eval()

    rows = [json.loads(l) for l in (DATA / "sft_test.jsonl").open()]
    print(f"[{tag}] test {len(rows)}개 추론 시작")

    n_lat = 0.0
    with out_path.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            prompt_text = tok.apply_chat_template(
                r["prompt"], tokenize=False, add_generation_prompt=True)
            inputs = tok(prompt_text, return_tensors="pt").to(model.device)
            t0 = time.time()
            with torch.no_grad():
                gen = model.generate(
                    **inputs, max_new_tokens=a.max_new, do_sample=False,
                    pad_token_id=tok.pad_token_id)
            dt = time.time() - t0
            n_lat += dt
            new_tokens = gen[0][inputs["input_ids"].shape[1]:]
            pred = tok.decode(new_tokens, skip_special_tokens=True)
            gold = r["completion"][0]["content"]
            f.write(json.dumps({
                "ticker": r["ticker"], "filingType": r["filingType"], "section": r["section"],
                "gold": gold, "pred": pred, "latency_s": round(dt, 3),
            }, ensure_ascii=False) + "\n")
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(rows)}  avg {n_lat/(i+1):.2f}s/예제")

    print(f"[{tag}] 저장: {out_path} | 평균 지연 {n_lat/len(rows):.2f}s/예제")


if __name__ == "__main__":
    main()
