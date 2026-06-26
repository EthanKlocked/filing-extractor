# 로드맵 & 서비스화 아키텍처 (이어가기용 핸드오프)

> 다른 디바이스/세션에서 이어서 작업할 때 이 문서부터 읽으면 맥락이 복원됨.
> 작성 기준일: 2026-06-26.

---

## 1. 프로젝트 한 줄

SEC 공시(10-Q/10-K) → 구조화 JSON 추출 로컬 소형모델 + MCP. frontier LLM이 매 분석마다
반복하던 공시 해석을 distill·QLoRA로 튠한 로컬 3B로 오프로드(토큰비용·지연↓, 출력정합성↑).

## 2. 현재 상태 (완료)

| 단계 | 산출물 | 결과 |
|---|---|---|
| 02 데이터 | SEC 공시 456건 distill 라벨(Gemini Flash) + 종목단위 split | $2.78 |
| 03 학습 | Qwen2.5-3B에 4bit QLoRA SFT (Runpod RTX4090) | 어댑터 57MB |
| 05 평가 | base vs tuned | valid 6%→**87%**, 필드정확도 **+67%p** |
| 04 서빙 | merge→GGUF(f16 5.8GB)→양자화(Q8 3.1GB/Q4 1.8GB)→llama-server(Metal) | 로컬·무료 |
| 08 제약디코딩 | JSON 스키마 grammar + 배열 maxItems | 로컬 valid **89%** |

총 실지출 ~$4.3 (Gemini $2.78 + GPU $1.5). 상세: [05-eval/RESULTS.md](../05-eval/RESULTS.md).

**핵심 발견(디버깅):** ① transformers+MPS 4GB 텐서한계→llama.cpp ② smoke로 NaN 2종
차단(dtype/정답잘림) ③ chat템플릿 불일치→raw /completion ④ 자유생성 폭주→제약디코딩.

## 3. 두 레포 구조

| 레포 | 역할 |
|---|---|
| **filing-extractor** (이 레포, 공개) | 모델 **생산·평가·서빙·보관** (라이프사이클). 공개 SEC 데이터만 |
| **투자비서**(toss-stock-trading, private) | 모델 **소비자**. MCP를 `.mcp.json`에 등록해 호출 |

## 4. 서비스화 아키텍처 (목표 = 계층 분리)

```
① filing-extractor (이 레포)   모델 생산·관리
      학습→평가→GGUF 빌드 → [아티팩트: 어댑터/GGUF → HF Hub]
                         ↓ serverize
② 서빙 레이어                  모델 → OpenAI호환 HTTP 엔드포인트 (llama-server)
                         ↑ HTTP(얇은 호출)
③ MCP 레이어 (얇음)            엔드포인트 감싸 툴 노출 → 투자비서 .mcp.json 등록
```

**원칙:**
- MCP는 **모델을 품지 않음** — 별도로 떠 있는 llama-server를 HTTP로 호출하는 *얇은 래퍼*.
- 무거운 모델(GGUF)은 **HF Hub에 두고 pull** (Ollama `pull`과 동일 원리). MCP 클론은 가볍게.
- `merge`/양자화는 **일회성 빌드**(모델 레포). MCP 런타임엔 없음.

**MCP를 별도 레포로?** — 정석은 그렇지만 **순서가 중요**:
1. v1(지금): 이 레포 `09-capstone-mcp/`에 MCP를 두고 투자비서에 끼워 **dogfooding 먼저**.
2. 값어치 검증되면 → MCP를 **별도 레포로 추출** + GGUF는 HF Hub로 (졸업).
- 미리 3-레포로 쪼개면 over-engineering. 검증 후 분리.

> 참고: "모델을 직접 호스팅하는 MCP"는 드문 패턴(대부분 MCP는 원격 API 래퍼). 우리는
> *API비용 회피·로컬처리*라는 분명한 목적으로 택한 **실험적 통합**. 정직하게 그렇게 포지셔닝.

## 5. 운영 트레이드오프 (정직)

