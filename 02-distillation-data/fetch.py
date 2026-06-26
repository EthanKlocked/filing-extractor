"""SEC EDGAR에서 유니버스의 최근 10-Q/10-K 수집.

디스크 절약: 청킹엔 primary-document.html만 필요 → 큰 full-submission.txt는 받은 뒤 삭제.
SEC 요청 한도(10 req/s)는 sec-edgar-downloader가 알아서 스로틀.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sec_edgar_downloader import Downloader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from universe import ALL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(str(ROOT / ".env"))
RAW = ROOT / "data" / "raw"

N_10Q = 5
N_10K = 2


def cleanup_big_files():
    """full-submission.txt (수 MB) 삭제 — primary-document.html만 유지."""
    freed = 0
    for p in RAW.glob("sec-edgar-filings/*/*/*/full-submission.txt"):
        freed += p.stat().st_size
        p.unlink()
    return freed


def main():
    email = os.getenv("SEC_EDGAR_EMAIL") or "ethanklocked@gmail.com"
    dl = Downloader("llm-work-research", email, str(RAW))
    ok = fail = 0
    for i, t in enumerate(ALL, 1):
        got = 0
        for form, n in (("10-Q", N_10Q), ("10-K", N_10K)):
            try:
                got += dl.get(form, t, limit=n, download_details=True)
            except Exception as e:
                print(f"  ! {t} {form} 실패: {str(e)[:60]}")
        if got:
            ok += 1
        else:
            fail += 1
        print(f"[{i:>3}/{len(ALL)}] {t:6s} filings={got}")
        if i % 10 == 0:
            freed = cleanup_big_files()
            print(f"    ...중간 정리: {freed/1e6:.0f}MB 회수")

    freed = cleanup_big_files()
    htmls = len(list(RAW.glob("sec-edgar-filings/*/*/*/primary-document.html")))
    print(f"\n완료: 성공 {ok} / 실패 {fail} 종목 | primary-document.html {htmls}개 | 최종정리 {freed/1e6:.0f}MB")


if __name__ == "__main__":
    main()
