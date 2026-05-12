# 송원우 작업 메모리

---

## 1. 프로젝트 전략 목표

### 핵심 과제
**휠라(FILA)의 강력한 신발 브랜드 자산을 의류(애슬레저) 시장으로 확장**하기 위한 데이터 기반 전략 수립.

### 분석 목적
- 경쟁사(젝시믹스, 안다르, 룰루레몬) 소비자 리뷰 데이터(~700MB)를 분석하여 **미충족 수요(Unmet Needs)** 발굴
- 소비자가 현재 브랜드에서 무엇을 원하고, 무엇이 부족한지를 데이터로 증명

### 최종 산출물
- **2D 브랜드 포지셔닝 맵** (Tableau / Streamlit)
  - X축: 기능성(Functionality) — 소재, 핏, 운동 퍼포먼스 관련 언급 강도
  - Y축: 브랜드 헤리티지(Heritage) — 디자인, 감성, 브랜드 충성도 관련 언급 강도
- **전략적 제언**: 휠라가 공략해야 할 포지셔닝 공백(White Space) 식별

---

## 2. 하이브리드 워크플로우 (Hybrid Workflow) — 정밀 기술 표준

모든 작업은 아래 역할 분리 원칙을 따른다.

| 영역 | 파일 형식 | 담당 | 역할 |
|------|-----------|------|------|
| Core Logic | `.py` | 클로드 | 핵심 함수, 병렬처리, 대용량 연산 모듈화 |
| Experimental Sandbox | `.ipynb` | 사용자 | 시각화, 샘플 테스트, 최종 실행 |

### §1. 모듈 파일 규칙 (`.py`)

모든 핵심 함수는 `./송원우/*.py`에 **함수 단위**로 모듈화. 파일명은 역할을 명확히 반영한다.

| 파일명 | 역할 |
|--------|------|
| `preprocess.py` | 텍스트 정제, 형태소 분석, 필터링 |
| `user_dict.py` | Kiwi 애슬레저 도메인 사용자 사전 |
| `topic_model.py` | BERTopic 토픽 모델링 |
| `absa.py` | Ollama ABSA 감성 분석 파이프라인 |
| `sna.py` | NetworkX 키워드 중심성 분석 |
| `positioning.py` | sklearn 정규화 + 포지셔닝 맵 데이터 생성 |

### §2. 노트북 실행 셀 — 표준 스니펫 (항상 이 형식으로 제공)

`.py` 파일을 작성하거나 수정할 때마다 아래 형식의 스니펫을 **반드시** 함께 제공한다.

```python
# ── 노트북 실행 셀 ────────────────────────────────────
import importlib, sys
sys.path.insert(0, './송원우')   # 경로 미등록 시에만 필요

import module_name
importlib.reload(module_name)   # .py 수정 후 변경사항 즉시 반영

result = module_name.some_function(args)
```

**적용 원칙:**
- `.py` 수정 후 재실행이 필요한 경우 `importlib.reload()`를 **반드시** 포함한다.
- `sys.path.insert(0, './송원우')`는 노트북 위치가 프로젝트 루트일 때 기준. 위치가 다르면 경로 조정.
- 함수 호출 예시까지 스니펫에 포함하여 사용자가 **복붙 즉시 실행** 가능하게 한다.
- 여러 모듈을 동시에 로드할 경우:

```python
# ── 다중 모듈 로드 예시 ───────────────────────────────
import importlib, sys
sys.path.insert(0, './송원우')

import preprocess, topic_model, absa
for mod in [preprocess, topic_model, absa]:
    importlib.reload(mod)
```

### §3. Token Efficiency
- `.claudignore`를 통해 `.ipynb`와 `.csv` 인덱싱을 차단한다.
- 필요한 데이터 맥락은 사용자가 직접 제공하는 `head()` 샘플을 통해서만 파악한다.

---

## 3. 전처리 규칙 (Data Governance)

### 3-1. 노이즈 통제 — Two-track Strategy (엄수)

| 조건 | BERTopic 토픽 모델링 | ABSA 감성 분석 |
|------|----------------------|----------------|
| 공백 제외 **5자 이하** | ❌ 제외 | ❌ 제외 |
| 공백 제외 **6~9자** | ❌ 제외 (노이즈 방지) | ✅ 포함 |
| 공백 제외 **10자 이상** | ✅ 포함 | ✅ 포함 |

> 근거: 짧은 리뷰("좋아요", "배송빠름")는 토픽 모델링 품질을 저하시키지만, 감성 신호는 유효함.

### 3-2. 형태소 분석 (Kiwi)
- **엔진**: kiwipiepy
- **애슬레저 도메인 사용자 사전** 필수 구축:
  - 브랜드명: `젝시믹스`, `안다르`, `룰루레몬`, `필라`, `FILA`
  - 소재 용어: `에어로쿨`, `네오프렌`, `스판`, `라이크라` 등
  - 핏 용어: `허리밴드`, `레깅스핏`, `크롭` 등
- **병렬 처리(Multiprocessing)** 필수: M4 Pro 코어 최대 활용 (`multiprocessing.Pool`)

### 3-3. 텍스트 정제 순서
1. HTML 태그 / 특수문자 제거
2. 연속 공백 정규화
3. 공백 제외 길이 계산 후 5자 이하 필터링
4. Kiwi 형태소 분석 (사용자 사전 적용)
5. 불용어(stopwords) 제거
6. 길이 기준으로 BERTopic용 / ABSA용 분기

### 3-4. 로컬 우선주의
- 외부 API 호출 **금지**
- LLM: Ollama 로컬 EXAONE 3.5 (7.8B) 전용
- GPU 가속: MPS(Metal Performance Shaders) 활용

---

## 4. 기술 스택 및 환경

| 항목 | 내용 |
|------|------|
| 하드웨어 | MacBook Pro M4 Pro |
| Python | 3.13+ |
| 패키지 매니저 | `uv` (실행 시 `uv run` 필수) |
| 형태소 분석 | kiwipiepy + 도메인 사용자 사전 |
| 토픽 모델링 | BERTopic (`jhgan/ko-sroberta-multitask` + HDBSCAN + c-TF-IDF) |
| 감성 분석 | Ollama EXAONE 3.5 7.8B, Few-shot Prompting |
| 네트워크 분석 | NetworkX (키워드 중심성) |
| 정규화 | sklearn |
| 시각화 | Tableau / Streamlit, plotly, seaborn, wordcloud |
| 검증 지표 | Macro-F1 score, Cohen's kappa |

---

## 5. 파이프라인 아키텍처 (결정 완료)

```
[데이터 로드] master_preprocessed_260430.csv (624MB)
      ↓
[텍스트 정제] HTML 제거 → 공백 정규화 → 5자 이하 필터
      ↓
[형태소 분석] kiwipiepy + 애슬레저 사용자 사전 + 병렬 처리
      ↓
      ├─── [BERTopic 입력] 10자 이상만
      │      임베딩: jhgan/ko-sroberta-multitask
      │      군집화: HDBSCAN
      │      키워드: c-TF-IDF
      │
      └─── [ABSA 입력] 6자 이상 전체
             Ollama EXAONE 3.5 (7.8B)
             Few-shot Prompting
             속성(Aspect)별 감성 점수 산출
             검증: Macro-F1, Cohen's kappa
      ↓
[NetworkX SNA] 토픽별 키워드 중심성 계산
      ↓
[sklearn 정규화] 기능성 / 헤리티지 점수 스케일링
      ↓
[시각화] 2D 포지셔닝 맵 (Tableau / Streamlit)
  X축: 기능성(Functionality)
  Y축: 브랜드 헤리티지(Heritage)
```

---

## 6. 데이터 현황 (2026-05-02 기준)

### ⚠️ 데이터 정제 상태 (중요)
> **`./final_data/` 내 모든 마스터 테이블 및 브랜드별 CSV는 '공백 제외 5자 이하 리뷰'가 이미 물리적으로 제거된 상태.**
> 코드 작성 시 5자 이하 필터링 로직을 중복 작성하지 말 것. 연산 효율성에만 집중.

### 핵심 분석 데이터 (`./final_data/`)

| 파일 | 행 수 | 크기 | 설명 |
|------|-------|------|------|
| `master_preprocessed_260430.csv` | **1,170,945행** | 624MB | 전처리 완료 마스터 테이블 **(주요 작업 대상)** |
| `master_table.csv` | — | 624MB | 원본 마스터 테이블 |
| `안다르_master.csv` | — | 384MB | 안다르 전체 리뷰 |
| `젝시믹스_master.csv` | — | 240MB | 젝시믹스 전체 리뷰 |
| `FILA_master_v2.csv` | — | 9MB | 필라 전체 리뷰 |
| `룰루레몬_master.csv` | — | 6MB | 룰루레몬 전체 리뷰 |

### 마스터 테이블 컬럼 구조 (31개)
```
collect_date, platform, review_id, product_id, product_name, review_date,
year, month, content, rating, helpful_count, has_image,
purchase_option, purchase_option_color, purchase_option_size,
women_size_yn, user_height, user_weight, user_height_group, user_weight_group,
product_url, brand, cat1, cat2, cat3, gender,
original_price, discount_price, color_count, is_new, is_best
```
- 핵심 분석 컬럼: `content`, `brand`, `rating`, `cat1`, `cat2`, `cat3`, `gender`
- `user_height` / `user_weight`: 결측치 다수 (각 ~446k / ~439k 건만 유효)

### 브랜드별 원천 데이터 (`./data/`)

| 파일 | 크기 | 비고 |
|------|------|------|
| `xexymix_raw_review.csv` | 3.3GB | 원본 크롤링 (전처리 전) |
| `xexymix_raw_review_final.csv` | 531MB | 1차 정제 |
| `andar_homepage_review_final_s2024.csv` | 322MB | 안다르 홈페이지 |

### 메모리 처리 전략
- 대용량 CSV 로드 시 `chunksize` 또는 `dtype` 지정 필수
- `master_preprocessed_260430.csv` 작업 기준 RAM ~2–4GB 예상 (실제 메모리 사용: 794.5MB+)
- BERTopic / sentence-transformers: MPS(Metal) 가속 활용

---

## 7. 작업 노트북 현황

### 완료된 작업

| 노트북 | 날짜 | 내용 |
|--------|------|------|
| `andar_homepage_reviews_preprocessed_260428.ipynb` | 04/28 | 안다르 홈페이지 리뷰 전처리 |
| `andar_musinsa_reviews_preprocessed_260428.ipynb` | 04/28 | 안다르 무신사 리뷰 전처리 |
| `xexymix_homepage_review_preprocessed_260429.ipynb` | 04/29 | 젝시믹스 홈페이지 전처리 |
| `xexymix_musinsa_review_preprocessed_260429.ipynb` | 04/29 | 젝시믹스 무신사 전처리 |
| `lululemon_homepage_review_preprocessed_260429.ipynb` | 04/29 | 룰루레몬 홈페이지 전처리 |
| `fila_preprocessed.ipynb` | — | 필라 전처리 |
| `basic_eda_260429.ipynb` | 04/29 | 기초 EDA |
| `master_preprocessed_260430.ipynb` | 04/30 | 마스터 테이블 통합 및 전처리 |
| `unmatched_data_260430.ipynb` | 04/30 | 매칭 실패 데이터 검토 |
| `wordcloud_260501.ipynb` | 05/01 | 워드클라우드 분석 |

### 크롤링 노트북
- `lululemon_크롤링.ipynb`, `musinsa_크롤링.ipynb`

### 토큰 검수 파일
- `step1_token_inspection_v4_9.xlsx`, `step1_token_inspection_v4_10.xlsx`,
  `step1_token_inspection_v4_12.xlsx` (1500건), `step1_token_inspection_v4_13.xlsx` / `_v4_14.xlsx` (10000건)

---

## 8. wordcloud_260501.ipynb 분석 결과 (2026-05-02)

### 노트북 전체 구조
1차~5차 워드클라우드 실험 반복 → 전부 주석 처리됨. **현재 활성 코드는 v4.10 파이프라인 단 하나.**

### 확정된 전처리 아키텍처 (v4.10)

#### `clean_text()` — 텍스트 정제
HTML 태그, URL, 이메일, 이모지 제거 → 반복문자 1개로 통일 (`ㅋㅋㅋ→ㅋ`) → 소문자 통일 → 공백 정규화

