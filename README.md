# Filing-Extraction Co-Processor

SEC 공시(10-Q/10-K)에서 투자 판단에 필요한 정보를 **구조화 JSON으로 추출**하는 로컬 소형 모델과,
이를 감싼 **MCP 서버**. frontier LLM이 매 분석마다 반복하던 공시 해석·구조화를 오프로드해
**토큰 비용·지연을 줄이고 출력 정합성을 보장**한다.

---

## 개요

투자 분석 파이프라인에서 공시 원문은 보통 frontier LLM이 매번 직접 읽어 수치를 해석한다.
이 반복적·기계적 추출을 **distill·QLoRA로 파인튜닝한 로컬 3B 모델**로 대체하고,
스키마 제약 디코딩으로 항상 유효한 JSON을 보장한다. frontier는 추출 결과를 받아 *판단*에만 집중.

```
[sec-edgar / DART MCP]  →  공시 원문(raw)
          │
          ▼
  ★ Co-Processor MCP ★   = Qwen2.5-3B + QLoRA 어댑터 (로컬 서빙)
  (공시 원문 → 구조화 JSON, 스키마 제약 디코딩으로 항상 valid)
          │
          ▼  압축된 구조화 JSON
  [frontier LLM]  →  최종 투자 판단
```

추출 결과는 매수 스코어카드(매출 YoY·수익성 궤도·회계 신뢰성·촉매 등) 입력으로 바로 연결된다.

## 결과 (v1)

distillation 학습셋(SEC 공시 456건 라벨) + QLoRA SFT로:

| 지표 | base (Qwen2.5-3B) | **tuned** |
|---|---:|---:|
| JSON valid % | 6.4 | **87.2** |
| 필드 정확도 % | 1.8 | **69.0** |

베이스가 사실상 수행하지 못하던 구조화 추출을 튜닝으로 실용 수준까지 끌어올렸다.
상세·필드별·한계는 [05-eval/RESULTS.md](05-eval/RESULTS.md).

## 파이프라인

| 디렉토리 | 내용 |
|---|---|
| `02-distillation-data/` | SEC 공시 수집 → 섹션 청킹 → teacher 라벨링 → 누수방지 split |
| `03-finetune-qlora/` | Qwen2.5-3B에 4-bit QLoRA SFT (`completion_only_loss`) |
| `05-eval/` | base vs tuned 정량 비교 (JSON valid% / 필드정확도 / 지연) |
| `04-serving/` | 로컬 서빙(llama.cpp/GGUF·양자화) *(예정)* |
| `06-hybrid-search/` `07-agentic-rag/` | 공시 검색·리서치 보강 *(예정)* |
| `08-constrained-decoding/` | 스키마 제약 디코딩 + Pydantic 불변식 *(예정)* |
| `09-capstone-mcp/` | MCP 서버 패키징 + 통합 *(예정)* |

추출 스키마: [common/schema.py](common/schema.py) · 태스크 설계: [docs/00-design-filing-extraction.md](docs/00-design-filing-extraction.md)

## 스택

Python 3.12 · PyTorch · HuggingFace (transformers / peft / trl / datasets) ·
bitsandbytes (4-bit QLoRA) · Pydantic · SEC EDGAR

## 데이터

공개 SEC EDGAR 공시(US)만 사용. 라벨은 teacher 모델 distillation 산출물. 개인 비공개 데이터 없음.
