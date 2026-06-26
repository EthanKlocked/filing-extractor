# 02 — Distillation 데이터셋 (공시 → 구조화 JSON)

teacher(Gemini Flash)로 SEC 공시 섹션 → `FilingExtract` JSON 라벨을 만들어,
로컬 학생 모델 SFT용 학습셋을 구축한다. (distillation)

## 파이프라인
```
universe.py   50종목 (대형흑자/고성장/적자·턴어라운드/바이오 — 라벨 다양성)
   └ fetch.py        SEC EDGAR 10-Q×5 / 10-K×2 수집 (full-submission.txt는 삭제)
       └ chunk_filings.py   HTML → MD&A·재무제표 섹션 청크 (코드, 무료)
           └ build_dataset.py label   청크 → Flash 라벨 (동시성8+체크포인트+재시도)
               └ build_dataset.py split   종목 단위 train/val/test (누수방지)
                   └ format_sft.py        chat 포맷 sft_*.jsonl (assistant=JSON)
```

## 결과 (v1)
- **456 예제** (1예제 = 공시 1섹션 → FilingExtract), 라벨 에러 0
- teacher: `gemini-2.5-flash`, 실비 **$2.78** (in 6.7M / out 0.31M 토큰)
- split: train 362 / val 47 / test 47 — **종목 비중복(누수검증 통과)**
- 다양성: 흑자 250 / 적자 119 / 불명 87, 10-Q 350 / 10-K 106

자세한 분포는 [DATA_CARD.md](DATA_CARD.md).

## 핵심 설계 결정
- **종목 단위 split**: 같은 회사 공시가 train/test에 동시에 안 들어가게 → 회사 암기 방지, 평가 신뢰성.
- **dedup**: 동일 텍스트(보일러플레이트/중복제출) 제거 + 길이 필터(200~28K토큰).
- **teacher=student 동일 시스템프롬프트** ([common/prompts.py](../common/prompts.py)) → 입출력 분포 일치.
- **스키마 강제**: teacher 호출에 Pydantic 스키마(structured output) → 항상 valid JSON.

## 알려진 한계 (v1 → v2 개선거리)
- **입력 truncation**: sft 변환 시 32K자(≈8K토큰) 초과분 앞부분만 유지(292/362 truncated).
  매출·수익성(상단)은 보존되나, 뒤쪽 catalysts는 잘려 라벨-입력 불일치 소지.
  → 평가(05)에서 영향 측정 후 필요 시 max_len 상향 또는 truncated 텍스트 재라벨.
- 골드셋(사람 검수 정답)은 미구축 → 05 평가 전 소량(50~100) 수작업 예정.
- 라벨은 teacher(Flash) 산출물이라 teacher 오류가 상한선(예: 청크별 grossMarginTrend 불일치 관찰됨).

## 재현
```bash
python fetch.py                              # SEC 수집 (data/raw, gitignore)
python build_dataset.py label                # 라벨링 (GEMINI_API_KEY 필요)
python build_dataset.py split && python build_dataset.py card
python ../03-finetune-qlora/format_sft.py    # sft_*.jsonl
```