#### `advanced_pre_process()` — 형태소 분석 전 처리
- 오타 교정 딕셔너리(`TEXT_CORRECTIONS`) 적용
- 부정 패턴 분리: `하지않다 → 안 하다`, `못하다 → 못 하다`
- 접속어 앞 공백 삽입으로 Kiwi 분석 정확도 향상

#### Kiwi 설정
```python
kiwi = Kiwi(num_workers=os.cpu_count())  # C++ 내부 병렬 처리 (Python multiprocessing 불필요)
kiwi.tokenize(contents)                   # 리스트 일괄 전달 → 배치 처리
```
- Python-level multiprocessing 없이 `num_workers`로 M4 Pro 코어 활용
- 개별 `.apply()` 대신 리스트 일괄 전달이 핵심 속도 최적화 포인트

#### `process_result()` — 토큰 정제 (v4.10 핵심 로직)
추출 대상 품사:
- `NNG` (일반명사), `NNP` (고유명사), `XR` (어근): 2글자 이상 또는 `['핏','딱','꽉','쏙']`
- `VA` / `VV` (형용사·동사): `form + '다'` 형태로 변환

부정 접두어 처리:
```python
# MAG(부사) 중 '안','못','잘','딱' → 다음 토큰에 prefix로 결합
# 예: '안' + '비치다' → '안비치다'
```

정규화 → 불용어 필터 순서로 적용.

#### 사용자 사전 (USER_DICT v4.10) — 주요 카테고리
| 카테고리 | 예시 |
|----------|------|
| 핏 유형 | 오버핏, 슬림핏, 테이퍼드핏, 루즈핏, 머슬핏 등 11종 |
| 아이템명 | 조거팬츠, 브라탑, 바이커쇼츠, 윈드브레이커, 아노락 등 |
| 소재/구조 | 심리스, 쿨링, 텐셀, 메쉬, Y존, 암홀, 시보리 등 |
| 품질 표현 | 신축성, 복원력, 허리말림, 비침, 땀흡수, 통기성 등 |
| 체형 용어 | 하체비만, 힙딥, 군살, 체형보정, 흉곽압박, 승마살 등 |
| 브랜드별 제품명 | 에샤페, 얼라인, 스쿠바, 에어리핏, 블랙라벨, 쉐르파 등 |
| 트렌드/라이프스타일 | 고프코어, 발레코어, 오운완, 바디프로필, 꾸안꾸 등 |

#### NORMALIZATION_DICT — 브랜드명/오타 통일
```python
'젝시' → '젝시믹스', '룰루' → '룰루레몬', '필라' → '휠라',
'이쁘다' → '예쁘다', '런닝복' → '러닝복', '블라' → '블랙라벨' 등
```

#### FINAL_STOPWORDS
`RAW_STOPWORDS - set(USER_DICT)` — 사용자 사전 등록 단어는 불용어에서 자동 제외.

### 현재 실행 결과
- **샘플**: 안다르 150 + 젝시믹스 150 + FILA 100 + 룰루레몬 100 = **500건**
- **출력 파일**: `step1_token_inspection_v4_10.xlsx` (원문 + 토큰 비교용)
- **전체 데이터 적용**: 아직 미실행. `.sample()` 제거 후 `combined_df.copy()`로 전환 필요.

### 다음 작업 방향
- `preprocess.py`로 v4.10 파이프라인 모듈화 (하이브리드 워크플로우 규칙)
- 전체 1,170,945건 배치 처리 실행
- BERTopic용(10자 이상)과 ABSA용 분기 로직 추가

---

## 8-A. 토큰화 파이프라인 진화 (v4.10 → v4.14, 2026-05-03)

### 변경 이력 요약

| 버전 | USER_DICT | RAW_STOPWORDS | NORM | ALL_COVERED | 주요 변경 |
|------|-----------|---------------|------|-------------|-----------|
| v4.10 | ~189 | 165 | ~30 | - | 초기 |
| v4.11 | 367 | 164 | 43 | 578 | 사용자 사전 대폭 확장 |
| v4.12 | 417 | 152 | 46 | 615 | **`없다` 영구 삭제**, 부정 결합 강화, 도메인 어휘 승격 |
| v4.13 | 435 | 152 | 53 | 646 | NORM 어간 통일, NNG 1차 승격, find_variants 정밀화 |
| **v4.14** | **461** | **152** | **54** | **673** | **`add_user_word(score=5.0)`** , 부적합 4건 제거, NNG 2차 승격 |

### v4.12 핵심 변경 (감성 역전 방지)
- **`없다` 영구 삭제**: stopwords에서 제거 → "후회없다/실패없다/필요없다" 부정 의미 보존
- **부정 결합 강제 치환**: TEXT_CORRECTIONS에 `부드럽진 않→안부드럽다`, `늘어남이 없→안늘어나다` 등 9건
- **도메인 어휘 승격**: `사이즈/느낌/착용감/재질/색상/색감/길이/가격/소재/무릎` → 불용어→USER_DICT (ABSA 속성)
- **사전 보호 어휘**: 강제 치환 결과물(`안부드럽다`, `안조이다` 등)을 USER_DICT 최상단 등록

### v4.13 핵심 변경 (정밀화)
- `advanced_pre_process()` **부정 결합 정규식 일반화**: `r'([가-힣]{2,4})(이|가|도|은|는)?\s+없([다어요습네음])'` → TEXT_CORRECTIONS 무한 팽창 차단
- `find_variants` edit_dist 트랙 정밀화: 1~2글자 + `다` 종결 형용사 어간 제외 → `좋다/크다/얇다` noise 차단
- `dict_미적용` 단어 경계 검사: `re.search(r'(?<![가-힣A-Za-z0-9])w(?![...])', orig)` → false positive 제거
- NORM 어간 통일: `적당→적당하다`, `무난→무난하다`, `넉넉→넉넉하다`, `저렴→저렴하다`, `고급→고급지다`
- NORM 오타 통일: `싸이즈→사이즈`, `브렌드→브랜드`, `평상복→일상복`
- ⚠️ NORM 부작용 발견: `'맞다':'잘맞다'` → prefix '잘'+'맞다' 결합 시 `잘잘맞다` 중복 → v4.14에서 제거

### v4.14 핵심 변경 (검수 결과 반영)
- **HIGH_SCORE_WORDS 도입**: `add_user_word(word, 'NNP', score=5.0)` 적용 — 분해 발생 단어
  - 대상: `셋업, 신축성, 한사이즈, 반사이즈, Y존, 8.2부, 가격대비, 한사이즈업, 반사이즈업, 한사이즈다운, 반사이즈다운`
  - **효과**: `신축성` 14건→1건 (대폭 개선), `가격대비` 3건→0건. **단 `셋업/한사이즈/반사이즈/Y존/8.2부`는 효과 미미** → score 추가 강화 또는 다른 API(`add_pre_analyzed_word`) 검토 필요
- **USER_DICT 부적합 제거**: `매일`(MAG), `등`(중의), `봄`(1글자), `사이즈가`(조사형) — 미적용 false positive 287건 ↓
- **NORM 추가**: `젝스믹스→젝시믹스` (오타 16건)
- **NNG 후보 USER_DICT 승격**(P2):
  - 아이템: `팬츠, 티셔츠, 쇼츠, 양말, 팬티, 운동화, 가방, 모자, 스커트`
  - 신체/핏: `가슴, 상의, 속옷, 여유`
  - 소재/구조: `데님, 패드`
  - 품질: `세탁, 품절, 치수, 걱정`
  - 디자인: `투웨이, 플레어, 레이어, 스퀘어`
  - 브랜드: `로고, 실물, 매장`
  - 라이프: `여행, 활동, 활용, 일상`

### v4.14 검수 통계 (10000건 샘플)
| 지표 | v4.13 | **v4.14** | 변화 |
|------|-------|----------|------|
| dict 미적용 | 515건 | **207건** | ↓ 60% |
| 의심 단어 (영문/이모지) | 1504건 | 1504건 | - |
| 사전미해당 토큰 | 710건 | 622건 | ↓ 12% |
| 변형 클러스터 | 40 | 40 | - |
| 처리 시간 | 35.0s | 39.1s | M4 Pro 양호 |

샘플 비율: 안다르 3000 / 젝시믹스 3000 / FILA 2000 / 룰루레몬 2000 (3:3:2:2 유지)

### v4.14 잔존 이슈 (다음 라운드 후보)

**[P0] HIGH_SCORE 가중치 추가 강화 필요**
- `셋업` 38건 / `한사이즈` 64건 / `반사이즈` 20건 / `Y존` 9건 / `8.2부` 6건 — score=5.0 적용에도 분해 발생
- 후속: `score=10.0` 시도 또는 `kiwi.add_pre_analyzed_word()` API 검토

