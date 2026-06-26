"""LoRA 어댑터를 베이스에 merge → 단독 모델 (GGUF 변환·서빙의 전제).

맥에서 실행. 4비트(QLoRA)는 학습 전용 — merge/서빙은 fp16 베이스에 어댑터를 흡수.
산출물: 04-serving/merged/ (~6GB, gitignore).
"""

from __future__ import annotations

from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER = Path(__file__).resolve().parent.parent / "03-finetune-qlora" / "outputs" / "adapter"
OUT = Path(__file__).resolve().parent / "merged"


def main():
    print("베이스 로드 (fp16)...")
    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float16, device_map="cpu")
    tok = AutoTokenizer.from_pretrained(BASE)

    print("어댑터 결합...", ADAPTER)
    model = PeftModel.from_pretrained(model, str(ADAPTER))
    model = model.merge_and_unload()   # 어댑터를 가중치에 흡수 → 단독 모델

    OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT), safe_serialization=True)
    tok.save_pretrained(str(OUT))
    print("저장 완료:", OUT)


if __name__ == "__main__":
    main()
