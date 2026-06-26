"""Teacher(Gemini)로 청크 → FilingExtract JSON 라벨 생성 (distillation).

학생 모델이 이걸 보고 배우므로 라벨 품질이 상한선. structured-output으로
우리 Pydantic 스키마를 직접 강제 → 항상 valid JSON (part 8 제약디코딩 맛보기).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.schema import FilingExtract  # noqa: E402

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type  # noqa: E402

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM = """You extract structured facts from a section of a US SEC filing (10-Q/10-K).
Output MUST conform to the provided schema.

RULES:
- Extract ONLY facts explicitly stated in THIS text. If a field is not present here, use null.
  Do NOT guess, infer, or hallucinate. Missing-but-nulled is correct; invented values are penalized.
- For every section with a `sourceSpan`, quote the exact verbatim sentence/phrase from the text
  that supports the extraction. If you cannot quote it, the value should be null.
- Numbers: report in the filing's currency, as plain numbers (e.g. 26.0 billion -> 26000000000).
  Growth rates as decimals (45% -> 0.45).
- `meta.market` is "US". Infer ticker/company/filingType/periodEnd only if stated; else null.
- catalysts: only forward-looking, explicitly described events. Empty list if none.
"""


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def label_chunk(text: str, model: str = "gemini-2.5-flash",
                hint_ticker: str | None = None, hint_type: str | None = None) -> FilingExtract:
    prompt = SYSTEM
    if hint_ticker or hint_type:
        prompt += f"\nContext hint (verify against text): ticker={hint_ticker}, filingType={hint_type}\n"
    prompt += "\n--- FILING SECTION TEXT ---\n" + text

    resp = _client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FilingExtract,   # 스키마 강제
            temperature=0.0,                 # 라벨은 결정적으로
        ),
    )
    obj = FilingExtract.model_validate_json(resp.text)  # 우리 스키마로 재검증
    usage = resp.usage_metadata
    obj_meta = {"_in": usage.prompt_token_count, "_out": usage.candidates_token_count}
    return obj, obj_meta


if __name__ == "__main__":
    import json
    from chunk_filings import chunks_from_raw

    model = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash"
    chunks = chunks_from_raw()
    print(f"=== teacher={model} | pilot {len(chunks)} chunks ===\n")
    tot_in = tot_out = 0
    for c in chunks:
        obj, m = label_chunk(c.text, model=model, hint_ticker=c.ticker, hint_type=c.filingType)
        tot_in += m["_in"]; tot_out += m["_out"]
        print(f"### [{c.ticker} {c.filingType} {c.section}] in={m['_in']} out={m['_out']}")
        print(json.dumps(obj.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2))
        print()
    print(f"=== 합계 토큰: in={tot_in:,} out={tot_out:,} ===")
