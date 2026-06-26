# RUNPOD 실행 런북 — QLoRA SFT

> RTX 4090(24GB)에서 공시추출 학생 모델 학습. 실비 ~$1~2. 맥에선 SSH로만 조작.
> 핵심 원칙: **디버깅은 맥에서 끝냄(derisk 통과). pod에선 순수 학습만 → GPU 시간 최소화.**

## 0. 사전 (한 번)
- Runpod 가입 + 카드로 크레딧 $10 충전
- (선택) 어댑터를 HF Hub에 올릴 거면 무료 HF 계정 + write 토큰

## 1. Pod 생성
- **GPU**: RTX 4090 (24GB) — 1장
- **Template**: "RunPod PyTorch 2.x" (CUDA·PyTorch 기설치 이미지)
- **Disk**: Container 20GB+ (베이스 모델 ~6GB 받음)
- Deploy → SSH 접속 정보 확인

## 2. 접속 (맥 터미널)
```bash
ssh root@<pod-ip> -p <port> -i ~/.ssh/<key>   # Runpod이 안내하는 명령 그대로
```

## 3. 코드+데이터 가져오기 (git clone — 데이터도 레포에 있음)
```bash
git clone https://github.com/EthanKlocked/filing-extractor.git
cd filing-extractor/03-finetune-qlora
pip install -r requirements-gpu.txt
nvidia-smi            # GPU 인식 확인
```

## 4. 스모크 테스트 먼저 (몇 스텝, ~2분) — 깨지나 확인
```bash
python train.py --smoke
# 통과 = 데이터로딩·4bit로드·LoRA·loss·저장 경로 OK
```

## 5. 본 학습 (~1~2시간)
```bash
python train.py            # max_len=8192, epochs=3, QLoRA r=16
# 진행: loss가 떨어지는지 + eval_loss 확인
# 산출물: outputs/adapter/  (LoRA 어댑터, 수백MB)
```
> 끊김 대비: `tmux` 안에서 실행 권장 (`tmux new -s train` → 실행 → `Ctrl+b d`로 detach).

## 6. 어댑터 회수 (둘 중 하나) — pod 끄기 전 필수
**(a) HF Hub 업로드 (추천 — 포트폴리오+백업)**
```bash
pip install -U huggingface_hub
huggingface-cli login        # write 토큰 입력
huggingface-cli upload EthanKlocked/filing-extractor-qlora-3b outputs/adapter .
```
**(b) 맥으로 직접 다운로드**
```bash
# 맥에서:
scp -r -P <port> root@<pod-ip>:/workspace/filing-extractor/03-finetune-qlora/outputs/adapter ./outputs/
```

## 7. Pod 종료 (과금 정지)
- Runpod 콘솔에서 **Terminate** (Stop 아님 — Stop은 디스크 과금 계속됨)

## 검증 포인트 (이력서/평가 연결)
- 학습 중 train/eval loss 곡선 → 수렴 확인
- 베이스(튠 전) vs 어댑터(튠 후)는 **05 평가**에서 JSON valid%·필드정확도로 정량 비교
- 이 런북 자체 = GPU 인스턴스 프로비저닝·환경·비용관리 운영 경험 문서
