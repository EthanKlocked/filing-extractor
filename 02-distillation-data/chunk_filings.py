"""SEC 공시 HTML → 타깃 섹션 청크 추출.

설계(docs/00 §5): 10-Q/10-K 통째 입력 X. 관련 섹션(MD&A·재무제표)만 잘라
청크 단위로 입력 → teacher가 청크별 FilingExtract 라벨 → 학생도 청크→추출 학습.

10-Q 섹션 마커는 목차(TOC)와 본문에 2번 등장 → 마지막 출현 기준으로 본문 슬라이스.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import tiktoken

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    ticker: str
    filingType: str
    accession: str
    section: str          # "MD&A" | "FinancialStatements"
    text: str
    n_tokens: int


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# (섹션명, 시작 패턴, 끝 패턴) — 끝은 다음 Item 시작
_SECTIONS_10Q = [
    ("FinancialStatements",
     r"item\s*1\.?\s*financial statements",
     r"item\s*2\.?\s*management.s discussion"),
    ("MD&A",
     r"item\s*2\.?\s*management.s discussion",
     r"item\s*3\.?\s*quantitative"),
]

# 10-K: Item 7 = MD&A, Item 8 = 재무제표
_SECTIONS_10K = [
    ("MD&A",
     r"item\s*7\.?\s*management.s discussion",
     r"item\s*7a\.?\s*quantitative"),
    ("FinancialStatements",
     r"item\s*8\.?\s*financial statements",
     r"item\s*9\.?\s*changes in and disagreements"),
]


def _sections_for(filing_type: str):
    return _SECTIONS_10K if filing_type.upper() == "10-K" else _SECTIONS_10Q


def _slice_last(text: str, start_pat: str, end_pat: str) -> str | None:
    low = text.lower()
    starts = [m.start() for m in re.finditer(start_pat, low)]
    ends = [m.start() for m in re.finditer(end_pat, low)]
    if not starts:
        return None
    s = starts[-1]
    # 시작 이후의 첫 end 사용 (없으면 끝까지)
    e = next((x for x in ends if x > s), len(text))
    seg = text[s:e].strip()
    return seg or None


def chunk_filing(html: str, ticker: str, filing_type: str, accession: str) -> list[Chunk]:
    text = html_to_text(html)
    out: list[Chunk] = []
    sections = _sections_for(filing_type)
    for name, sp, ep in sections:
        seg = _slice_last(text, sp, ep)
        if seg and len(seg) > 200:
            out.append(Chunk(ticker, filing_type, accession, name,
                             seg, len(_ENC.encode(seg))))
    return out


def chunks_from_raw(raw_dir: str = "data/raw/sec-edgar-filings") -> list[Chunk]:
    """data/raw 아래 받아둔 모든 공시를 청크로."""
    chunks: list[Chunk] = []
    for primary in Path(raw_dir).glob("*/*/*/primary-document.html"):
        # 경로: .../<TICKER>/<FORM>/<ACCESSION>/primary-document.html
        accession = primary.parent.name
        filing_type = primary.parent.parent.name
        ticker = primary.parent.parent.parent.name
        html = primary.read_text(encoding="utf-8", errors="ignore")
        chunks.extend(chunk_filing(html, ticker, filing_type, accession))
    return chunks


if __name__ == "__main__":
    cs = chunks_from_raw()
    print(f"총 청크: {len(cs)}")
    for c in cs:
        print(f"  [{c.ticker} {c.filingType} {c.section}] {c.n_tokens:,} tokens  ({c.accession})")
        print("    미리보기:", re.sub(r"\s+", " ", c.text[:140]))
