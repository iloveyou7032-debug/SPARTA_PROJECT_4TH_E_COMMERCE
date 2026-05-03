# 프로젝트 가이드

## 핵심 작업 공간
- **모든 파일 생성 및 수정은 반드시 `./송원우` 폴더 내에서 진행할 것.**
- 상위 폴더의 `pyproject.toml`을 참고하여 환경을 파악하되, **다른 팀원의 폴더는 절대 참조하지 말 것.**

---

## 프로젝트 배경 및 전략적 목표

- **핵심 과제**: 휠라(FILA)의 강력한 신발 브랜드 자산을 의류(애슬레저) 시장으로 확장하기 위한 전략 수립.
- **분석 대상**: 젝시믹스, 안다르, 룰루레몬 등 주요 경쟁사 리뷰 데이터(약 700MB) 분석 → 소비자 미충족 수요(Unmet Needs) 발굴.
- **최종 목표**: 기능성(Function)과 브랜드 헤리티지(Heritage)를 축으로 하는 2D 포지셔닝 맵 도출 및 전략적 제언.

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| 패키지 매니저 | `uv` (실행 시 항상 `uv run` 사용) |
| 환경 | MacBook Pro M4 Pro (로컬 우선주의, 외부 API 호출 금지) |
| 형태소 분석 | Kiwi (kiwipiepy) + 애슬레저 도메인 사용자 사전 |
| 토픽 모델링 | BERTopic (`jhgan/ko-sroberta-multitask` + HDBSCAN + c-TF-IDF) |
| 감성 분석 | Ollama 로컬 LLM EXAONE 3.5 (7.8B), Few-shot Prompting |
| 네트워크 분석 | NetworkX (키워드 중심성 계산) |
| 시각화 | Tableau / Streamlit (최종 포지셔닝 맵) |
| 검증 지표 | Macro-F1 score, Cohen's kappa |

---

## 단계별 기술 아키텍처 (End-to-End)

1. **전처리 (Preprocessing)**
   - Kiwi 형태소 분석기 활용
   - 애슬레저 도메인 전용 사용자 사전 구축 및 적용
   - 병렬 처리(Multiprocessing) 필수: M4 Pro 코어 최대 활용

2. **토픽 모델링 (Topic Modeling)**
   - BERTopic: `jhgan/ko-sroberta-multitask` 임베딩 + HDBSCAN 군집화 + c-TF-IDF 키워드 추출

3. **감성 분석 (ABSA)**
   - Ollama 로컬 LLM EXAONE 3.5 (7.8B) 연동
   - Few-shot Prompting으로 리뷰 속성(Aspect)별 감성 점수 산출

4. **네트워크 및 시각화 (SNA & Visualization)**
   - NetworkX 키워드 중심성 계산
   - sklearn 정규화 → 최종 포지셔닝 맵(Tableau/Streamlit) 데이터 생성

---

## 데이터 거버넌스 규칙 (엄수)

### 노이즈 통제 (Two-track Strategy)
- **필터링**: 공백 제외 5자 이하 리뷰 → 모든 분석에서 제외
- **분기 처리**:
  - 10자 미만 리뷰 → BERTopic 모델링 **제외** (노이즈 방지)
  - 10자 미만 리뷰 → ABSA(감성 분석) **포함** (데이터 활용도 극대화)

### 로컬 우선주의
- 외부 API 호출 금지
- M4 Pro 로컬 리소스(MPS/Metal 가속 포함) 활용

---

## 협업 프로토콜

- **토큰 효율**: `.claudignore`에 설정된 무거운 파일은 직접 읽지 않음. 필요 시 사용자가 제공하는 `head()` 샘플 텍스트를 바탕으로 로직 설계.
- **설명 최소화**: 코드의 논리적 정확성과 메모리 효율에 집중.
- **대용량 처리**: `chunksize` 또는 `dtype` 지정으로 메모리 절감.

---

## 하이브리드 워크플로우 (필수 규칙)

### 역할 분담

| 영역 | 파일 형식 | 담당 | 역할 |
|------|-----------|------|------|
| Core Logic | `.py` | 클로드 | 핵심 함수, 병렬처리, 대용량 연산 모듈화 |
| Experimental Sandbox | `.ipynb` | 사용자 | 시각화, 샘플 테스트, 최종 실행 |

### 1. 모듈 파일 규칙 (`.py`)
- 모든 핵심 함수, 병렬 처리 로직, 대용량 연산은 `./송원우/*.py`에 **함수 단위**로 모듈화하여 작성한다.
- 파일명은 역할을 명확히 반영한다:

| 파일명 | 역할 |
|--------|------|
| `preprocess.py` | 텍스트 정제, 형태소 분석, 필터링 |
| `user_dict.py` | Kiwi 애슬레저 도메인 사용자 사전 |
| `topic_model.py` | BERTopic 토픽 모델링 |
| `absa.py` | Ollama ABSA 감성 분석 파이프라인 |
| `sna.py` | NetworkX 키워드 중심성 분석 |
| `positioning.py` | sklearn 정규화 + 포지셔닝 맵 데이터 생성 |

### 2. 노트북 실행 셀 (Jupyter용)
- `.py` 파일을 작성하거나 수정할 때마다, 아래 형식의 **노트북 실행 코드 스니펫**을 반드시 함께 제공한다.

```python
# ── 노트북 실행 셀 ────────────────────────────────────
import importlib, sys
sys.path.insert(0, './송원우')   # 경로 미등록 시에만 필요

import module_name
importlib.reload(module_name)   # .py 수정 후 변경사항 즉시 반영

result = module_name.some_function(args)
```

- `.py` 수정 후 재실행이 필요한 경우 `importlib.reload()`를 **반드시** 포함한다.
- 함수 호출 예시까지 스니펫에 포함하여 사용자가 복붙 즉시 실행 가능하게 한다.

### 3. Token Efficiency
- `.claudignore`를 통해 `.ipynb`와 `.csv` 인덱싱을 차단한다.
- 필요한 데이터 맥락은 사용자가 직접 제공하는 `head()` 샘플을 통해서만 파악한다.

---

## 작업 완료 정의 (Definition of Done)

- 모든 코드 수정이나 파일 생성 후에는 반드시 `./송원우/MEMORY.md`를 최신 상태로 업데이트해야 함.
- 업데이트 시에는 **현재 진행 상태**, **결정된 아키텍처**, **새롭게 배운 점**을 포함할 것.
- 사용자가 명시적으로 시키지 않아도, 한 태스크가 끝나면 자동으로 메모리 수정을 제안할 것.
