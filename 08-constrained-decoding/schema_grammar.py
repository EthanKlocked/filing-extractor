"""스키마 제약 디코딩용 JSON 스키마 (llama.cpp grammar로 변환됨).

FilingExtract Pydantic 스키마를 그대로 쓰되, 배열에 maxItems를 둬서
모델이 catalysts 등을 무한 생성하다 토큰 한도에 잘리는 것(폭주)을 방지.
→ 항상 유효+완결된 JSON 생성 후 정지.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.schema import FilingExtract  # noqa: E402

MAX_ITEMS = 8


def bounded_schema(max_items: int = MAX_ITEMS) -> dict:
    s = FilingExtract.model_json_schema()
    for arr in ("catalysts", "insiderActivity"):
        if arr in s.get("properties", {}):
            s["properties"][arr]["maxItems"] = max_items
    return s


if __name__ == "__main__":
    import json
    print(json.dumps(bounded_schema(), ensure_ascii=False)[:400], "...")
