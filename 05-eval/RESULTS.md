# 평가 결과 — 베이스 vs QLoRA 튠 (v1)

> test 47개 (종목 비중복, train과 누수 없음). gold = teacher(Gemini) 라벨.
> 베이스/튠 동일 프롬프트(스키마 *내용*은 미포함 — "conform to schema"만).

## 요약

| 지표 | base (Qwen2.5-3B) | **tuned (QLoRA)** | 변화 |
|---|---:|---:|---|
| JSON valid % | 6.38 | **87.23** | +80.9%p |
| 필드 정확도 % | 1.84 | **68.97** | **+67.1%p** |
| null 정확도 % | 100.00 | 78.86 | — |
| 평균 지연(s, 4bit/4090) | 21.97 | 23.87 | — |

**결론**: 베이스는 이 추출 태스크를 사실상 수행 못 함(valid JSON 6%). 362-예제
distillation + QLoRA SFT로 **valid 87% / 필드정확도 69%**까지 도달 → 스키마·추출
능력이 어댑터 가중치에 학습됨. "파인튜닝 효과"의 정량 입증.

> base의 null정확도 100%는 함정: 거의 빈/깨진 출력 → 전부 null로 읽혀 trivial.
> 실제 필드정확도 1.84%로 무용. 튠은 값을 실제로 채우며 69% 달성.

## 필드별 (tuned)

| 필드 | 정확도 | n | 비고 |
|---|---:|---:|---|
| meta.filingType / market | 87.2% | 47 | 견고 |
| meta.ticker | 81.2% | 32 | |
| meta.periodEnd | 80.9% | 47 | |
| profitability.isProfitable | 75.8% | 33 | |
| revenue.valueReported | 72.3% | 47 | 핵심 숫자 |
| profitability.epsDiluted | 66.7% | 12 | |
| profitability.gaapNetIncome | 60.6% | 33 | |
| revenue.yoyGrowth | 53.2% | 47 | 계산 필요 필드, 개선 여지 |
| profitability.grossMarginTrend | 27.8% | 18 | enum 분류 약함 (라벨도 불안정) |
| goingConcernDoubt | 0% | 20 | false 대신 null 누락 — v2 타깃 |
| auditOpinion / epsAcceleration / restatement | — | 1~2 | 표본 과소, 통계 무의미 |

## 정직한 한계 / v2 개선거리
- **gold = teacher 라벨**: "사람 정답"이 아니라 "teacher 재현도". 사람 검수 골드(소량) 추가 필요.
- **베이스 베이스라인이 약함**: 프롬프트에 스키마/few-shot 미포함. 더 공정한 비교 = "스키마 프롬프트 + few-shot 베이스" vs 튠.
- **약한 필드**: grossMarginTrend(enum), goingConcernDoubt(체계적 null) → 데이터 보강·라벨 정제로 개선.
- **JSON valid 87% → 100%**: part 8 스키마 제약 디코딩으로 끌어올릴 수 있음.

## 재현
```bash
# pod(GPU): python 05-eval/predict.py --base / --adapter ...
python 05-eval/score.py   # → 이 표 + results.json
```
