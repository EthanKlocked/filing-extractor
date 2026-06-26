1. **기본기** — PyTorch + HuggingFace(transformers/datasets/peft/trl) 최소 운용. 딥러닝 개념(loss·overfitting·train/val/test·attention·tokenizer) 이해 기반으로.

2. **데이터셋 구축** — 기존 LLM(API) 출력을 distillation 학습셋으로 전환하는 파이프라인. 정제·포맷(instruction/JSON)·train/test 분리·누수 방지. [문항 도메인]

3. **LoRA/QLoRA 파인튜닝** ★ — 소형 오픈모델(3B급)에 QLoRA로 SFT. "비정형 텍스트 → 구조화 문항 JSON" 태스크. 베이스 대비 성능 정량 개선 확인. [문항]

4. **서빙** — vLLM로 파인튜닝 모델 서빙 + OpenAI 호환 API 래핑. 추론 양자화(GGUF/AWQ), 처리량·p95 지연·비용 튜닝.

5. **평가** ★ — 상용 API vs 파인튜닝 모델을 품질·지연·비용 3축 비교. LLM-as-judge + 소량 라벨셋 + 회귀 테스트.

6. **하이브리드 검색 + 리랭킹** — 벡터 + BM25 + 크로스인코더. 적용 전/후 검색 품질 정량 비교. [공시]

7. **Agentic RAG** — LangGraph로 반복 검색·쿼리 재작성·자기검증 루프. 정확도 개선 + 비용 증가폭 함께 측정. [공시]

8. **스키마 제약 디코딩 + 검증** — 타입·키·교차필드 불변식 강제, 위반 시 재시도/복구. [문항·커머스]

9. **캡스톤(통합)** — 1~8을 한 서비스로: 비싼 API 호출 → 파인튜닝 소형모델 대체 + 평가 검증 + 싸게 서빙 + agentic RAG 보강. end-to-end 데모 + 비용 절감% 입증.

**순서:** 1→2→3→4→5→9 (메인), 6→7·8 (병행, 강점 확장). ★는 차별화 핵심.
