# PLAN — Filing-Extraction Co-Processor

## 목표

프로필 기술갭(모델을 *쓰는* 사람 → 모델을 *학습·서빙·평가하는* 사람)을 GUIDE 9단계로 실제로 채운다.
가짜 토이가 아니라 **돌아가는 결과물 + 정량 수치**가 매 단계 산출물.

## 무엇을 만드나

금융 공시(SEC 10-Q/10-K · DART) 원문에서 투자 판단에 필요한 정보를 **구조화 JSON으로 추출**하는
소형 모델. distill→QLoRA로 튠하고, 로컬 서빙하고, **MCP 서버**로 패키징해서
실제 운영 중인 Claude Code 투자비서(`~/Desktop/investment/toss-stock-trading`)에 끼워넣어 검증.

## 두 공간

- **개발/학습 = 이 레포(`llm-work`, 공개 포트폴리오)** — 기술 경험 라인
- **실사용/검증 = 투자비서(private, 운영 중)** — 실용성·검증 라인. MCP를 끼워 dogfooding.

## 스택 = 하이브리드

- 대부분 맥(M4 Pro, 24GB, MPS)에서 로컬·무료
- 3(QLoRA)·4(vLLM 벤치)만 클라우드 Linux GPU 잠깐 임대(SSH). GPU 옵스 자체도 산출물화.
- 총비용 현실 ~$15~25. Python은 3.12로 핀(3.14는 torch 휠 미지원 우려).

## 단계 (★ = 차별화 핵심)

1. **기본기** — PyTorch(MPS)+HF, 토크나이저·attention 관찰, 미니 학습루프(loss/overfit/split)
2. **데이터셋(distill)** — 공시 원문 → frontier(teacher) 라벨 → instruction/JSON 포맷 → train/val/test, **누수방지·dedup**, DATA_CARD
3. ★ **QLoRA SFT** — 3B 오픈모델(예: Qwen2.5-3B)에 4bit QLoRA(PEFT/TRL/bitsandbytes). 베이스 대비 정량 개선 확인
4. **서빙** — vLLM OpenAI호환(클라우드 벤치: 처리량/p95/비용) + llama.cpp 로컬 상시 서빙. 양자화(AWQ/GGUF)
5. ★ **평가** — frontier vs 튠모델 품질(필드정확도·JSON valid%·judge)·지연·비용 3축. LLM-as-judge+골드셋+회귀
6. **하이브리드 검색+리랭킹** — 공시 코퍼스에 벡터+BM25+크로스인코더. 검색 품질 정량 비교
7. **Agentic RAG** — LangGraph 반복검색·쿼리재작성·자기검증. naive vs agentic 정확도·비용
8. **스키마 제약 디코딩** — 출력 JSON 강제, 타입·키·교차필드 불변식, 위반 시 재시도/복구
9. ★ **캡스톤(MCP화)** — 1~8을 MCP 서버 하나로. 투자비서에 끼워 실제 브리핑/스크리닝 → 비용절감% 입증

**순서:** 1→2→3→4→5→9 (메인) / 6→7, 8 (병행).

## 첫 통과(end-to-end 1회) 태스크

**공시 → 구조화 JSON 추출** 하나로 전체 파이프라인을 끝까지 돌린다.
(뉴스 4그룹 분류 등은 검증된 파이프라인 위에 나중에 확장.)

## 정직한 전제

- 검증 결과가 음수(로컬이 frontier만 못함)로 나올 수도 있음 → 그것도 진짜 결과.
  "어디까지 로컬에 맡길 수 있는지 경계를 정량으로 그었다"가 성숙한 서사.
- 로컬 모델은 **추출/triage** 용. 투자 판단까지 시키지 않는다.

## 프라이버시 (나중에 확정)

공개 레포에는 **공개 데이터만**(SEC/DART 공시는 public) + frontier distill 라벨.
실제 개인 매매·포지션 데이터는 로컬에서만, 푸시 금지.
