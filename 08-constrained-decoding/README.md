# 08 — 스키마 제약 디코딩

모델 출력을 `FilingExtract` JSON 스키마에 **강제로 맞춰** 생성. 항상 유효+완결된 JSON 보장.

## 문제
튠 모델을 llama.cpp로 자유 생성하면 JSON을 쓰고 **멈추지 못함** — catalysts 무한 생성 /
반복 루프 → 토큰 한도에서 잘림 → invalid. (양자화 무관, Q8도 동일)

## 해결
llama.cpp의 **JSON 스키마 제약 디코딩(grammar)** 사용. 매 토큰을 스키마가 허용하는 것만
생성 → 구조적으로 항상 유효. 배열은 `maxItems`로 상한을 둬 무한 생성/잘림 방지.

- [schema_grammar.py](schema_grammar.py): `FilingExtract.model_json_schema()` + `catalysts/insiderActivity` maxItems=8
- 서버 호출: `/completion` 요청에 `"json_schema": bounded_schema()` 전달

## 효과 (test 47)
| | 자유 생성(Q8) | **제약 디코딩(Q8)** |
|---|---:|---:|
| JSON valid % | 20 | **89.4** |

## 트레이드오프 (정직)
제약 디코딩은 validity를 보장하지만, 토큰마다 문법을 강제하므로 모델이 자유롭게 내고 싶던
값에서 약간 벗어남 → 필드 정확도가 자유생성 대비 다소 낮아질 수 있음(구조 vs 정확도).
교차필드 불변식(isProfitable↔netIncome 부호) 같은 *의미* 제약은 grammar로 못 막음
→ Pydantic 검증 후 재시도/복구가 다음 보강.
