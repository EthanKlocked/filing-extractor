"""QLoRA SFT — 공시 섹션 → FilingExtract JSON 추출 학생 모델 학습.

클라우드 GPU(CUDA)에서 실행. 4-bit QLoRA(bitsandbytes) + LoRA(peft) + TRL SFTTrainer.
베이스: Qwen2.5-3B-Instruct (32K ctx, 구조화 출력 강함).

  python train.py --smoke           # 몇 스텝만 (파이프라인 검증)
  python train.py                    # 본 학습

산출물: outputs/adapter/ (LoRA 어댑터, 수백 MB) → 맥으로 내려받아 04 서빙/05 평가.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer


def parse():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen2.5-3B-Instruct")
    p.add_argument("--data", default="../data")          # sft_train.jsonl / sft_val.jsonl
    p.add_argument("--out", default="outputs")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--lr", type=float, default=2e-4)
    p.add_argument("--bsz", type=int, default=1)
    p.add_argument("--grad_accum", type=int, default=16)
    p.add_argument("--max_len", type=int, default=8192)  # 긴 재무제표 청크 수용 (메모리와 trade-off)
    p.add_argument("--lora_r", type=int, default=16)
    p.add_argument("--lora_alpha", type=int, default=32)
    p.add_argument("--smoke", action="store_true")
    return p.parse_args()


def main():
    a = parse()
    assert torch.cuda.is_available(), "CUDA GPU 필요 (Runpod/Colab). 맥에선 bitsandbytes 안 돎."
    data = Path(a.data)

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        a.model, quantization_config=bnb, torch_dtype=torch.bfloat16, device_map="auto",
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    lora = LoraConfig(
        r=a.lora_r, lora_alpha=a.lora_alpha, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )

    ds = load_dataset("json", data_files={
        "train": str(data / "sft_train.jsonl"),
        "val": str(data / "sft_val.jsonl"),
    })
    if a.smoke:
        ds["train"] = ds["train"].select(range(min(16, len(ds["train"]))))
        ds["val"] = ds["val"].select(range(min(8, len(ds["val"]))))

    cfg = SFTConfig(
        output_dir=a.out,
        num_train_epochs=1 if a.smoke else a.epochs,
        max_steps=8 if a.smoke else -1,
        per_device_train_batch_size=a.bsz,
        gradient_accumulation_steps=a.grad_accum,
        learning_rate=a.lr,
        bf16=True,
        max_length=a.max_len,
        packing=False,
        assistant_only_loss=True,         # assistant(JSON)에만 loss
        logging_steps=5,
        eval_strategy="steps", eval_steps=50,
        save_strategy="epoch",
        warmup_ratio=0.03, lr_scheduler_type="cosine",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model, args=cfg,
        train_dataset=ds["train"], eval_dataset=ds["val"],
        peft_config=lora, processing_class=tok,
    )
    trainer.train()
    trainer.save_model(str(Path(a.out) / "adapter"))
    tok.save_pretrained(str(Path(a.out) / "adapter"))
    print("저장 완료:", Path(a.out) / "adapter")


if __name__ == "__main__":
    main()
