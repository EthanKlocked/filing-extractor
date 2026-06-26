# DATA_CARD — Filing Extraction distillation set (v1)

- 총 예제: **456** (1 예제 = 공시 1섹션 → FilingExtract)
- teacher: `gemini-2.5-flash` (distillation 라벨)
- 토큰: 입력 6,708,000 / 출력 306,840

## 분포
- 종목군: {'large_profitable': 200, 'loss_turnaround_volatile': 121, 'growth_recent_profit': 101, 'biotech_often_loss': 34}
- 공시타입: {'10-Q': 350, '10-K': 106}
- 섹션: {'MD&A': 280, 'FinancialStatements': 176}
- 수익성(isProfitable): {'None': 87, 'True': 250, 'False': 119}  ← 흑/적자 다양성 확인
- revenue.yoyGrowth 존재: 395/456

## 출처/라이선스
- SEC EDGAR 공개 공시(US). 개인 비공개 데이터 없음.
- 라벨은 teacher 모델 distillation 산출물(검증 골드셋은 별도 수작업 예정).

## 누수 방지
- train/val/test는 **종목 단위**로 분할(같은 회사 공시가 두 split에 안 걸침).