**[P1] find_variants edit_dist 트랙 잔여 noise** (정밀도 ~70%)
- `타이트/화이트/라이트/웨이트` (#7), `베이지/페이스/아이스/베이스` (#16), `브라탑/브라운/브라만` (#24)
- `심리스/플리스` (#31), `스커트/스쿼트` (#33), `스트레치/스트레칭/스트레스` (#39)
- `청바지/반바지/속바지` (별개 아이템 — 분리 유지)
- **결론**: edit_dist 클러스터는 자동 NORMALIZATION 반영 금지, 수동 검토 후 선별 적용

**[P2] 추가 USER_DICT 승격 후보** (10000건 NNG 후보 시트)
- 색상: `와이드(369), 블랙(327), 검정(117), 흰색(100), 화이트(102), 베이지(88), 그레이(73)`
- 평가: `고민(349), 처음(275), 마음(256)`
- 카테고리: `요가(139), 골프(98), 밴드(122)`

---

### v4.15 핵심 변경 (NNG P2 승격 + 마음에들다 수정)

| 버전 | USER_DICT | RAW_STOPWORDS | NORM | 주요 변경 |
|------|-----------|---------------|------|-----------|
| **v4.15** | **483** | **152** | **54** | NNG P2 색상/평가/카테고리 승격, 마음들다→마음에들다 수정 |

- **NNG P2 라운드** (91K 샘플 기준):
  - 색상: `와이드, 블랙, 검정, 흰색, 화이트, 베이지, 그레이, 네이비, 브라운`
  - 평가: `고민, 처음, 마음`
  - 카테고리: `요가, 골프, 밴드`
- **마음들다→마음에들다** 전체 교체: USER_DICT + TEXT_CORRECTIONS 9곳 + 정규식 치환값

### v4.16 핵심 변경 (91K 검수 결과 반영)

| 버전 | USER_DICT | RAW_STOPWORDS | NORM | 주요 변경 |
|------|-----------|---------------|------|-----------|
| **v4.16** | **507** | **152** | **54** | 아이템/색상/소재/평가/라이프 추가 승격 |

- 91K 샘플 검수 결과 반영:
  - 아이템: `청바지, 반바지`
  - 색상: `실버`
  - 소재/디자인: `스트레치, 소프트, 주머니`
  - 평가: `가성비`
  - 라이프: `출근`
- dict 미적용률: **1.87%** (91K 샘플 기준)

### v4.17 핵심 변경 (시리즈명 + 성능 최적화, 2026-05-03)

| 버전 | USER_DICT | RAW_STOPWORDS | NORM | 주요 변경 |
|------|-----------|---------------|------|-----------|
| **v4.17** | **554** | **152** | **62** | 시리즈/라인명 47개 추가, kiwi.space() 배치화, _DICT_PATTERN 컴파일 |

#### 추가 항목 (47개)
- **안다르 시리즈**: 시그니처, 에어데님, 에어엑스퍼트, 에어터치, 에어솔리드, 에어웜, 풀앤비치, 소프텐션
- **젝시믹스 시리즈**: 멜로우데이, 파워라이즈, 데일리페더, 썸머브리즈, 컴포트파인, 에코덱스, 덱스, xfk, xmk
- **FILA 시리즈**: coldwave, 리트모, 푸퍼, 니트트랙, 맥스, 하레핀, 벨로, 슬릭, 판테라, 플로트, 데시무스, 한소희
- **룰루레몬 시리즈**: 하이라이즈, 미드라이즈, 트레인, 패스트, 브레이커, 테크, 원더, 데이드리프트, 트라우저
- **일반아이템**: 셔츠, 후드, 후디, 탱크탑, 카고, 부츠컷, 모크넥, 하프넥, 슬리브리스, 긴팔티, 반팔티, 카라티셔츠, 볼캡, 토트백, 백팩, 드로즈, 파자마, 저지, 재킷, 타이츠, 패딩
- **일반소재**: 플리스, 모달, 니트, 약기모, 스웻, 메모리, 나일론
- **일반어**: 착용(불용어→USER_DICT 이동), 라운드, 우먼즈, 키즈

#### NORMALIZATION_DICT v4.17 추가 (2개)
- `'align': '얼라인'`, `'abc': 'ABC팬츠'`

#### 성능 최적화 (80분 → 2.1분)
```python
# kiwi.space() 배치화 (3곳 — inspect_tokens, extract_oov, find_variants)
processed = kiwi.space([advanced_pre_process(t) for t in cleaned])  # 리스트 일괄

# _DICT_PATTERN 모듈레벨 컴파일 (554개 단어 → 1회 컴파일)
_DICT_SORTED  = sorted(USER_DICT_SET, key=len, reverse=True)
_DICT_PATTERN = re.compile(
    r'(?<![가-힣A-Za-z0-9])(' + '|'.join(re.escape(w) for w in _DICT_SORTED) + r')(?![가-힣A-Za-z0-9])'
)
```

#### v4.17 process_result() 핵심 변경
- **prefix 결합 조건 강화**: compound ∈ USER_DICT_SET 또는 NORMALIZATION_DICT에 있을 때만 결합
  → `안조이다/딱길이` 같은 임의 결합 noise 차단

#### v4.17 검수 결과 (231,523건 — 2026-05-03)
| 지표 | v4.16 | **v4.17** | 변화 |
|------|-------|-----------|------|
| dict 미적용률 | 1.87% | **1.75%** | ↓ 0.12%p |
| dict 미적용 건수 | - | 4,048건 | |
| 의심 단어 건수 | - | 35,704건 (15.42%) | 주로 영문(SL)/이모지(SW) |
| 사전 미해당 토큰 | - | 12,809건 (5.53%) | |
| 변형 클러스터 | - | 40개 | |
| 처리 시간 | 80분+ | **2.1분** | 97% 단축 |
| 브랜드별 미적용률 | - | 젝시믹스 0.90% / 룰루레몬 2.16% / 안다르 2.38% / FILA 2.59% | |

샘플 구성: 안다르 100K / 젝시믹스 100K / FILA 20,063 / 룰루레몬 11,460 = 231,523건

#### v4.17 NNG 후보 Top10 (주요 미등록 어휘)
`추가(4861), 감사(4171), 스타일(4118), 선물(4005), 필요(3285), 사진(3178), 가능(2889), 동일(2778), 기능(2458), 이너(2249)`
→ 대부분 일반어/동작어 → 다음 라운드 USER_DICT 승격 또는 허용 판단 필요

#### v4.17 dict 미적용 처리방안 (결정)
| 단어 | 건수 | 판정 | 처리방안 |
|------|------|------|----------|
| 한사이즈 | 1,341 | 패치 | `re.sub(r'한\s*사이즈', '한사이즈', text)` — preprocess.py 적용 |
| 셋업 | 1,163 | 패치 | `re.sub(r'셋\s*업', '셋업', text)` — preprocess.py 적용 |
| 사이즈 | 641 | 허용 | _DICT_PATTERN false alarm (복합어 내 오탐) |
| 반사이즈 | 262 | 패치 | `re.sub(r'반\s*사이즈', '반사이즈', text)` |
| 하이라이즈 | 237 | 패치 | HIGH_SCORE_WORDS 추가 + 정규식 보강 |
| 나머지 ≤114 | - | 허용 | BERTopic 흡수 또는 false alarm 수준 |

#### v4.17 의심 형태소 Top5 (SL — 영문)
`new(12971), set(10889), xl(3186), cm(2343), kg(2276)` — 현재 허용 (단위/제품 정보)

#### 생성된 파일
- `step1_token_inspection_v4_17_FINAL.xlsx` (6시트: 토큰검수/NNG후보/사전미적용/미인식형태소/사전미해당토큰/변형표현)
- `oov_candidates_v4_17.xlsx` (4시트: NNG후보/사전미적용/미인식형태소/사전미해당토큰)

---

### v4.18 핵심 변경 (강도 부사 보존 + 듀얼 토큰 컬럼, 2026-05-04)

| 버전 | USER_DICT | RAW_STOPWORDS | NORM | INTENSITY | 주요 변경 |
|------|-----------|---------------|------|-----------|-----------|
| **v4.18** | **554** | **146** | **62** | **16** | 강도 부사 보존, INTENSITY_ADVERBS 신규, process_result MAG 분기 추가, preprocess.py 듀얼 토큰 컬럼 |

#### 변경 동기
- 강도 부사(`너무/매우/별로/전혀` 등) v4.17까지 토큰 출력에서 영구 손실 (RAW_STOPWORDS 6개 + 그 외 MAG는 process_result `else` 분기에서 폐기)
- ABSA LLM 입력은 `content_clean`이라 영향 없으나, **검증 통계·NetworkX 의미망·포지셔닝 강도 가중치**에서 분석 차원 손실 발생

#### 코드 변경 (3곳)
1. **RAW_STOPWORDS 6개 제거**: `진짜, 너무, 정도, 많이, 조금, 약간` (152 → 146)
2. **INTENSITY_ADVERBS 신규 셋 (16개)**:
   - 강한 강조: `매우, 엄청, 너무, 진짜, 정말, 무척, 아주, 되게, 훨씬`
   - 약한 강조: `조금, 약간, 꽤, 많이, 정도`
   - 부정적 강조: `별로, 전혀`
   - **USER_DICT에 등록 안 함** — `add_user_word(NNP)`는 부사를 명사화하여 Kiwi 분석 왜곡
3. **process_result() MAG 보존 분기**:
   ```python
   if tag == 'MAG':
       if t.form in {'잘','안','못','딱'}: prefix = t.form; continue
       if t.form in INTENSITY_ADVERBS: extracted.append(t.form); continue
       prefix = ''; continue
   ```

#### preprocess.py 변경 (듀얼 토큰 컬럼)
- **`tokens`** (ABSA·통계·NetworkX용): 강도 부사 **포함**
- **`tokens_topic`** (BERTopic CountVectorizer용): 강도 부사 **제외** (`_strip_intensity()` 적용)
- BERTopic 필터 `has_topic_token` 추가 — 강도 부사만 있던 케이스 추가 제외

#### v4.17 vs v4.18 비교
| 항목 | v4.17 | v4.18 |
|------|-------|-------|
| 출력 컬럼 | 3개 | 4개 (+`tokens_topic`) |
| 강도 부사 정보 | 영구 손실 | tokens에 보존 |
| ABSA LLM 추론 | 동등 (`content_clean` 사용) | 동등 |
| BERTopic 키워드 품질 | OK | 동등 (`tokens_topic` 사용 시) |
| 강도 분포 분석 | 불가 | 가능 |
| NetworkX 강도-속성 결합 | 불가 | 가능 |
| 별점 편향 텍스트 강도 검증 | 불가 | 가능 |
| 처리 시간 | 2.8분 | ~3.0분 |

→ **v4.18 채택**: 디스크/시간 비용 무시 가능, 분석 차원 1단계 확장

---

## 8-B. 컬럼 사용 가이드 (v4.18 parquet 기준)

### parquet 출력 컬럼 (4개 신규)
| 컬럼 | 내용 | 주 사용처 |
|------|------|----------|
| `content_clean` | clean_text 결과 (자연 문장) | BERTopic 임베딩, ABSA LLM 입력 |
| `content_len` | 공백 제외 길이 | 필터링 (≥10/≥6) |
| `tokens` | ABSA·통계·NetworkX용 (강도 부사 포함) | 검증 통계, 의미망 분석, 강도 가중치 |
| `tokens_topic` | BERTopic CountVectorizer용 (강도 부사 제외) | c-TF-IDF 키워드 추출 |

### 단계별 사용 매핑
| 단계 | 컬럼 | 사용 방식 |
|------|------|----------|
| BERTopic 임베딩 | `content_clean` | SentenceTransformer.encode (자연 문장 필요) |
| BERTopic CountVectorizer | `tokens_topic` | `vocabulary=USER_DICT_SET, tokenizer=str.split` |
| ABSA LLM (EXAONE) 입력 | `content_clean` | 프롬프트에 직접 삽입 |
| ABSA Stage1 캐스케이드 | `tokens` | KoBERT 다중라벨 분류 |
| ABSA 검증 통계 | `tokens` + `rating` | 강도 분포 ↔ 별점 정합성 |
| NetworkX 의미망 (Y축) | `tokens` | 토큰 동시출현 → eigenvector centrality |
| 워드클라우드/빈도 | `tokens_topic` | 강도 부사 노이즈 제거 후 시각화 |
| 포지셔닝 X축 | `content_clean` (ABSA 결과) | 속성별 (P-N)/(P+N+ε) |
| 포지셔닝 동적 가중치 | `tokens` | $w_i = \sigma^2_i / \Sigma\sigma^2_j$ |

### 핵심 결정 룰
> 문장이 필요한 곳은 **`content_clean`**, 정량 분석은 **`tokens`**, 토픽 키워드 추출은 **`tokens_topic`**.

---

## 9. 진행 상황 로그

| 날짜 | 내용 |
|------|------|
| 2026-04-28 | 안다르 홈페이지/무신사 리뷰 전처리 완료 |
| 2026-04-29 | 젝시믹스, 룰루레몬 전처리 + 기초 EDA 완료 |
| 2026-04-30 | 마스터 테이블 통합, 매칭 실패 데이터 검토 |
| 2026-05-01 | 워드클라우드 1차~5차 반복 실험, v4.10 파이프라인 확정, 500건 샘플 검수 완료 |
| 2026-05-02 | 전략 컨텍스트 수신, MEMORY.md / CLAUDE.md 전면 개편, 하이브리드 워크플로우 확정, wordcloud_260501.ipynb 전체 분석 완료 |
| 2026-05-03 | v4.11~v4.14 사전 4회 갱신: `없다` stopword 제거, 부정 결합 정규식 일반화, find_variants 정밀화, `add_user_word(score=5.0)` 도입, 10000건 검수 2회 — dict 미적용 60% 감소 (515→207) |
| 2026-05-03 | v4.15~v4.17 사전 3회 갱신 (554개): 시리즈/라인명 47개 추가, kiwi.space() 배치화, _DICT_PATTERN 컴파일 → 2.1분(97% 단축). 231K 전수검수 완료. dict 미적용 1.75% (목표 2% 이하 달성) |
| 2026-05-03 | preprocess.py v1.0 작성 완료: v4.17.1 패치(한사이즈/셋업/반사이즈/하이라이즈), preprocess_texts(), preprocess_master() (CSV→parquet 2종 Two-track) |
| 2026-05-03 | preprocess_master() 전체 실행 완료: 1,170,945건 → BERTopic 1,143,466건 / ABSA 1,168,567건 (2.8분). pyarrow ArrowInvalid 버그(청크 간 product_id 혼합 타입) 수정 완료. |
| 2026-05-04 | v4.18 강도 부사 보존 패치: RAW_STOPWORDS에서 6개(진짜/너무/정도/많이/조금/약간) 제거. INTENSITY_ADVERBS 셋(16개) 신규. process_result()에 MAG 보존 분기 추가. preprocess.py 듀얼 토큰 컬럼(`tokens` ABSA용 / `tokens_topic` BERTopic용) 도입. parquet 재생성 필요. |
| 2026-05-04 | 데이터 아키텍트 관점 종합 설계 완료: BERTopic OOM 방지(UMAP 5차원+서브샘플 HDBSCAN), c-TF-IDF USER_DICT vocabulary 강제, EXAONE 캐스케이드 전략(KoBERT Stage1 → EXAONE Stage2), 50K 층화표본+5K 골든셋, 분산 기반 동적 가중치 포지셔닝 맵 수식 확정 |

---

## 9. Current Sprint — 토큰화 정밀 검수 및 반복 테스트

### 목표
샘플 데이터로 토큰화 정확도를 반복 검수하며 `USER_DICT`와 불용어를 정제 → 최종 `user_dictionary.txt` 완성 → 에러 없는 마스터 테이블 구축.

### 검수 반복 루프
```
샘플 추출 (n 조정)
   ↓
check_tokens.py 실행
   ↓
dict 미적용 / NNG 후보 / 의심 단어 보고 확인
   ↓
USER_DICT · NORMALIZATION_DICT · FINAL_STOPWORDS 수정
   ↓
importlib.reload(check_tokens) → 재실행
```

### 생성된 모듈

| 파일 | 상태 | 역할 |
|------|------|------|
| `check_tokens.py` | ✅ 완료 (v4.18) | 토큰화 검수 전용 모듈 — INTENSITY_ADVERBS 추가 |
| `preprocess.py` | ✅ 완료 (v1.1) | 전처리 마스터 모듈 — 듀얼 토큰 컬럼 (tokens / tokens_topic) |

#### `check_tokens.py` 주요 함수

| 함수 | 반환값 | 용도 |
|------|--------|------|
| `inspect_tokens(texts)` | DataFrame [원문\|형태소_상세\|최종_토큰\|dict_미적용\|의심_단어] | 3단 비교 검수 |
| `extract_oov(texts, top_n)` | dict {nng_candidates, dict_miss_report, suspicious_forms} | 사전 업데이트 후보 추출 |
| `run_inspection(df, sample_sizes)` | (inspect_df, oov_report) + 엑셀 저장 | 원클릭 전체 실행 |

#### OOV/오분석 감지 로직
- **NNG 후보**: USER_DICT 미등록 고빈도 일반명사 → 고유명사(NNP) 등록 후보
- **dict_miss**: 원문에 USER_DICT 단어가 존재하는데 최종 토큰에 없는 케이스 → 사전 등록 오류 탐지
- **suspicious_forms**: Kiwi가 `SW`/`SB`/`SL`/`UNKNOWN` 태그로 처리한 형태소 → 미인식 신조어 후보

### 다음 작업 (Sprint 목표)
- [x] 노트북에서 `run_inspection()` 반복 실행 후 `USER_DICT` 업데이트 (v4.10 → v4.17, 231K건 검수)
- [x] `preprocess.py` v1.0 작성 — check_tokens v4.17 임포트 + v4.17.1 패치 + preprocess_master()
- [x] 전체 1,170,945건 배치 처리 실행 → `preprocessed_bertopic.parquet` 1,143,466건 / `preprocessed_absa.parquet` 1,168,567건 (2.8분)
- [x] v4.18 강도 부사 보존 패치 + 듀얼 토큰 컬럼 도입 (preprocess.py + check_tokens.py 수정 완료)
- [ ] **v4.18 parquet 재생성** — `preprocess_master()` 재실행하여 `tokens_topic` 컬럼 추가
- [ ] NNG 후보 P3 라운드 — 추가(4861), 스타일(4118), 이너(2249), 세트(2067) 등 승격 검토
- [ ] 검수 완료 후 BERTopic 토픽 모델링 (`topic_model.py`) 진입

---

## 10. 다음 단계 (To-Do) — 데이터 아키텍트 권고 우선순위

### P0 (즉시)
- [ ] **v4.18 parquet 재생성** — duals 토큰 컬럼 적용 (~3분)
- [ ] **임베딩 캐싱 전략 설계** — UMAP 5차원, low_memory=True, parquet에 embedding 저장 → 튜닝 시 재계산 0
- [ ] **5K 골든셋 인간 어노테이션** — Cohen's κ ≥ 0.7 검증 기반 (속성×감성)

### P1 (BERTopic + ABSA 본 작업)
- [ ] **`topic_model.py` 작성** — `content_clean` 임베딩 + `tokens_topic` CountVectorizer + USER_DICT vocabulary 강제
  - UMAP(n_components=5, min_dist=0.0), HDBSCAN(min_cluster_size=500, leaf), c-TF-IDF(reduce_frequent_words=True, bm25_weighting=True)
  - 서브샘플 HDBSCAN (200K stratified fit + approximate_predict)
- [ ] **`absa_sampling.py` 작성** — 50K 층화표본 (brand×rating×cat1, 1-3점 oversample 3.0×)
- [ ] **카테고리 가이드 토픽 모델링** — `seed_topic_list`에 USER_DICT 카테고리 시드 주입

### P2 (캐스케이드 + 정밀화)
- [ ] **`absa.py` Stage1 (KoBERT 다중라벨 분류기)** — 116만 건 1차 속성 존재 여부 라벨링
- [ ] **`absa.py` Stage2 (EXAONE Few-shot)** — 모호 케이스 + 50K 표본 정밀 추론, llama.cpp parallel decoding + KV 캐시 재사용
- [ ] **NNG 후보 P3 라운드** — 추가, 스타일, 이너 등 USER_DICT 승격 검토

### P3 (포지셔닝 맵)
- [ ] **`sna.py`** — `tokens` 기반 NetworkX 동시출현 그래프 → eigenvector centrality
- [ ] **`positioning.py`** — 분산 기반 동적 가중치 $w_i = \sigma^2_i / \Sigma\sigma^2_j$, sklearn StandardScaler, bootstrap 신뢰구간
- [ ] **검증 지표** — Macro-F1, 속성별 F1 (목표 ≥ 0.85), Cohen's κ ≥ 0.70
- [ ] **White Space 도출** — FILA 좌표 ↔ 경쟁사 점유도 그리드 분석

---

## 10. 결정된 아키텍처 요약

| 결정 사항 | 내용 |
|-----------|------|
| 분석 기준 파일 | `master_preprocessed_260430.csv` |
| 5자 이하 필터 | 모든 분석에서 전면 제외 |
| BERTopic 입력 기준 | 공백 제외 10자 이상 |
| ABSA 입력 기준 | 공백 제외 6자 이상 (10자 미만 포함) |
| LLM | Ollama 로컬 EXAONE 3.5 7.8B (외부 API 금지) |
| 임베딩 모델 | `jhgan/ko-sroberta-multitask` |
| 포지셔닝 축 | X: 기능성(Functionality) / Y: 브랜드 헤리티지(Heritage) |
| 워크플로우 | 하이브리드 — `.py` 모듈(클로드) + `.ipynb` 실행(사용자) |

---

## 11. ABSA 골든셋 라벨링 (2026-05-04 ~ 05-06)

### 11-A. 6-Aspect 속성 구조 (확정)

| # | 속성 | 정의 | 포지셔닝 축 |
|---|------|------|------------|
| 1 | 핏/사이즈 | 사이즈 정확도, 라이즈, 압박감, Y존, 라인감 | X 보조 |
| 2 | 소재/내구성 | 원단 촉감·두께, 보풀·변색·늘어짐 | X 보조 |
| 3 | 기능성 | 신축성, 흡습속건, 통기성, 활동성, 보온/냉감 | **X 핵심** |
| 4 | 디자인 | 색상, 패턴, 실루엣, 데일리 활용도 | Y 보조 |
| 5 | 브랜드/헤리티지 | 재구매·추천·충성도·정체성 표현 (v2: 협소화) | **Y 핵심** |
| 6 | 가격/가치 | 가격, 가성비, 프로모션 | 보조 |

### 11-B. `absa_sampling.py` (v1.0)

**역할**: `preprocessed_absa.parquet` → 1,000건 골든셋 + 어노테이션 xlsx 생성

**샘플링 전략**:
- 4 브랜드 × 250건 = 1,000건 균등
- 1-3점 50% (125건) + 4-5점 50% (125건) — 별점 편향(4-5점 92%) 보정
- `content_len ≥ 20` 정보량 필터, rating=0(별점 결측) 제외
- xlsx 2시트: [가이드라인 v1] + [라벨링] (드롭다운 P/N/U/X 검증)
- 라벨링 컬럼: `content_clean`(70칸 주 텍스트) + `content`(50칸 참고)

**주요 함수**: `build_golden_set()`, `sample_golden_set()`, `build_annotation_template()`

### 11-C. Cohen's κ 측정 (1차, v1 4-class P/N/U/X)

**라벨링 분담**:
- `absa_golden_set_1000_done.xlsx`: sample_idx 1-500 → 라벨러 1, 501-1000 → 라벨러 2 (분업, 겹침 없음)

**κ 측정용 교차 재라벨링** (각 50건, 총 100건):
- 라벨러 1 → sample_idx 501~ 50건 신규 라벨링 (라벨러 2 원본 구간)
- 라벨러 2 → sample_idx ~500 50건 신규 라벨링 (라벨러 1 원본 구간)
- 비교: 원본(done) ↔ 신규(L1/L2)

**1차 κ 결과 (v1)**:
| 속성 | κ | 판정 |
|---|---|---|
| 핏/사이즈 | 0.6679 | ⚠️ 합격권 |
| 소재/내구성 | 0.5913 | ❌ |
| 기능성 | 0.5586 | ❌ |
| 디자인 | 0.6248 | ⚠️ 합격권 |
| 브랜드/헤리티지 | 0.1612 | ❌ 심각 |
| 가격/가치 | 0.6867 | ⚠️ 합격권 |
| **Macro-avg** | **0.5484** | 기준 0.75 미달 |

### 11-D. 4대 구조적 결함 진단

| 결함 | 영향 | 근본 원인 |
|---|---|---|
| A. 브랜드 정의 범위 과도 | 브랜드/헤리티지 (κ=0.16) | 약한 시그널("추가구매", "또") 포함 여부 라벨러별 상이 |
| B. "편하다" 귀속 규칙 부재 | 핏·기능성·소재 | 단어 하나가 3개 속성에 모두 매핑 가능 |
| C. 부정 톤 우세 처리 부재 | 전 속성 | "구매했는데 별로" 처리 룰 없음 |
| D. U 클래스 활용 저조 | 전 속성 | 1~22건만 사용, P↔U·N↔U 혼동이 κ 끌어내림 |

**P↔X 불일치 패턴** (가장 지배적): 67건 — "이 표현이 해당 속성을 언급하는 것인가?" 기준이 라벨러별 상이

### 11-E. 가이드라인 v2.0 (2026-05-06, 235줄)

`/송원우/absa_guideline_v2.md` — 누구나 읽고 동일 판단 가능한 표준 문서

**핵심 변경**:
1. **U 폐지** → 3-class (P/N/X)
2. **브랜드/헤리티지 협소화** → 명시 트리거(재구매·추천·충성도·정체성)만 P
3. **"편하다" 귀속 Hard Rule** → 맥락 없으면 X
4. **부정 톤 우세 룰** → rating ≤ 2 + 강한 부정어 시 약한 P → X 강등
5. **트리거 사전** → 6 속성 × P/N 키워드 명시 (각 10~20개)

**문서 구성** (9장):
1·2장 정의·의사결정 트리 / 3장 속성별 상세 룰 / 4장 전역 룰 / 5장 모호 표현 매핑 사전(25개) / 6장 셀프 체크리스트 / 7장 합의 프로세스 / 8장 FAQ / 9장 변경 이력

### 11-F. `absa_relabel.py` (v1→v2 변환 모듈)

**핵심 아이디어**: 1,000건 재라벨링 ❌ → 트리거 사전 자동 매칭으로 충돌 케이스만 라벨러 검토

**자동 변환**:
- U → X 일괄 (177건)
- 부정 톤 우세 + 약한 브랜드 P → X 강등 후보 플래그

**재검토 플래그 (5종)**:
| 플래그 | 의미 | 우선순위 |
|---|---|---|
| `X_HAS_TRIGGER` | v1=X, 트리거 매칭 (누락 의심) | P1 |
| `P_vs_TRIGGER_N` | v1=P, 트리거=N (충돌) | P1 |
| `N_vs_TRIGGER_P` | v1=N, 트리거=P (충돌) | P1 |
| `PYEONHADA_AMBIGUOUS` | "편하다" 단독 P | P1 |
| `NEG_TONE_WEAK_P` | 부정 톤 + 약한 브랜드 P | P1 |
| `P_NO_TRIGGER` / `N_NO_TRIGGER` | 트리거 매칭 없음 (사전 한계 가능) | P2 (스폿) |

**라벨러별 검토 분담** (분업 구조 유지: L1=1-500, L2=501-1000 본인 구간):
- 라벨러1: P1 106건 + P2 스폿 50건 = **156건** (~1.5시간)
- 라벨러2: P1 156건 + P2 스폿 50건 = **206건** (~2시간)

**산출 파일**:
- `absa_golden_set_1000_v2.xlsx` (U→X 자동변환)
- `absa_relabel_P1_L1.xlsx` / `absa_relabel_P1_L2.xlsx` (즉시 검토)
- `absa_relabel_P2_spotcheck_L1.xlsx` / `absa_relabel_P2_spotcheck_L2.xlsx` (스폿)

### 11-G. 도메인 인정 가능 κ 기준

**Landis & Koch (1977) 표준**:
- 0.81~1.00 Almost Perfect / **0.61~0.80 Substantial (산업 표준)** / 0.41~0.60 Moderate / <0.40 Fair

**도메인 비교**:
- KOLD (한국어 혐오, 2022): κ=0.86 (binary)
- NIKL ABSA (국립국어원, 2021): κ=0.72 (4-class)
- SemEval-2014/2016 ABSA: κ=0.67~0.81

**예상 도달 κ (단계별)**:
| 단계 | 예상 κ | 판정 |
|---|---|---|
| 현재 v1 | 0.55 | Moderate (사용 불가) |
| v2 자동변환 직후 | 0.60~0.64 | 경계 |
| **v2 + P1 검토 후** | **0.68~0.74** | **Substantial (상용 학습 데이터 사용 가능)** |
| v2 + 100건 교차 재라벨링 | 0.72~0.78 | NIKL/SemEval 수준 |
| + 시니어 중재 | 0.78~0.85 | Almost Perfect (벤치마크) |

**솔직한 평가**:
- κ ≥ 0.65 도달 가능성: **90%+** (P1 검토만으로도 가능)
- κ ≥ 0.75 도달 가능성: **70~80%** (P1 검토 + 100건 재라벨링 + 시니어 중재 조건)
- v2 자동변환만으로는 0.60~0.64 머무를 가능성 → P1 검토 필수

### 11-H. 다음 단계 액션 플랜

**Day 1 (완료)**:
- [x] 가이드라인 v2.0 문서화
- [x] `absa_relabel.py` 작성 — 자동 변환 + 재검토 플래그
- [x] U→X 자동 변환 완료 (`absa_golden_set_1000_v2.xlsx` 산출)
- [x] P1/P2 검토 시트 생성 (라벨러1 156건, 라벨러2 206건)

**Day 2 (진행 예정)**:
- [ ] 라벨러 2명 가이드라인 v2 정독 + 캘리브레이션 미팅 (30분)
- [ ] P1 즉시 검토 작업 (라벨러별 1.5~2시간)
- [ ] P2 스폿 체크 50건 → 트리거 사전 보강 필요 여부 판단

**Day 3 (예정)**:
- [ ] P1 검토 결과 통합 → v2.1 라벨 갱신 코드 (작성 필요)
- [ ] 100건 교차 재검증 v2.1 기반 재라벨링
- [ ] κ 재측정 → 목표 ≥ 0.65 도달 확인

**Day 4 이후**:
- [ ] 시니어 중재 (필요 시)
- [ ] 최종 골든셋 v2.2 확정
- [ ] ABSA 본 작업 진입 (`absa.py` 캐스케이드)

### 11-I. 주요 산출물 위치 (송원우/)

| 파일 | 용도 |
|---|---|
| `absa_guideline_v2.md` | 라벨러 가이드라인 v2.0 (235줄, 9장) |
| `absa_sampling.py` | 골든셋 추출 + xlsx 자동 생성 모듈 |
| `absa_relabel.py` | v1→v2 변환 + 재검토 플래그 모듈 |
| `absa_labeling_260504.ipynb` | Cohen's κ 계산 노트북 |
| `final_data/absa_golden_set_1000_done.xlsx` | v1 라벨링 완료 (1-500 L1, 501-1000 L2) |
| `final_data/absa_golden_set_1000_v2.xlsx` | v2 자동 변환 (U→X) |
| `final_data/kappa_overlap_100.xlsx` | 교차 재라벨링 풀 (100건) |
| `final_data/kappa_overlap_100_L1.xlsx` | 라벨러1 신규 라벨 (51-100 구간 50건) |
| `final_data/kappa_overlap_100_L2.xlsx` | 라벨러2 신규 라벨 (1-50 구간 48건) |
| `final_data/absa_relabel_P1_L1.xlsx` | 라벨러1 즉시 검토 (106건) |
| `final_data/absa_relabel_P1_L2.xlsx` | 라벨러2 즉시 검토 (156건) |
| `final_data/absa_relabel_P2_spotcheck_L1.xlsx` | 라벨러1 스폿체크 (50건) |
| `final_data/absa_relabel_P2_spotcheck_L2.xlsx` | 라벨러2 스폿체크 (50건) |

---

## 12. 진행 로그 (2026-05-04 ~ 05-06)

| 날짜 | 내용 |
|------|------|
| 2026-05-04 | `absa_sampling.py` v1.0 작성, 1,000건 골든셋 추출 (4브랜드 균등 250 + 1-3점 oversample 50%). xlsx 2시트(가이드라인+라벨링) + P/N/U/X 드롭다운 검증. content_clean을 라벨링 주 텍스트로 배치 |
| 2026-05-05 | 1,000건 라벨링 완료 (분업: L1=1-500, L2=501-1000). 100건 교차 재라벨링 진행 (각 50건씩). κ 측정 코드 디버깅 (overlap_pool 변수 참조 오류 → done.xlsx에서 원본 라벨 가져오는 방식으로 수정) |
| 2026-05-06 | 1차 κ 측정: Macro 0.55 (브랜드/헤리티지 0.16 심각, 가격/가치 0.69 합격). 4대 구조적 결함 진단 완료. 가이드라인 v2.0(235줄) 작성 — U 폐지, 브랜드 협소화, 편하다 룰, 부정 톤 룰, 트리거 사전. `absa_relabel.py` 작성 — 자동 변환 + P1/P2 우선순위 검토 시트 생성 (라벨러1 156건, 라벨러2 206건). 도메인 κ 기준 검토: P1 검토 후 κ 0.68~0.74 (Substantial) 도달 예상 |
| 2026-05-06 | P1/P2 검토 완료 → v2.1 골든셋 → 2차 κ 0.4633 (Moderate, 미달). Mismatch 분석으로 L1 전이오류·L2 누락오류 진단. 가이드라인 v2.1 → v2.2 패치 (착용감 귀속 규칙, 브랜드 협소화 박스, 캘리브레이션 합의 3건 반영). 캘리브레이션 30건 진행 → κ_calib (기능성 1.000, 브랜드 0.900, Macro 0.950 Almost Perfect) |
| 2026-05-06 | v2.2 base + 2속성 재라벨링 (L1 idx 1~500, L2 idx 501~1000). v2.3 골든셋 병합 완료 → `absa_golden_set_1000_v23.xlsx`. 전체 κ: 기능성 0.6573 / 브랜드 0.4587 / Macro 0.5580. 단, 이는 "새라벨 vs 구 over-labeled" 비교의 측정 artifact. 실질적 IAA = 캘리브레이션 κ 0.95. v2.3 브랜드 P 423→202(-221), X 420→690(+270) — 가이드라인 협소화 적용 결과 |
| 2026-05-06 | 시나리오 A 채택 (즉시 ABSA 진행 + 사후 검증). L2 구간 100건 stratified sample 추출 (P:25/N:15/X:60) → `absa_overlap_validation_L1.xlsx` (3시트: 안내/검증라벨링/가이드라인요약, P/N/X 드롭다운). 정답지 비공개 저장: `_overlap_answer_key_v23.xlsx`. 라벨러1 작업 완료 후 cross-overlap κ 측정 → Gate 1 (≥0.65 시 absa.py 진입 확정) |
| 2026-05-07 | 역할 재정의: 라벨러1이 Phase A~E end-to-end 단독 진행 (overlap 라벨링→κ→absa.py 구현→F1 검증→1.16M 추론). 송원우는 L2 합의 미팅(필요 시) + BERTopic/SNA/포지셔닝 후속 작업. 산출물: `L1_작업매뉴얼.md`(end-to-end 절차+의사결정 분기), `absa.py`(골격: Stage1 트리거+Stage2 EXAONE 캐스케이드, [L1 채우기] 함수 표시), `L1_실행노트북.py`(Phase B/C/D/E 셀단위). Q1 A 결정: 송원우=골격, L1=구현. 정답지 파일 `_DO_NOT_OPEN_BEFORE_LABELING` 접미어로 rename. Stage1 트리거 사전은 `absa_relabel.py` v2.2 기준 재활용 권고 |
| 2026-05-07 | Streamlit 대시보드 3단계 개편 완료. Step1: 사이드바 필터 전면 교체(multiselect/slider/selectbox/checkbox×3), session.py 키 재설계, apply_filters 새 키 처리, app.py 거시적 요약 전용으로 단순화. Step2: 브랜드 개별 페이지 P1~P4 신설(휠라/안다르/젝시믹스/룰루레몬), 공통 템플릿 brand_page.py, 매출 더미 placeholder/월별 추이/카테고리 분포/가격 히스토그램/워드클라우드(wordcloud 폴백 포함). Step3: 분석 페이지 P5~P7으로 번호 변경(BERTopic/ABSA/전략포지셔닝), 구 P1~P4 삭제, 필터 변수명 업데이트. requirements.txt에 wordcloud/matplotlib 추가. 스키마 경고(reviews schema) 수정 — 부분 컬럼 로드 시 check_schema 생략, REVIEWS_SCHEMA 실 parquet 타입에 맞게 정렬. |
| 2026-05-08 | 대시보드 3차 개편 완료. (1) P2 전면 개편: 가격 탄력성 X축을 할인율(%)로 교체(룰루레몬 0~15% vs domestic 0~55% 브랜드별 프리미엄 방어력 시각화), 고관여 인게이지먼트 섹션 신규(포토 리뷰 비율/평균 도움이 돼요/신상품 포토 비율 브랜드 비교 Bar 3열), SKU 복잡도 Box Plot으로 교체(색상 수 구간별 리뷰 수 분포), 컬러 빈도 분석 신규(purchase_option_color Top10 horizontal bar), 리뷰 볼륨×평점 사분면 Scatter 신규(브랜드×카테고리, 중앙값 기준선). P2 총 6섹션. (2) P3 파일명 3_고객의_목소리.py → 3_BERTopic.py, P4 파일명 4_브랜드_속성_평가.py → 4_ABSA.py (사이드바 표시 이름 변경). (3) 전체 이모티콘 제거: app.py/P1~P5/brand_page.py/filters.py 전 파일의 page_icon, title, subheader, caption, markdown, button, annotation 텍스트에서 이모티콘 완전 제거. |
| 2026-05-08 | P2 실데이터 연결 완료. preprocessed_absa.parquet(1.17M행, 35컬럼)으로 더미 전면 대체. 6섹션 모두 get_reviews() 컬럼 프루닝 + @st.cache_data 집계 함수로 재작성: (1)체형 Heatmap — user_height/weight_group groupby pivot_table, 첫 숫자 기준 정렬; (2)가격탄력 — 할인율=(original-discount)/original×100, 5% 구간 집계 scatter; (3)고관여 — is_new 혼합타입 정규화(True/1.0), has_image mean/helpful_count mean/is_new×has_image 브랜드별 집계; (4)SKU Box Plot — product_id 단위 n_reviews+color_count 집계, 5구간 버킷; (5)컬러 빈도 — purchase_option_color unknown 제외+쉼표 분리 첫색상 top10; (6)사분면 — brand×cat1 groupby n_reviews+avg_rating. warn_using_dummy 제거, numpy/더미생성기 전부 삭제. 실데이터 주요 인사이트: 젝시믹스 포토 리뷰 비율 99.4%(플랫폼 특성), 룰루레몬 helpful_count 0.76(최고), 룰루레몬 할인율 0% 집중(노세일 정책 확인). |
| 2026-05-08 | 대시보드 UX 2차 개편 완료 (Phase 1~3). Phase1: session_state.brands를 단일 문자열로 전환, app.py 하단에 브랜드 바로가기 버튼(4열), brand_page.py 최상단에 st.pills 브랜드 전환 UI 추가. session.py/filters.py 타입 호환 의존성 수정(get_filters()에서 string→list 정규화). Phase2: 개별 브랜드 4개 페이지(1~4) → 단일 통합 페이지 1_브랜드_별_현황.py로 통합, 심화분석 페이지 5→3(BERTopic), 6→4(ABSA), 7→5(포지셔닝)으로 번호 변경 및 제목 수정. Phase3: 신규 페이지 2_상품_및_고객_전략.py 생성 — 체형별 만족도 Heatmap(키/몸무게 그룹 × 평균 평점), 가격 탄력성 Scatter(discount_price vs 평점/리뷰수, lowess trendline), SKU 관여도 이중축 Bar(색상수 구간별 상품 수 + 포토 리뷰 비율). 전체 페이지 구성: 홈(app.py) + P1~P5 = 총 6개 화면. |
| 2026-05-08 | 대시보드 고도화 5개 항목 완료. (1) 홈+P1 통합: app.py에서 "데이터 산출물 상태" 섹션 삭제, 하단에 render_brand_page() 직접 호출 — KPI요약+브랜드현황테이블+브랜드별상세분석이 단일 페이지로 통합. (2) 라이트 모드 전환: .streamlit/config.toml base="light" 변경, 브랜드색상 라이트모드 최적화(FILA #003087/안다르 #D4000F/젝시믹스 #E0561A/룰루레몬 #1565C0), style.css 라이트모드 스타일로 전면 재작성. (3) P2 컬러 빈도 hex 매핑: _KR_COLOR_HEX dict(40+ 매핑) 정의, go.Bar marker_color에 한국어→hex 변환 적용 — 블랙막대=검정, 네이비막대=남색 등 실제 색상 렌더링. (4) P4 레이더 차트: aspect_polarity_grouped_bar 삭제, Scatterpolar 4브랜드 오버레이(fill=toself, fillcolor+2E opacity, 6속성 closed polygon) 교체. (5) P2 고관여 아웃라이어 추적: 3개 인게이지먼트 바 차트 하단에 expander 추가 — helpful_count/has_image 기준 선택+임계값 슬라이더+브랜드선택 → content_clean 포함 top50 리뷰 DataFrame 노출. (6) P5 PMI 신발↔의류 연결 분석 신규: networkx + math, @st.cache_data _compute_pmi_centrality() 함수(window=3 동시출현+PMI 계산+nx.Graph+degree/betweenness centrality), 연결중심성 Bar/매개중심성 Bar/degree×betweenness 산점도 3차트, 신발/의류/공통 카테고리 색상 구분, PMI 파라미터 조정 슬라이더 제공. |
| 2026-05-08 | data_loader.py get_topic_meta() KeyError 방어 로직 추가. 원인: get_topics() 결과에 topic_id 컬럼 없을 때 groupby("topic_id") 직접 호출로 KeyError 발생 → P3/P5 렌더링 전체 중단. 수정: (1) topics.empty 체크 유지. (2) topic_id 없고 Topic(대문자) 있으면 rename 처리. (3) 그래도 topic_id 없으면 warn_using_dummy() + 5개 더미 토픽 DataFrame 반환. (4) groupby 전 agg_kwargs 동적 구성 — topic_name/review_id/topic_keywords 컬럼 존재 여부에 따라 선택적 집계, 누락 컬럼은 폴백값으로 채움. |
| 2026-05-08 | data_loader.py 스키마 검증 강화 — Graceful Degradation 적용. 문제: config.py에서 positioning/sna 경로가 athleisure_bertopic.parquet(토픽 결과)을 가리켜 파일은 존재하지만 필수 컬럼(x_function/y_heritage 등) 누락으로 대시보드 중단 발생. 수정사항: (1) `from utils.exceptions import warn_using_dummy` 임포트 추가. (2) get_positioning(): 파일 존재 시 check_schema 실행 → result.missing 비어있지 않으면 warn_using_dummy() 호출 + compute_positioning_from_absa() 반환으로 폴백. (3) _load_or_dummy(): 동일 패턴 — result.missing 있으면 warn_using_dummy() + dummy_fn() 반환. 파일 없음과 스키마 불일치를 동일하게 처리하여 대시보드 UI 보장. |
| 2026-05-09 | 인간튜터1·2 피드백 12개 항목 일괄 반영. **P0(즉시·고임팩트)**: (1) 포지셔닝 좌표 — minmax 제거 후 절대 스케일 `0.5×(1+(P-N)/(P+N))` 채택, NaN 보존(0 전치 금지), positioning_map.py에서 NaN 브랜드 스킵+경고, 5번 페이지에 좌표 산출법 expander+테이블 NaN→"산출 불가" 표시. (2) "가격 탄력성" 표현 정정 → "할인율별 평점 분포" (탄력성은 수요량 기반 정의). (3) topic_keyword_treemap에 비율 라벨(`%{percentRoot}`) 추가. (4) 컬러 빈도 Bar — 브랜드 단색 통일 + y축 색상 동그라미(HTML span). **P1**: (5) Main.py에 핵심 인사이트 카드 3개(시장위치/속성강약점/전략가설) 추가, ABSA 동적 산출. (6) 2번 페이지 끝에 Action Recommendation 카드 3개(무채색 SKU/신발→의류/기능성 메시지). (7) 4번 ABSA 상단에 P/N/X 분모 정의 expander + 하단에 대표 리뷰 expander(브랜드×속성×감성 신뢰도 상위 5건). (8) 3번 BERTopic 드릴다운 컬럼 확장(작성일/상품명/카테고리/평점/토픽명/토픽확률/원문). **P2**: (9) 브랜드×토픽 히트맵 → 100% 누적막대(행/열 정규화 토글). (10) 월별 추이 — 최댓값 annotation + 수집 기준 caption. (11) helpful_count — 노출 기간 보정 토글(`helpful_count/days_exposed` 일평균). **데이터 연결**: (12) `PATHS["tokens"]` 추가 (preprocessed_bertopic.parquet), `get_tokens(brand, column)` 신규 로더, brand_page.py 워드클라우드 연결 + 일반 평가 어휘 불용어 사전 추가(좋다/있다/없다 등 50+개). 연도별 매출 차트는 사용자 결정으로 유지(외부 데이터 추가 예정). |
| 2026-05-09 | 대시보드 B·A·E 3항목 반영 완료. **B(페이지 연결 강화)**: Main/P2/P3/P4/P5 5개 파일 상단에 흐름 내비게이션 밴드(`📊 홈 › 상품/고객 전략 › BERTopic › ABSA › 포지셔닝`) + 이전 단계 맥락 캡션 추가. **A(ABSA 자동 통합 준비)**: config.py에 `absa_labeler1` / `absa_complement` 경로 2개 추가. data_loader.py `get_absa()`를 4단계 merge stub으로 재작성 — 두 파일 모두 존재 시 concat+drop_duplicates("review_id") 자동 병합, 하나만 있으면 단독, 둘 다 없으면 기존 단일파일 폴백 → 더미. 현재는 두 파일 없어 동작 변화 없음. **E(신규 ABSA 차트)**: `4_ABSA.py`에 `plotly.express` import 추가. 레이더 차트 앞에 브랜드×속성 P_ratio 히트맵(`px.imshow`, RdYlGn, 4×6) 삽입 — 실데이터 없으면 `st.info` placeholder. 대표 리뷰 expander 앞에 FILA 부정 리뷰 핵심 키워드 카드 섹션 삽입 — `absa_fila_complement_predictions.parquet` 존재 시 자동 활성화, 없으면 `st.info` placeholder. |
| 2026-05-10 | **브랜드별 매출 데이터 Main.py 반영**: 휠라/안다르/젝시믹스/룰루레몬 2023~2025 매출(억 원) + 전년비(24→25) + 2025 시장점유율. `_SALES` dict를 Main.py 상단에 하드코딩. 브랜드별 KPI 카드(4열, 브랜드색 헤더 + 매출 + YoY + 점유율) + 연도별 상세 테이블을 "브랜드별 매출 현황" 섹션으로 신규 추가 (전체 KPI와 핵심 인사이트 카드 사이). 룰루레몬 2025=2,093억은 추산치(*) 표기 + 각주. YoY: 휠라+5.3%/안다르+26.7%/젝시믹스-0.2%/룰루레몬+33.6%(추산). |
| 2026-05-10 | 대시보드 다중 수정 완료. **(1) ABSA 한글→영문 컬럼 rename**: `absa_fila_complement_predictions.parquet` 속성 컬럼이 한글(핏/사이즈 등)로 저장되어 있어 `data_loader.py`에 `_ABSA_COL_RENAME` dict + `_load_absa_parquet()` 헬퍼 추가 — 로드 시 자동 rename. `get_absa()` 4-priority 분기 모두 `_load_absa_parquet()` 경유로 교체. 파일을 `final_data/`에 복사하면 자동 실데이터 전환. **(2) BERTopic 컬럼 대응**: `athleisure_bertopic.parquet`이 `topic`(소문자)/`keyword_1~5` 컬럼 사용 → `get_topic_meta()`에서 `topic`(소문자) rename 처리 추가, `keyword_1~5` → 리스트 병합 후 `topic_keywords` 생성. topic_name 있으면 `/` 분리 키워드 폴백도 추가. **(3) UI 개선 — 인게이지먼트 레이아웃**: `st.toggle`을 `st.columns(3)` 바깥으로 이동 → 포토리뷰/도움이돼요/신상품포토 3차트 동일 수평 위치 유지. **(4) 컬러 매칭 개선**: `_resolve_color_hex()` 함수 추가 — 정확 매칭 실패 시 `_KR_COLOR_HEX` 키 중 가장 긴 것부터 포함 여부 체크(베이스컬러 추출). 안다르 `멜란지그레이→그레이`, `스톤블루→블루`, 룰루레몬 `라이트_아이보리→아이보리` 등 커버. **(5) 부정 레이더 축 범위 자동 조정**: `update_radar_layout(fig, title, r_max=1.0)` 파라미터화. 부정 차트는 실제 N_ratio 최댓값×1.4 기준 동적 범위(최소 15%, 최대 50%)로 설정 → 작게 보이던 문제 해결. **(6) 용어 단순화**: `연결 중심성→직접 연결도` / `매개 중심성→가교 지수` 전체 교체 (차트 제목/레이블/컬럼명/subheader/caption). **(7) 이모티콘 전체 삭제**: Main.py 인사이트 카드, nav 밴드 📊, ABSA 리뷰 ⭐, 포지셔닝 ⚠, 상품전략 액션카드 🎨👟🧪 전부 제거. **(8) `absa_fila_complement_predictions.parquet` → `final_data/` 복사 완료**: 4.0MB, 17,014행. FILA 실데이터 히트맵·부정키워드카드·대표리뷰 자동 활성화. | 2026-05-09 | ABSA 옵션 4-A (FILA 차집합) 동시 진행 시작. **배경**: 라벨러1(안진식)이 stratified 12,056건(`absa_phase_e_sample.parquet`) 처리 중. 송원우는 라벨러1 sample 제외한 FILA 17,014건(차집합)을 동시 추론 → 라벨러1 결과와 합쳐 FILA 전수 분석 완성. **노트북 신규**: `송원우/absa_exaone/run_fila_complement.ipynb` (16셀: 환경셋업/차집합추출/벤치마크/본추론/검증). **모델 변경**: `call_exaone_batch` 기본 모델을 `'exaone3.5:7.8b-instruct-q4_K_M'` → `'exaone3.5:7.8b'`로 수정 (사용자 환경 Ollama 태그명 일치). **벤치마크 결과 (M4 Pro Metal)**: 100건 105.1초 = **1.05초/건** — RTX 3050 4GB(8.62초/건) 대비 **8.2배 가속**. 17K건 추정 5시간. **분포 진단**: 벤치마크 100건이 5점 93건 + 4점 7건(부정 0건)이라 N 라벨 거의 0이지만, FILA 모집단 평점이 5점 90.2% / 4점 8.0% / 1~3점 1.8%이므로 비정상 아님. v9 모델은 X 편향 없이 정상 작동 확인. **본 추론 옵션 X 선택**: 모집단 분포 그대로 17,014건 추론 진행 (체크포인트 50건마다 `absa_fila_complement_checkpoint.csv`). 부정 분석은 라벨러1 sample에 위임, 송원우 결과는 FILA 긍정 강점 패턴 분석 가치. **동시작업 가이드**: M4 Pro에서 추론 중 일반 작업(브라우저/문서/코딩) 가능. GPU 무거운 앱(영상편집/3D)·Ollama 재시작·sleep만 회피. 산출물 경로: `송원우/absa_exaone/absa_fila_complement_predictions.parquet` (5h 후 완료 예정). 추론 완료 대기 중 대시보드 작업 집중 예정. |
| 2026-05-10 | 대시보드 고도화 ①·② 일괄 반영 + ABSA EXAONE 정밀 보고. **(A) ABSA 균형/딥다이브 토글**: `data_loader.compute_aspect_polarity(sample_mode=...)` + `get_absa(sample_mode=...)` 인자 추가 — `balanced`(phase_e 12,056건, 4브랜드 동등) / `all`(phase_e + complement, FILA 20K + 경쟁 3K, 6.6:1 비대칭). `4_ABSA.py` 상단에 `analysis_mode` 라디오 추가 → 모든 차트가 mode 따라 갱신. **(B) BERTopic × ABSA 교차 히트맵 (P1)**: 토픽 × 6속성 Sentiment Score(P−N) ∈ [-0.5, 0.5], 표본 30건 미만 셀 제외, 상위 15개 토픽. **(C) 시계열 부정 트렌드 (P1)**: 월별 N_ratio 라인 차트(4브랜드 색상), 속성 선택(전체/6속성), 30건 미만 월 제외. **(D) 브랜드 부정 비율 KPI 게이지 (P2)**: 6속성 평균 N_ratio 가로 막대 + 적색 그라데이션. **(E) `components/page_header.py` 신규 컴포넌트**: `render_page_intro(message, accent)` — 5페이지 모두 상단에 "이 페이지에서 알 수 있는 것" 박스 적용 (Main 네이비 / 2번 오렌지 / 3번 블루 / 4번 레드 / 5번 퍼플). **(F) 경고 메시지 정리**: `config.PATHS["positioning"]` → `positioning_scores.parquet`(미존재)으로 변경하여 schema mismatch 경고 제거. `get_topics()` strict schema check 제거 (기존 `_load_or_dummy` → 직접 load) — `get_topic_meta()` 컬럼 flexibility 의존, athleisure_bertopic.parquet의 `topic`/`keyword_1~5` 그대로 통과. `5_전략_포지셔닝.py`의 `warn_using_dummy("ABSA에서 즉석 산출 중")` 삭제. **(G) ABSA EXAONE v9 정밀 보고 (③ 대기)**: `absa_exaone/absa_v9.py`(674줄) + `ABSA_파이프라인_진행보고.md`(834줄) 직접 분석. Macro F1 0.7032의 **zero-sum 천장** 진단(v3~v9 7회 반복 trade-off) — 프롬프트만으로는 0.70 부근이 한계. 0.80+ 도달 경로: Conservative(A-1+A-2+A-3 프롬프트, +0.04~0.06) / Realistic(+B-1 골든셋 보더리 100~200건 재라벨링, +0.05~0.07) / Aggressive(+B-3 LoRA on Golden 800/200, +0.08~0.12). 라벨러 1명 단독 + κ=0.7141 → 모델 ceiling ≈ 0.85, 0.90+ 도달은 라벨 품질 자체 개선 없이 불가. ③ 사용자 결정 대기. **(H) ~/.claude memory 갱신**: project_streamlit_dashboard.md 갱신 + project_absa_phase_e_v9.md 신규 — Macro F1·zero-sum·0.80 점프 시나리오 영구 보존. |
| 2026-05-10 | ABSA Phase 1 격리 샌드박스 노트북 신규 + 대시보드 히트맵 P-N 고도화. **(I) `absa_phase1_sandbox.ipynb` 생성**: `송원우/absa_exaone/`에 7셀 노트북. (1) v9.py 헬퍼만 import (수정 없음, 격리). (2) 검증셋 973건(Few-shot 27건 제외) 풀에서 random_state=42로 100건 sample. (3) Phase 1 고도화 System Prompt — 핏/사이즈 vs 브랜드/헤리티지 boundary 명문화 (mutually exclusive 정의 + '편하다·좋다·찰떡' 단독 X 규칙 + 부정+긍정 혼재 시 후미 절 우선 + 의류 옵션명사 X). (4) Ollama JSON Schema 강제: 1차 structured outputs(JSON_SCHEMA dict) → 2차 format='json' 폴백 + 재시도. (5) 즉석 Macro F1 평가, v9 baseline(0.7032) 대비 Δ 출력, 속성별 비교. (6) 핏·브랜드 confusion matrix + 잔여 X→P/P→X 오분류 케이스 8건씩 노출. **목적**: zero-sum 천장 깨질 수 있는지 100건 빠른 검증, 본 서버·대시보드·v9.py 일절 영향 없음. **예상 Uplift**: +0.04~+0.06(Conservative) → 0.74~0.76 도달 가능성 검증. **(J) `4_ABSA.py` 히트맵 고도화**: 그룹 막대 No-Go 결정에 따라 기존 P_ratio 히트맵을 Sentiment Score(P−N) 히트맵으로 교체. zmin/zmax=−0.5~+0.5, midpoint=0.0(노랑), text_auto='+.2f', colorbar 'Sentiment (P−N)' tickvals=[−0.5,−0.25,0,0.25,0.5]. caption: 음수=부정 우세, 양수=긍정 우세, 0=양극 균형. P_ratio 단독 대비 약점 셀 시각적 식별 강화. |
| 2026-05-10 | **Phase 1 샌드박스 실측 결과 — Zero-sum 천장 가설 검증 완료**. 100건 random sample(SEED=42, FS 27건 제외 974건 풀에서) JSON Schema + Boundary 강화 프롬프트 실행. **결과: Macro F1 = 0.7013 vs v9 baseline 0.7032 → Δ = −0.0019 (사실상 변화 없음)**. 추론 속도 1.77초/건(M4 Pro Metal, 단일 스레드, 100건/176초). **속성별 검증**: 핏/사이즈 0.6107→**0.7759 (+0.1652)** ✅ — boundary 규칙("편하다·좋다 단독 X") 직격탄, X recall 0.27→0.60. 소재 0.7831→0.8416 (+0.0585) ✅. 그런데 **기능성 -0.0786 / 디자인 -0.0576 / 가격 -0.0899 폭락** — 동일 규칙이 "이쁘다·편하다" 단독을 다른 속성에서도 X로 분류, P recall 떨어짐. 브랜드/헤리티지 0.6019→0.5932 (-0.0087) — "또 살게요"는 잡지만 간접 충성도("하나더 있으면 좋겠다") 놓침. **결론: v3~v9 7회 trade-off 패턴이 8번째도 재현 — prompt-only 0.70 천장 실증**. 0.80+ 도달은 (1) 속성별 분리된 프롬프트 또는 (2) B-1 골든셋 보더리 재라벨링 또는 (3) B-3 LoRA 필수. Phase 1 단독으로는 zero-sum 깰 수 없음을 100건 실험으로 정량 입증. 라벨러1과 파이프라인 합의 시 B-1 우선 권고. |
| 2026-05-10 | **BERTopic 신규 산출물 4종 대시보드 연결**. `송원우/final_data/`에 도착: `dashboard_reviews_110M.parquet`(1,110,168건/6cols), `dashboard_reviews_22M.parquet`(213,972건/균형샘플), `dashboard_reviews_low.parquet`(9,448건/저평점 별도모델/topic_low,topic_name_low), `topic_dictionary.csv`(49토픽 메타: topic_id,topic_name,aspect,aspect_label,count,keywords_top5). **주의: review_id 부재** — ABSA·기존 reviews와 join 불가. 4_ABSA.py의 BERTopic×ABSA 히트맵은 기존 `athleisure_bertopic.parquet`(review_id 보유) 유지, 신규 4종은 3_BERTopic.py 단독 분석 전용. **변경**: (1) `config.PATHS`에 `bert_110m`/`bert_22m`/`bert_low`/`topic_dict` 추가. (2) `data_loader.py`에 `get_dashboard_reviews(scope='22m'|'all'|'low')` + `get_topic_dictionary()` 신규 — low 스코프는 자동 컬럼 리네임(topic_low→topic, topic_name_low→topic_name) + topic_name에서 [aspect] 정규식 추출. (3) `3_BERTopic.py` 전면 재작성 — 데이터 스코프 토글(22M 기본/110M 전체/low 저평점), aspect 그룹별 막대 분포, 트리맵(aspect→topic 2-level path, count 면적), 토픽 카드 Top8(키워드 dict 매칭), 브랜드×토픽 정규화 토글(상위 15토픽), 드릴다운(토픽 KPI+브랜드/평점 필터+content 30건). 검증: 3 스코프 모두 정상 로드, 페이지 신택스 OK. |
| 2026-05-10 | **Phase 2 GT 재라벨링 boundary case 추출 스크립트 작성** — `송원우/absa_exaone/extract_boundary_cases.py` (421줄). 사용자 안(핏·브랜드 우선/X↔P-N 혼동/150건/Excel) + 5가지 개선 통합: **(A) Priority Score** — 타겟 속성 mismatch ×2, X↔P-N +1, P↔N ×3 (sentiment 정반대 가중치), 라벨러 overlap 100건 교집합 시 +2. **(B) Error Type Stratified** — 12 bucket(핏/브랜드 × X→P/X→N/P→X/N→X/P→N/N→P) 균등 quota(75:75) → 자연 분포 X→P 쏠림 차단. **(C) Hint 자동 생성** — 정규식 9패턴 매칭(편하다 단독·재구매 표현·혼재 -는데/-지만·브랜드명·사이즈수치·핏 직접 단어 등)으로 모델 오답 추정 원인 자동 부착, 라벨러 케이스당 판단 시간 단축. **(D) 정답지 분리 파일** — `_answers.xlsx` 별도 저장으로 anchoring bias 완화, 라벨러 작업 후 검증용. **(E) v9 추론 캐시** — `absa_v9_validation_predictions.parquet` 1회 ~30분 생성 후 재사용. **출력**: `absa_relabel_boundary_150.xlsx`(가이드/라벨링/분포 3시트, _NEW 컬럼 노란색 강조) + `absa_relabel_boundary_150_answers.xlsx`. **검증 시 발견**: 골든셋 1,000건 review_id ∩ phase_e/complement = 0건 (별개 sampling), v9 검증셋 974건 predictions 미저장 상태였음 → 스크립트가 캐시 부재 시 자동 추론 실행하도록 설계. **검증**: 신택스 OK, BUCKET 합계 150 정확, Hint 함수 5개 테스트 케이스 4/5 정확 매칭. **실행 방법**: `uv run python 송원우/absa_exaone/extract_boundary_cases.py` (974건 추론 미캐시 시 1.77초/건 × 974 ≈ 30분, 이후 즉시). |
| 2026-05-10 | **Phase 2 사전 준비 3종 작성 완료** (라벨러1 1-2시간 작업 병행). **(I) `apply_relabel_v24.py`**(180줄) — _NEW 라벨 검증(결측/잘못된라벨 감지) + v2.3↔v2.4 sample_idx 매칭 머지 + 속성별 transition matrix 리포트(v23 GOLD→v24 NEW 6속성 crosstab). 결측 시 미작성 sample_idx 출력 후 abort. **(II) `absa_v10.py`**(69줄) — v9 로직 100% 재export(프롬프트/트리거/JSON/후보정 무수정), default golden path만 v23→v24 변경. v24 미존재 시 명확한 FileNotFoundError. **(III) `run_phase2_pipeline.py`**(236줄) — End-to-End 1-clic: Step1 v2.4 빌드 → Step2 v10 974건 추론(~30분, 캐시 활용) → Step3 F1 측정(v9 baseline 0.7032 대비 Δ + 속성별 비교) → Step4 분기 자동 판정(A:F1≥0.78=Phase E 29K 재추론 권고 / B:0.74~0.78=per-aspect or 추가 100건 / C:<0.74=긴급 검토). 결측 발견 시 abort, 캐시 사용으로 재실행 빠름. **검증**: 3개 파일 신택스 OK, validate_new_labels 3개 케이스(완료/결측/잘못된라벨) 정확 감지, merge_to_v24 더미 데이터로 P/N 적용 + 미라벨링 행 v23 유지 확인, transition matrix 정상 출력. **사용자 1-clic**: `uv run python 송원우/absa_exaone/run_phase2_pipeline.py` → 라벨러1 결과 받자마자 ~30분 내 F1 결과 + 시나리오 판정. |
| 2026-05-11 | **Phase 2 v10 추론 결과: F1 0.6676 (Δ -0.0356, 시나리오 C)**. 라벨러1 _NEW 적용 후 5/6 속성에서 F1 하락(브랜드/헤리티지만 +0.0262). 변경량 분석: 라벨러1은 압도적으로 P/N→X 보수화(디자인 P→X 25건/ 핏 N→X 17건 등). 부호 전환(P↔N)은 거의 없고 "언급 자체의 존재 여부"를 다르게 판단. **두 가설 분기**: H1(v24가 옳다 = v23 over-labeling) vs H2(라벨러1 too strict). 본질적 진단 위해 spot-check 30건 추출 진행. |
| 2026-05-11 | **Spot-check 30건 검증 스크립트 2종 작성** — `송원우/absa_exaone/extract_spotcheck_30.py`(라벨러1이 P/N→X로 변경한 케이스 4속성 stratified 30건 추출: 핏 7/소재 7/기능성 7/디자인 9, openpyxl 라벨링+가이드라인 2시트), `kappa_spotcheck.py`(송원우 작성 후 일치율 측정). **핵심 발견**: 추출 30건은 라벨러1이 모두 X로 라벨한 single-class라 Cohen's κ가 항상 0에 수렴 → **Agreement Rate(AR) = (송원우=X)/30 을 주 지표로 사용**, κ는 보조. 분기: AR≥75% H1(LoRA 경로) / 50~75% 중간(가이드라인 정렬+추가 100건) / <50% H2(v23 baseline 유지). Mock 70% 일치 데이터로 dry-run 시 AR 56.7% → 중간 영역 분기 정상. 송원우 작업: Excel 30칸 작성(~15분) → `absa_spotcheck_30_completed.xlsx` 저장 → `uv run python kappa_spotcheck.py`. |
| 2026-05-11 | **대시보드 UI 버그 4종 수정**. **(1) 히트맵 소수점 미반올림**: `text_auto="+.2f"` Plotly 버전 미호환 — `_pivot.round(2).values` 선반올림 + `update_traces(texttemplate="%{text}")` 명시적 방식으로 교체(4_ABSA.py 메인 히트맵·BERTopic×ABSA 히트맵 2건). **(2) 토픽 트리맵 단일 색상**: `topic_dict`가 빈 DF일 때 `aspect_label="전체"` 고정 → 전 셀 동일 색. `topic_name` 대괄호 `\[([^\]]+)\]` 정규식 추출로 교체 — 사이즈/핏·기능성·소재·디자인·가격 등 aspect별 색상 분리(3_BERTopic.py). **(3) 속성 그룹 영문 표시**: topic_dict 없을 때 raw `aspect_other`/`aspect_size` 등 영문 노출 — `_asp_kr` 매핑(aspect_other→기타/aspect_size→핏/사이즈 등) 적용. `_ASPECT_KR` 전역 dict에 `aspect_other→기타` 추가(3_BERTopic.py). **(4) PMI 불용어 미적용**: `_compute_pmi_centrality()` vocab 필터에 stopword 없어 있다/좋다/없다/너무 등 일반어 Top15 진입 — `_PMI_STOPWORDS` 30개 frozenset 신규 정의 + vocab set comprehension에 `and w not in _PMI_STOPWORDS` 추가(5_전략_포지셔닝.py). **주의**: PMI 섹션은 `@st.cache_data` 적용 중이므로 변경 적용 위해 Streamlit 캐시 초기화(C 키) 또는 재시작 필요. |
| 2026-05-11 | **결정: v23 유지 (Phase 2 v24 채택 보류)**. 사용자가 spot-check 30건 라벨링 작업 없이 v23을 active baseline으로 유지 결정. **유지 근거**: F1 -0.0356 + 라벨러1 보수화 패턴 단독으로는 v23 over-labeling을 단정 불가, 추가 검증(spot-check) 비용 대비 의사결정 가치 작음. **유지 영향**: (1) 모델 = `absa_v9.py`(=Macro F1 0.7032) (2) 골든셋 = `absa_golden_set_1000_v23.xlsx` (3) Phase E predictions = 기존 12,056 + complement 17,014 = 29,070건 그대로 (대시보드 변경 없음) (4) 인사이트(White Space X≈0.55, Y≈0.40~0.45) 변경 없음. **사용 안 함 산출물**: `absa_golden_set_1000_v24.xlsx`, `absa_v10_validation_predictions.parquet`, `absa_spotcheck_30_for_review.xlsx`(미작성 상태) — 정책상 삭제하지 않고 보존(추후 LoRA 등 재검토 시 활용 가능). **사용 안 함 스크립트**: `apply_relabel_v24.py`, `absa_v10.py`, `run_phase2_pipeline.py`, `extract_spotcheck_30.py`, `kappa_spotcheck.py` — 코드는 유지, 향후 재라벨링 사이클 시 재사용. **다음 단계 미정**: 사용자 결정 대기 (LoRA 별도 트랙 / 대시보드 finalization / C-Level 보고서 / 추가 분석). |
| 2026-05-12 | **카테고리 expander 자식 새짐 버그 + White Space 좌표 정합화**. **(1) filters.py expander 새짐**: `with sb.expander(...)` 안에서 `sb.checkbox(...)` 호출 시 사이드바 root에 그려지면서 expander 밖으로 체크박스 8/26/9개가 흘러나오던 시각 버그. `sb.checkbox` → `st.checkbox`(현재 active 컨텍스트 = expander)로 교체. cat3(소분류) expander도 추가하여 brand_page에서 전달되는 옵션 활용. **검증**: AppTest.expander 자식 수 정확히 8/26/9, 사이드바 root checkbox 0개. **(2) 5_전략_포지셔닝.py White Space 좌표 정합화**: 기존 Option A(0.45,0.85)/B(0.70,0.75)/C(0.80,0.40)이 dashboard 포지셔닝 맵의 실제 좌표(FILA 0.91/0.98, 룰루레몬 0.96/0.95, 안다르 0.93/0.95, 젝시믹스 0.94/0.92)와 완전히 다른 공간이었음. 좌표는 (P-N)/(P+N) → 0.5*(1+score) 정규화로 모든 브랜드가 0.91~0.97 범위에 클러스터링됨. **재보정**: Option A Heritage Defender (0.94, 0.98) Δx +0.03 — 헤리티지 1위 유지 + 기능성 격차 절반 좁힘, R&D 부담 無. Option B Holistic Leader (0.96, 0.97) Δx +0.05/Δy -0.01 — 룰루레몬 기능성 좌표 직접 매치. Option C Function Catch-up (0.95, 0.93) Δx +0.04/Δy -0.05 — 안다르/젝시믹스 수준 기능성 추격, 헤리티지 양보. 캡션에 "좌표는 '언급 시 긍정 강도' / 발화량(BERTopic) FILA 기능성 9.7% vs 룰루레몬 46.7%로 4배 차이" 명시. 12~24개월 3-Phase 로드맵 박스에 각 Phase별 KPI 지표(반품률·디자인 P_ratio·기능성 발화 점유율·재구매율) 추가. **PDF 좌표계 별도**: generate_report.py의 positioning_svg는 raw P-N sentiment(0.17~0.67) 공간으로 자체 White Space (0.55, 0.43) 일관성 유지 — 변경 없음. PDF 952KB 재출력. |
| 2026-05-12 | **Main 브랜드 매출 차트 버그 + 3페이지 인사이트 카드 디벨롭 + PDF 재출력**. **(1) brand_page.py 매출 고정 버그**: `_sales_placeholder(brand_key, color)` → `_sales_placeholder(effective_brand, color)` — 사용자가 pill로 다른 브랜드 선택해도 매출 차트가 FILA에 고정되던 버그 수정. **(2) 카테고리 필터 expander 확인**: `filters.py`의 대분류/중분류는 `sb.expander(expanded=False)`로 처음에는 접혀 있고 클릭 시 펼쳐짐 — 기존 동작 그대로 정상. **(3) Main.py 핵심 전략 인사이트 3카드 갱신**: ① FILA 평점 순위(동적) + "고관여 충성도 확보됨" 추가. ② ABSA 강·약점 + BERTopic FILA 기능성 발화 8.3%(시장 평균 29.2%의 1/3) 결합 — "담론 빈자리" 명시. ③ 정적 카드 → BERTopic 1위 토픽이 신발(슈즈/양말/삭스) + 저평점 핏 46.4%+품질 36.8%=83% — "사이즈 표 정확화 + 형태 안정성" 명시. **(4) 2_상품_및_고객_전략.py Action Recommendation 3카드 재작성**: ① 1순위 방어선(저평점 83% 차단, 50회 세탁 후 형태 인증) ② 무채색 60% + 디자인 강점 카드(P_ratio +0.611 4브랜드 1위) ③ 기능성 발화 점유 회복(룰루레몬 46.7% vs FILA 9.7%, 12개월 KPI 30%). 각 카드 근거 파일명 명시(dashboard_reviews_low.parquet, dashboard_reviews_22M.parquet). **(5) 5_전략_포지셔닝.py White Space 3옵션 재작성**: Option A 헤리티지 프리미엄(Design-Led, +0.611 자산 직접 전이) / Option B Holistic Leader(R&D + 발화 30% KPI) / Option C 기능 우선 진입(저평점 83% 차단). 좌표·발화량·sentiment 점수 모두 carry. 하단에 **권장 진입 경로 12~24개월 3-Phase 로드맵** 박스 추가 (Phase 1: Option C 단기 액션 → Phase 2: Option A 디자인 컬렉션 → Phase 3: Option B 기능성 R&D). **(6) generate_report.py PDF 재출력** 952KB 9페이지. **검증**: 5페이지 AppTest exceptions=0/errors=0 + Main 브랜드 pill switch(brands="안다르")도 0건. |
| 2026-05-12 | **BERTopic 최신 데이터셋 연결 + 사이드바 필터 충돌 해소 + aspect_quality 매핑**. `송원우/final_data/`에 갱신 도착: `dashboard_reviews_110M.parquet`(1,110,129건), `dashboard_reviews_22M.parquet`(213,812건), `dashboard_reviews_low.parquet`(9,445건, `topic_low/topic_name_low/aspect_low` 컬럼), 신규 `topic_aspect_mapping.parquet`(49토픽 메타), `low_topic_aspect_mapping.parquet`(30토픽). **수정 ① session 정합화 (`utils/session.py`)**: `_DEFAULTS["brands"]`를 `BRAND_ORDER[0]` 단일 string → `list(BRAND_ORDER)`로 변경 (사이드바 multi-pills 호환), `year_range` 디폴트 `(2022,2026)`→`(2024,2026)` (슬라이더 min/max와 동기화). `init_session()`에 잔존 단일 string brands 자동 list 변환 + year_range 클램핑 추가. **수정 ② brand_page.py**: `st.session_state.brands = effective_brand`(string) → `[effective_brand]`(list) — 멀티 pills와 타입 불일치 해소. **수정 ③ filters.py**: `show_year`/`show_price`/`show_category` 파라미터 추가 — BERTopic 페이지에서 year/cat/price 슬라이더 숨김 가능. brand pills 호출 직전 string→list 정합화 가드. **수정 ④ config.py**: `PATHS`에 `topic_map`/`topic_map_low` 추가. `BERT_ASPECT_KR`(8개 키→한글) + `BERT_ASPECT_COLOR`(트리맵·파이 색) 신규 — `aspect_quality`("품질/내구성") 정식 매핑 (기존 누락분 보강). ABSA 6속성과 키 체계 다름 명시. **수정 ⑤ data_loader.py**: `get_dashboard_reviews()` low 스코프 컬럼 통일 + `aspect_label` 자동 매핑(BERT_ASPECT_KR 우선, `[bracket]` 폴백, "기타" 최종). `get_topic_dictionary(scope='all'|'low')` 신규 — `topic_aspect_mapping.parquet` 로드 + `aspect_label`/`keywords_top5` 파생. **수정 ⑥ 3_BERTopic.py**: 페이지 진입 시 `render_sidebar_filters(show_year=False, show_price=False, show_category=False)` 호출 (사이드바 brand·rating만 노출). 필터 적용 코드 — 잔존 string brands list 정합화 + 빈 리스트 시 BRAND_ORDER 폴백 + rating 안전 int 변환. `aspect_label` 매핑 로직 전부 제거(data_loader가 처리) — Aspect 분포·트리맵·브랜드 파이가 모두 단일 `aspect_label` 컬럼 + `BERT_ASPECT_COLOR` 사용. 트리맵 색상 `color="n"`(연속)→`color="aspect_label"`(범주별, 매개변수=BERT_ASPECT_COLOR)로 교체. **검증**: 5페이지 × Streamlit AppTest = 모두 exceptions=0/errors=0. 3 BERTopic scope(all/22m/low) 전환 0건. 엣지(brands=string/[]/rating=5/year=(2022,2026) 옛값) 모두 0건. 데이터: 110M aspect_label 7군(노이즈 433K 제외), 22M·low도 정상. |
