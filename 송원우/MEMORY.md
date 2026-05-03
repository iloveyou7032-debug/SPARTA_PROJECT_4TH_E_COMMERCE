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