| 항목 | 값 |
|---|---|
| 추론 중 메모리 | Q8 ~4~6GB / Q4 ~3~5GB (KV캐시가 긴 컨텍스트라 큼) |
| 지연 | ~21초/예제 (클라우드 API ~2~5초보다 느림) |
| 비용 | $0 (로컬) ↔ 클라우드 API |
| 실용 ROI | **modest** — 투자비서 토큰 실측상 공시추출은 tool토큰의 ~8.6% |

→ "비싼 frontier ↔ 내 기기 RAM/지연" 교환. 종목 몇 개 triage엔 OK, 대량·실시간엔 부담.
**메모리 다이어트 레버:** Q4 / `-c` 축소 / KV캐시 양자화(`-ctk q8_0`) / 온디맨드 로드.
**프로젝트 1차 가치 = 모델 레이어 직접 구축(기술)**, dogfooding은 "경계를 정량으로 긋는" 보조.

## 6. 남은 작업

- **09 MCP화 + dogfooding** (캡스톤, 미착수)
  - `09-capstone-mcp/`에 얇은 MCP: 입력 공시텍스트 → HF 동일프롬프트 → llama-server `/completion`(+json_schema 제약) → FilingExtract JSON
  - **온디맨드 lifecycle** 권장(유휴 시 자원 0)
  - 투자비서 `.mcp.json`에 등록 → 실제 브리핑/스크리닝에서 토큰·지연 절감 실측
- **(선택 v2)**
  - 약한 필드 보강: `grossMarginTrend`(enum 27.8%), `goingConcernDoubt`(0/20, null 누락) → 데이터 보강·재라벨 후 재학습
  - 양자화 비교: Q5_K_M/Q6_K로 필드정확도-크기 절충점 탐색
  - GGUF를 HF Hub에 업로드(서빙 포터블)
  - 사람 검수 골드셋(소량) + 회귀 테스트 (현재 gold=teacher 라벨)
  - 더 공정한 베이스라인: 스키마+few-shot 프롬프트 base vs 튠

## 7. 새 디바이스에서 이어가기

```bash
git clone git@github.com:EthanKlocked/filing-extractor.git
cd filing-extractor
uv venv --python 3.12 && uv pip install -r requirements-mac.txt
cp .env.example .env          # GEMINI_API_KEY 채우기 (시크릿, 레포에 없음)
```
레포에 있음: 전 파이프라인 코드 + 학습된 어댑터(57MB) + 가공데이터 + 결과.
재생성 필요(없어도 됨): `data/raw`(fetch.py) / `merged`·`*.gguf`(merge.py+양자화) / `.venv`.

**재학습**: `data/sft_*.jsonl`(레포에 있음)로 `03-finetune-qlora/train.py` 실행(GPU 필요).
**서빙 재구성**: `04-serving/merge.py` → GGUF 변환 → `llama-server` → `04-serving/bench.py`.

## 8. 핵심 결정 로그 (왜 이렇게 했나)

- **도메인**: 문항(업무) 대신 **투자 공시** — 본인 운영 시스템(투자비서)에 dogfooding 가능 + 공개 SEC.
- **하이브리드 스택**: 대부분 맥 로컬, QLoRA만 클라우드 GPU(bitsandbytes=CUDA 전용).
- **teacher = Gemini Flash**: 보유 키 + 추출 품질 충분 + 저비용.
- **종목단위 split**: 같은 회사 공시가 train/test 양쪽에 안 들어가게(누수 방지).
- **completion_only_loss**: prompt(공시) 마스킹, JSON에만 loss. TRL 1.7 prompt/completion 포맷.
- **입력 토큰 truncation**: 정답(JSON)은 항상 보존, 입력 공시를 토큰단위로 컷(NaN 차단).
- **Q8 채택**: Q4보다 필드정확도 유지. **제약디코딩 필수**(자유생성은 폭주).
- **어댑터 git 포함**: 57MB, 디바이스 포터블 위해 .gitignore 예외. gguf는 재생성(미포함).
