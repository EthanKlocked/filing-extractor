# PLAN — Filing-Extraction Co-Processor

## 목표

SEC 공시(10-Q/10-K)에서 투자 판단에 필요한 정보를 구조화 JSON으로 추출하는 로컬 소형 모델을
만들고, MCP 서버로 패키징해 투자 분석 파이프라인에 통합한다. 매 단계 **돌아가는 결과물 + 정량 수치**.

## 무엇을 만드나

공시 원문 → `FilingExtract` 구조화 JSON 추출 모델. distill→QLoRA로 파인튜닝, 로컬 서빙,
**MCP 서버**로 패키징. frontier LLM이 매 분석마다 반복하던 공시 해석을 오프로드해 토큰 비용·지연 절감.

- **개발 = 이 레포(`llm-work`, 공개)** — 공개 SEC 데이터만 사용
- **통합/검증 = Claude Code 투자비서(private)** — MCP를 끼워 실제 브리핑/스크리닝에서 검증

## 스택

- 대부분 로컬(M4 Pro, MPS) — 데이터·평가·서빙·디코딩
- QLoRA 학습만 클라우드 GPU(Runpod RTX4090) 단시간. Python 3.12.

## 단계

1. **데이터셋(distill)** — 공시 원문 → teacher 라벨 → instruction/JSON 포맷 → train/val/test, 누수방지·dedup, DATA_CARD ✅
2. **QLoRA SFT** — Qwen2.5-3B에 4bit QLoRA(PEFT/TRL/bitsandbytes). 베이스 대비 정량 개선 ✅
3. **평가** — base vs tuned 품질(필드정확도·JSON valid%)·지연 비교. (+사람 골드셋·회귀) ✅
4. **서빙** — llama.cpp/GGUF 로컬 서빙, 양자화
5. **스키마 제약 디코딩** — 출력 JSON 강제, 타입·키·교차필드 불변식, 위반 시 재시도/복구
6. **하이브리드 검색+리랭킹** — 공시 코퍼스에 벡터+BM25+크로스인코더, 검색 품질 정량 비교
7. **Agentic RAG** — LangGraph 반복검색·쿼리재작성·자기검증, naive vs agentic 비교
8. **MCP화 + 통합** — MCP 서버로 패키징, 투자비서에 끼워 비용·지연 절감 측정

## 설계 원칙

- 로컬 모델은 **추출/triage** 전용. 최종 투자 판단은 frontier가 수행.
- 검증 결과는 정직하게 — 로컬이 약한 필드/케이스는 경계를 정량으로 명시.

## 데이터·프라이버시

공개 레포에는 공개 SEC 공시 + teacher distill 라벨만. 개인 매매·포지션 데이터는 로컬 전용(푸시 금지).
