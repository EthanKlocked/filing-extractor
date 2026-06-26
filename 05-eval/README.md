# 05 — 평가 (베이스 vs 튠 모델 정량 비교) ★

QLoRA 튜닝이 실제로 효과 있었나를 **숫자로** 증명. 이 프로젝트의 차별화 핵심.

## 무엇을 재나
- **JSON valid %**: 출력이 FilingExtract 스키마를 통과하는 비율
- **필드 정확도 %**: gold의 비-null 스칼라 필드(매출·수익성·회계 등)를 맞춘 비율 (숫자=허용오차 2%, enum/bool=정확)
- **null 정확도 %**: gold가 null인 필드를 null로 뒀나 (환각 안 했나)
- **평균 지연(s)**: 예제당 추론 시간 (로컬 튠 모델 vs 상용 API 비교 근거)

> gold = teacher(Gemini) 라벨 → "학생이 teacher 추출을 얼마나 재현하나"를 측정.
> 사람 검수 골드(소량)는 v2에서 추가 (DATA_CARD 참고).

## 실행

**1) 추론 — pod(GPU)에서, 학습 직후·종료 전**
```bash
cd 05-eval
python predict.py --base                                          # preds_base.jsonl (튠 전)
python predict.py --adapter ../03-finetune-qlora/outputs/adapter  # preds_tuned.jsonl (튠 후)
```

**2) 채점 — 어디서나 (맥 가능, GPU 불필요)**
```bash
python score.py          # 비교표 + results.json
```

## 회수할 것 (pod 종료 전)
- `data/preds_base.jsonl`, `data/preds_tuned.jsonl` (채점용, 작음)
- `03-finetune-qlora/outputs/adapter/` (어댑터, 서빙·보관용)

## 기대 산출물
```
지표                    base       tuned
JSON valid %           ??.??      ??.??
필드 정확도 %           ??.??      ??.??   ← 개선폭이 이력서 라인
null 정확도 %           ??.??      ??.??
평균 지연(s)            ??.??      ??.??
```
"QLoRA SFT로 필드 정확도 base 대비 +Xp, 로컬·무료로 teacher급 추출 재현" 을 입증.
