# 04 — 로컬 서빙 + 양자화 (+ 08 제약 디코딩)

튠 모델을 맥에서 무료로 서빙. merge → GGUF → 양자화 → llama-server(OpenAI/HTTP),
JSON 스키마 제약 디코딩으로 항상 유효한 출력.

## 파이프라인
```
merge.py          어댑터 → 베이스 흡수 → 단독 모델(merged/, fp16)
  └ convert_hf_to_gguf.py   → filing-extractor-f16.gguf (5.8GB)
       └ llama-quantize       → q4_k_m(1.8GB) / q8_0(3.1GB)
            └ llama-server -ngl 99 --port 8080   (Metal 서빙)
                 └ bench.py   raw /completion + HF 동일프롬프트 + json_schema 제약
```

## 실행
```bash
python merge.py                                          # 단독 모델
python /tmp/llama.cpp/convert_hf_to_gguf.py merged --outfile filing-extractor-f16.gguf --outtype f16
llama-quantize filing-extractor-f16.gguf filing-extractor-q8_0.gguf Q8_0
llama-server -m filing-extractor-q8_0.gguf -c 12288 -ngl 99 --port 8080 &
python bench.py 47                                       # → data/preds_local_q4.jsonl
python ../05-eval/score.py                               # 3-way 비교
```

## 결과 (test 47, [05-eval/RESULTS.md](../05-eval/RESULTS.md))
| 지표 | tuned(cloud) | **local Q8+제약** |
|---|---:|---:|
| JSON valid % | 87.2 | **89.4** (제약이 구조 보장) |
| 필드 정확도 % | 69.0 | 58.4 (양자화+제약 트레이드오프) |
| 평균 지연(s) | 23.9 | 21.0 |
| 모델 크기 | 6.2GB(f16) | **3.1GB(Q8) / 1.8GB(Q4)** |
| 비용 | GPU 임대 | **로컬·무료** |

## 실전 발견 (디버깅 기록)
1. **transformers+MPS는 긴 컨텍스트 추론 불가** — 단일 텐서 4GB(2³²) 한계 → 맥은 llama.cpp/GGUF가 정답.
2. **양자화**: f16 5.8GB → Q4 1.8GB(3.2×) / Q8 3.1GB. Q4는 필드정확도 더 떨어져 Q8 채택.
3. **chat 템플릿 불일치**: `/v1/chat/completions`(서버 템플릿) ≠ 학습 포맷 → valid 급락.
   → HF로 학습과 동일 프롬프트 만들어 raw `/completion` 사용.
4. **자유 생성 시 폭주**: GGUF 모델이 멈추지 못하고 catalysts 무한·반복 루프 → 잘림.
   양자화 무관(Q8도 동일). → **08 스키마 제약 디코딩(json_schema grammar + 배열 maxItems)**로 해결.

## 참고
- 서빙용 프롬프트는 학습과 100% 동일 형식이어야 함(분포 일치) → MCP도 동일 방식.
- 제약 디코딩은 validity↑ 대가로 field accuracy 약간↓ (구조-정확도 트레이드오프).
