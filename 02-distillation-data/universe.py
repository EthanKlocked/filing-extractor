"""학습셋용 종목 유니버스 — 라벨 다양성 확보가 목적.

대형 흑자주만 모으면 라벨이 '흑자+성장' 한쪽으로 쏠려 모델이 적자/턴어라운드/
감액 케이스를 못 배운다. 그래서 의도적으로 섞는다:
- 대형 흑자 (다양한 섹터)
- 고성장/최근흑자전환
- 적자/턴어라운드/고변동 중소형
- 바이오 (상시 적자 흔함)
"""

UNIVERSE = {
    "large_profitable": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "ORCL",
        "JPM", "JNJ", "PG", "KO", "WMT", "XOM", "UNH", "V", "MA", "HD", "COST",
    ],
    "growth_recent_profit": [
        "TSLA", "NFLX", "CRM", "AMD", "SHOP", "UBER", "PLTR", "ABNB", "SNOW", "DDOG",
    ],
    "loss_turnaround_volatile": [
        "RIVN", "LCID", "PLUG", "SOFI", "AFRM", "CVNA", "OPEN", "NKLA",
        "RUN", "FUBO", "CHPT", "DKNG", "RBLX", "U", "HOOD",
    ],
    "biotech_often_loss": [
        "MRNA", "BNTX", "NVAX", "BEAM", "CRSP", "EXAS",
    ],
}

ALL = [t for group in UNIVERSE.values() for t in group]

if __name__ == "__main__":
    for g, ts in UNIVERSE.items():
        print(f"{g:28s} {len(ts):2d}  {' '.join(ts)}")
    print(f"\n총 {len(ALL)}개 종목 / 중복 {len(ALL)-len(set(ALL))}")
