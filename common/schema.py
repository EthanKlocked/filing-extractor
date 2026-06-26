"""FilingExtract — 공시 → 구조화 JSON 추출 스키마 (단일 진실 소스).

설계: docs/00-design-filing-extraction.md
v1 스코프: US(SEC) 10-Q/10-K, 핵심 필드(meta/revenue/profitability/accounting/catalysts).
guidance/insiderActivity는 스키마엔 존재하되 v1 라벨링·평가 대상에서 제외(v2 확장).

모든 사실 필드는 nullable: 공시에 없으면 None. 환각으로 채우지 않는다.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---- enums (자유서술 대신 고정 → 제약 디코딩/정량 채점 용이) ----

class Market(str, Enum):
    US = "US"
    KR = "KR"


class FilingType(str, Enum):
    TEN_Q = "10-Q"
    TEN_K = "10-K"
    EIGHT_K = "8-K"
    DART_ANNUAL = "DART-사업보고서"
    OTHER = "other"


class MarginTrend(str, Enum):
    EXPANDING = "expanding"
    STABLE = "stable"
    CONTRACTING = "contracting"


class Specificity(str, Enum):
    DATED = "dated"
    WITHIN_QUARTER = "within_quarter"
    WITHIN_YEAR = "within_year"
    VAGUE = "vague"


class AuditOpinion(str, Enum):
    UNQUALIFIED = "unqualified"  # 적정
    QUALIFIED = "qualified"
    ADVERSE = "adverse"
    DISCLAIMER = "disclaimer"


class Direction(str, Enum):
    BUY = "buy"
    SELL = "sell"


# ---- sub-models ----

class Meta(BaseModel):
    ticker: Optional[str] = None
    company: Optional[str] = None
    market: Market
    filingType: FilingType
    periodEnd: Optional[str] = Field(None, description="보고 기간 종료일 ISO(YYYY-MM-DD), 모르면 None")
    currency: Optional[str] = None


class Revenue(BaseModel):
    valueReported: Optional[float] = Field(None, description="당기 매출 (보고 통화)")
    yoyGrowth: Optional[float] = Field(None, description="전년동기比, 소수(0.45=45%)")
    qoqGrowth: Optional[float] = None
    sourceSpan: Optional[str] = Field(None, description="추출 근거 원문 인용")


class Profitability(BaseModel):
    gaapNetIncome: Optional[float] = Field(None, description="GAAP 순이익 (적자면 음수)")
    isProfitable: Optional[bool] = None
    grossMarginTrend: Optional[MarginTrend] = None
    epsDiluted: Optional[float] = None
    epsAcceleration: Optional[bool] = Field(None, description="QoQ EPS 2배+ 가속, 애매하면 None")
    sourceSpan: Optional[str] = None

    @model_validator(mode="after")
    def _check_profit_consistency(self) -> "Profitability":
        # 교차필드 불변식: 순이익 부호와 흑자 여부 일치 (part 8 검증의 씨앗)
        if self.gaapNetIncome is not None and self.isProfitable is not None:
            if (self.gaapNetIncome > 0) != self.isProfitable:
                raise ValueError(
                    f"isProfitable({self.isProfitable})가 gaapNetIncome({self.gaapNetIncome}) 부호와 불일치"
                )
        return self


class Catalyst(BaseModel):
    description: str
    date: Optional[str] = Field(None, description="특정 가능하면 ISO/분기(2026-Q3), 아니면 None")
    specificity: Specificity
    thirdPartyValidation: bool = Field(
        False, description="대형수주 $50M+/전략파트너십/기관투자 동반 여부"
    )


class Accounting(BaseModel):
    auditOpinion: Optional[AuditOpinion] = None
    restatementMentioned: Optional[bool] = None
    goingConcernDoubt: Optional[bool] = None
    sourceSpan: Optional[str] = None


# ---- v2 확장 (스키마엔 존재, v1 평가 제외) ----

class Guidance(BaseModel):
    provided: Optional[bool] = None
    summary: Optional[str] = None
    sourceSpan: Optional[str] = None


class InsiderTrade(BaseModel):
    name: str
    role: Optional[str] = None
    direction: Direction
    valueUSD: Optional[float] = None
    date: Optional[str] = None
    plan10b5_1: Optional[bool] = None
    sourceSpan: Optional[str] = None


# ---- 최상위 ----

class FilingExtract(BaseModel):
    """공시 1건 → 구조화 추출 결과."""

    meta: Meta
    revenue: Revenue = Field(default_factory=Revenue)
    profitability: Profitability = Field(default_factory=Profitability)
    accounting: Accounting = Field(default_factory=Accounting)
    catalysts: list[Catalyst] = Field(default_factory=list)

    # v2 확장
    guidance: Optional[Guidance] = None
    insiderActivity: list[InsiderTrade] = Field(default_factory=list)

    extractionNotes: Optional[str] = None


# v1 라벨링/평가가 채점할 핵심 필드 그룹 (guidance/insider 제외)
V1_CORE_SECTIONS = ("meta", "revenue", "profitability", "accounting", "catalysts")


if __name__ == "__main__":
    # 자체 검증: 정상 샘플 + 불변식 위반 샘플
    import json

    sample = {
        "meta": {"ticker": "NVDA", "company": "NVIDIA Corp", "market": "US",
                 "filingType": "10-Q", "periodEnd": "2026-04-30", "currency": "USD"},
        "revenue": {"valueReported": 26044000000, "yoyGrowth": 0.45, "qoqGrowth": 0.12,
                    "sourceSpan": "Revenue was $26.0 billion, up 45% year-over-year"},
        "profitability": {"gaapNetIncome": 14881000000, "isProfitable": True,
                          "grossMarginTrend": "expanding", "epsDiluted": 0.60,
                          "epsAcceleration": True, "sourceSpan": "..."},
        "accounting": {"auditOpinion": "unqualified", "restatementMentioned": False,
                       "goingConcernDoubt": False, "sourceSpan": "..."},
        "catalysts": [{"description": "신규 DC GPU 출하", "date": "2026-Q3",
                       "specificity": "dated", "thirdPartyValidation": False}],
    }
    obj = FilingExtract.model_validate(sample)
    print("OK 정상 샘플 검증 통과:", obj.meta.ticker, "| catalysts:", len(obj.catalysts))
    print(json.dumps(obj.model_dump(mode="json", exclude_none=True), ensure_ascii=False)[:120], "...")

    # 불변식 위반: 적자인데 isProfitable=True
    try:
        FilingExtract.model_validate({
            **sample,
            "profitability": {"gaapNetIncome": -500, "isProfitable": True},
        })
        print("FAIL: 불변식이 위반을 못 잡음")
    except Exception as e:
        print("OK 불변식이 위반 탐지:", str(e).splitlines()[0][:60])
