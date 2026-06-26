"""GPU 빌리기 전 맥에서 무료 검증.

확인: (1) sft 데이터 로딩, (2) Qwen chat 템플릿 적용, (3) 토큰 길이 분포(max_len 적정?),
(4) assistant_only_loss 마스킹 가능 여부(템플릿이 generation 마커 지원?).
실패하면 GPU 시간 낭비 전에 여기서 잡는다.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "Qwen/Qwen2.5-3B-Instruct"
DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    tok = AutoTokenizer.from_pretrained(MODEL)
    rows = [json.loads(l) for l in (DATA / "sft_train.jsonl").open()]
    print(f"sft_train: {len(rows)} examples | tokenizer: {MODEL}")

    # (2)(3) chat 템플릿 적용 + 토큰 길이 (prompt+completion 전체)
    # tokenize=False로 렌더 후 인코딩 (버전별 반환형 차이 회피)
    lens = [len(tok(tok.apply_chat_template(r["prompt"] + r["completion"], tokenize=False))["input_ids"])
            for r in rows]
    lens.sort()
    med = int(statistics.median(lens))
    p90 = lens[int(len(lens) * 0.9)]
    print(f"\n토큰 길이: min {lens[0]} / median {med} / p90 {p90} / max {lens[-1]}")
    for cap in (4096, 8192, 16384):
        over = sum(1 for x in lens if x > cap)
        print(f"  > {cap:>5}: {over:3d}개 ({100*over/len(lens):.0f}%) 초과")

    # (4) prompt/completion 포맷 + completion_only_loss 마스킹 검증
    #     TRL이 내부에서 하는 토큰화/마스킹 경계를 재현해 확인.
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    r = rows[0]
    prompt_text = tok.apply_chat_template(r["prompt"], tokenize=False, add_generation_prompt=True)
    full_text = tok.apply_chat_template(r["prompt"] + r["completion"], tokenize=False)
    prompt_ids = tok(prompt_text)["input_ids"]
    full_ids = tok(full_text)["input_ids"]
    # completion_only_loss: prompt 길이만큼 -100, 나머지(completion)만 학습
    n_prompt = len(prompt_ids)
    n_comp = len(full_ids) - n_prompt
    print(f"\nprompt/completion 마스킹: prompt {n_prompt} 토큰(마스킹) / completion {n_comp} 토큰(학습)")
    boundary = tok.decode(full_ids[n_prompt - 4:n_prompt + 6])
    comp_head = tok.decode(full_ids[n_prompt:n_prompt + 12])
    print(f"  경계 부근: {boundary!r}")
    print(f"  학습 시작(completion 머리): {comp_head!r}")
    if comp_head.lstrip().startswith("{") and n_comp > 0 and full_ids[:n_prompt] == prompt_ids:
        print("  ✅ prompt(system+user) 마스킹 + completion(JSON)에만 loss — 정상")
    else:
        print("  ⚠️ 경계 불일치 — 포맷/템플릿 점검 필요")

    print("\n--- 렌더된 학습 텍스트(앞 240자) ---")
    print(full_text[:240])
    print("--- (끝 160자) ---")
    print(full_text[-160:])


if __name__ == "__main__":
    main()
