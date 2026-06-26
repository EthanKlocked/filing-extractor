# 03 — QLoRA SFT (클라우드 GPU)

공시 섹션 → `FilingExtract` JSON 추출 학생 모델을, 4-bit QLoRA로 Qwen2.5-3B-Instruct에 SFT.

## 왜 클라우드 GPU인가
QLoRA의 4-bit 양자화 커널(bitsandbytes)은 **CUDA 전용** → 맥(MPS)에선 안 됨.
3B엔 **RTX 4090(24GB) 한 대면 충분**. 학습 1~2시간, 실비 ~$1~3.
무료로 하려면 Colab(T4)도 가능(느림·끊김).

## 데이터 준비 (맥에서, GPU 전)
```bash
python ../02-distillation-data/build_dataset.py split   # train/val/test.jsonl
python format_sft.py                                     # sft_train/val/test.jsonl (chat 포맷)
```

## GPU에서 실행 (Runpod 예시)
```bash
# 1) Runpod에서 RTX 4090 + PyTorch 이미지 인스턴스 생성 → SSH 접속
# 2) 코드+데이터 업로드 (이 디렉토리 + ../data/sft_*.jsonl, ../common/)
pip install -r requirements-gpu.txt
python train.py --smoke      # 파이프라인 검증 (몇 스텝)
python train.py              # 본 학습 → outputs/adapter/
# 3) outputs/adapter/ 를 맥으로 내려받고 인스턴스 종료(과금 정지)
```

## 산출물
- `outputs/adapter/` — LoRA 어댑터(수백 MB). 04 서빙 / 05 평가에서 베이스+어댑터로 로드.

## 핵심 설정 (train.py)
- 4-bit nf4 + double quant, bf16 compute / LoRA r=16 α=32, attn+mlp 전체 타깃
- `completion_only_loss=True` — prompt(공시) 마스킹, JSON 출력에만 loss
- `max_len=8192` — 입력(공시)을 토큰단위로 잘라 정답 JSON은 항상 보존 (format_sft)

## 검증 포인트
베이스(Qwen2.5-3B-Instruct, 튠 전) vs 튠 후를 **05 평가**에서 정량 비교 →
JSON valid% · 필드 정확도 개선폭으로 "QLoRA SFT 효과"를 수치로 입증.
