# 태스크 설계 — 공시 → 구조화 JSON 추출

> 이 문서가 학습 데이터·모델 목표·평가 기준을 모두 결정한다. 코딩 전에 여기서 합의.

## 1. 태스크 정의

- **입력**: 단일 공시 문서의 텍스트 (SEC 10-Q/10-K 본문 또는 섹션, DART 보고서 본문).
  실무에선 sec-edgar / korea-stock(DART) MCP가 가져온 raw 텍스트.
- **출력**: 아래 `FilingExtract` 스키마를 따르는 **구조화 JSON 1개**.
- **성격**: 추출(extractive) 중심. 모델은 *판단*하지 않고 *원문에 있는 사실을 정형화*한다.
  → 정답이 비교적 명확 → frontier vs 튠모델 정량 비교가 가능(part 5의 핵심).

## 2. 왜 이 필드들인가 (스코어카드 역추적)

`toss-stock-trading/templates/scorecard-v2.md`가 공시에서 실제로 뽑아 쓰는 항목:

| 스코어카드 항목 | 소스 | → 추출 필드 |
|---|---|---|
| 매출 성장률 YoY (직전 분기) | SEC 10-Q | `revenue.yoyGrowth` |
| 수익성 궤도 (GAAP, 마진/EPS 가속) | SEC 10-Q | `profitability.*` |
| 촉매 구체성 (날짜+내용, 제3자 밸리데이션) | 공시/IR | `catalysts[]` |
| F1 회계 신뢰성 (감사의견, 2년내 재진술) | SEC 10-K | `accounting.*` |
| 내부자 매도 5요소 | Form4 / DART 임원보고 | `insiderActivity[]` |
| PEG / Fwd P/E (밸류) | SEC + 애널리스트 | (일부만 공시에 있음 → §5 논의) |

즉 추출 결과가 스코어카드 채점 입력으로 바로 흘러간다.

## 3. 출력 스키마 초안 (`FilingExtract` v0)

```jsonc
{
  "meta": {
    "ticker": "NVDA",              // 알 수 있으면, 없으면 null
    "company": "NVIDIA Corp",
    "market": "US",               // "US" | "KR"
    "filingType": "10-Q",         // "10-Q" | "10-K" | "8-K" | "DART-사업보고서" ...
    "periodEnd": "2026-04-30",    // 보고 기간 종료일 (ISO), 모르면 null
    "currency": "USD"
  },
  "revenue": {
    "valueReported": 26044000000, // 당기 매출 (보고 통화)
    "yoyGrowth": 0.45,            // 전년동기比, 0~ (소수). 산출 불가 시 null
    "qoqGrowth": 0.12,            // 전분기比
    "sourceSpan": "Revenue for the quarter was $26.0 billion, up 45% year-over-year"
  },
  "profitability": {
    "gaapNetIncome": 14881000000, // GAAP 순이익 (적자면 음수)
    "isProfitable": true,
    "grossMarginTrend": "expanding",  // "expanding" | "stable" | "contracting" | null
    "epsDiluted": 0.60,
    "epsAcceleration": true,          // QoQ EPS 2배+ 가속 여부 (스코어카드 기준), 판단 애매하면 null
    "sourceSpan": "..."
  },
  "guidance": {                   // 가이던스 제시 여부 (8-K/IR에 흔함)
    "provided": true,
    "summary": "Q2 revenue guided to ~$28B, gross margin ~75%",
    "sourceSpan": "..."
  },
  "catalysts": [                  // 향후 촉매가 될 만한 명시적 이벤트
    {
      "description": "신규 데이터센터 GPU 출하 시작",
      "date": "2026-Q3",          // 특정 가능하면 ISO/분기, 아니면 null
      "specificity": "dated",     // "dated" | "within_quarter" | "within_year" | "vague"
      "thirdPartyValidation": false  // 대형수주 $50M+/전략파트너십/기관투자 동반?
    }
  ],
  "accounting": {
    "auditOpinion": "unqualified",      // "unqualified"(적정) | "qualified" | "adverse" | "disclaimer" | null
    "restatementMentioned": false,      // 본 공시에 재진술 언급?
    "goingConcernDoubt": false,         // 계속기업 불확실성 언급?
    "sourceSpan": "..."
  },
  "insiderActivity": [            // Form4 / DART 임원·주요주주 보고가 입력일 때만
    {
      "name": "JensHuang",
      "role": "CEO",
      "direction": "sell",       // "buy" | "sell"
      "valueUSD": 4200000,
      "date": "2026-05-12",
      "plan10b5_1": true,        // 10b5-1 선결정 매도 여부
      "sourceSpan": "..."
    }
  ],
  "extractionNotes": "본문에 가이던스 섹션 없음" // 누락/모호 사유 자유서술 (선택)
}
```

### 설계 원칙
- **모든 필드 nullable**: 공시에 없는 정보는 `null`. 환각으로 채우면 안 됨(평가에서 페널티).
- **`sourceSpan`**: 추출 근거 원문 인용 → (a) 검증 가능성, (b) part 5 평가에서 환각 탐지, (c) part 8 교차필드 검증.
- **enum 고정**: 자유서술 대신 enum → 스키마 제약 디코딩(part 8)과 정량 채점이 쉬워짐.
- **단위 명시**: 통화·비율(소수) 일관. 교차필드 불변식 가능(예: `isProfitable == (gaapNetIncome > 0)`).

## 4. 평가 기준 (미리 정의 — part 5에서 사용)
- **JSON valid %**: 스키마 통과 비율
- **필드 정확도**: 숫자 필드 허용오차 내 일치율, enum 정확도, null 판단 정확도(없는 걸 null로 뒀나)
- **환각율**: `sourceSpan`이 원문에 실제 존재하는가
- 골드라벨: 소량(50~100건)은 사람이 검수한 정답, 대량은 frontier 라벨

## 5. v1 스코프 (확정 — 2026-06-26)

> 결정: **"좁게 시작 → 확장".** 첫 통과는 아래로 고정.

1. **시장 범위**: ✅ **US(SEC)만.** KR(DART)은 v2 확장.
2. **공시 타입**: ✅ **10-Q / 10-K (재무) 중심.** insider(Form4)는 별도 스키마로 2차.
3. **입력 길이**: ✅ **섹션 청크 입력** (MD&A, 재무제표/주석 등 관련 섹션만 잘라서) → 청크별 부분추출 → 병합. 10-K 통째 입력 X.
4. **스키마 범위**: ✅ **핵심 필드 먼저** — `meta` + `revenue` + `profitability` + `accounting` + `catalysts`.
   `guidance` / `insiderActivity`는 v2 확장 (스키마엔 남겨두되 v1 라벨링/평가 대상에서 제외).

## 6. 다음 단계
이 스키마 합의 → `02-distillation-data/`에서 공개 SEC 공시 수집 + frontier 라벨링 파이프라인 구축.
