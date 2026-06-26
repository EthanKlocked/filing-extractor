# Filing-Extraction Co-Processor

> 비싼 frontier LLM 호출을, 직접 distill·QLoRA 파인튜닝한 **로컬 소형 모델**로 오프로드하는 실험.
> 도메인: **금융 공시(SEC 10-Q/10-K · DART) → 구조화 JSON 추출**.
> 최종 산출물: 추출 전용 **MCP 서버**를 실제 운영 중인 Claude Code 기반 투자비서에 끼워넣어 검증.

---

## 한 줄 요약

기존 MCP(sec-edgar / DART)가 가져오는 **공시 원문(raw)** 을, 지금은 frontier Claude가 매번 직접
해석·구조화·채점한다. 이 반복적·기계적 추출 레이어를 **튠한 로컬 3B 모델**로 대체하고,
**품질 동등성 + 비용·지연 절감**을 정량으로 증명한다.

```
[sec-edgar / DART MCP]  →  공시 원문(raw)
          │
          ▼
  ★ 코프로세서 MCP ★   = 베이스 3B → distill 데이터로 QLoRA SFT → 로컬 서빙
  (공시 원문 → 정형화된 구조화 JSON, 스키마 제약 디코딩으로 항상 valid)
          │
          ▼  압축된 구조화 JSON
  [frontier Claude]  →  최종 투자 판단
```

frontier를 **대체**하는 게 아니라 앞단 **triage/추출 레이어**다. 투자 판단은 frontier가 계속 한다.

## 왜 이 프로젝트인가 (기술갭)

기존 역량은 LLM을 **API로 *쓰는*** 애플리케이션/파이프라인(LangChain·LangGraph·MCP·RAG)에 강하다.
비어있는 곳은 **모델 레이어** — 직접 *학습·파인튜닝·서빙·정량평가*. 이 레포가 그 갭을 채운다.

## 구조 (모노레포)

| 디렉토리 | 내용 | 어디서 |
|---|---|---|
| `01-fundamentals/` | PyTorch(MPS)+HF, 토크나이저·미니 학습루프 | 맥 |
| `02-distillation-data/` | 공시 원문 → frontier 라벨 → 학습셋(누수방지·dedup) | 맥+API |
| `03-finetune-qlora/` | 3B에 QLoRA SFT, 베이스 대비 정량 개선 | 클라우드 GPU |
| `04-serving/` | vLLM 벤치 + llama.cpp 로컬 서빙, 양자화 | 클라우드/맥 |
| `05-eval/` | frontier vs 튠모델 품질/지연/비용 정량 비교 | 맥+API |
| `06-hybrid-search/` | 벡터+BM25+크로스인코더 리랭킹 | 맥 |
| `07-agentic-rag/` | LangGraph 공시 딥리서치 루프 | 맥+API |
| `08-constrained-decoding/` | 스키마 제약 디코딩 + Pydantic 불변식 | 맥 |
| `09-capstone-mcp/` | 위를 MCP 서버로 패키징 → 투자비서에 끼워 dogfooding | 맥+클라우드 |

자세한 계획은 [PLAN.md](PLAN.md), 추출 태스크 설계는 [docs/00-design-filing-extraction.md](docs/00-design-filing-extraction.md).

## 상태

🚧 진행 중. **핵심 결과 (v1):** 베이스 Qwen2.5-3B는 공시 구조화 추출을 거의 못 함
(JSON valid 6%, 필드정확도 2%). 362-예제 distillation + **QLoRA SFT로 valid 87% /
필드정확도 69% (+67%p)** 달성 — 자세히는 [05-eval/RESULTS.md](05-eval/RESULTS.md).

- [x] 01~03: 데이터(456 distill 라벨) → QLoRA SFT (Runpod RTX4090, ~$1.5)
- [x] 05: 베이스 vs 튠 정량 평가
- [ ] 04 서빙(llama.cpp/양자화) · 08 스키마 제약 디코딩 · 09 MCP화 + 투자비서 dogfooding
