"""
data_loader.py — 통합 데이터 로더 + 더미 생성기
================================================

설계 원칙 (Decoupled Architecture):
- 페이지·컴포넌트는 절대 parquet 경로를 직접 알지 못한다.
- get_reviews(), get_topics(), get_absa(), get_positioning(), get_sna() 만 호출.
- 실제 파일이 존재하면 → 로드 + 스키마 검증.
- 존재하지 않으면 → 결정론적(seed) 더미를 즉시 생성하여 동일 인터페이스로 반환.
- 모델팀이 Parquet을 떨어뜨리는 순간, 페이지 코드 변경 없이 실데이터로 전환.

캐시 전략:
- 모든 로더는 @st.cache_data(ttl=CACHE_TTL).
- 인자 단위로 캐시 키 생성 → 필터 조합별 결과 보존.
- 117만 건 reviews 는 columns 인자로 사용 컬럼만 로드 (Parquet 컬럼 프루닝).
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from config import (
    PATHS, CACHE_TTL, BRAND_ORDER, ASPECT_KEYS, SENTIMENT_LABELS,
    MIN_REVIEWS_FOR_BRAND_SCORE,
)
from utils.data_contracts import (
    REVIEWS_SCHEMA, TOPICS_SCHEMA, TOPIC_META_SCHEMA,
    ABSA_SCHEMA, POSITIONING_SCHEMA, SNA_SCHEMA,
    check_schema,
)
from utils.exceptions import warn_using_dummy

logger = logging.getLogger(__name__)

DUMMY_SEED = 42
DUMMY_REVIEW_N = 5_000   # 더미 모드에서 생성할 리뷰 수


# ═════════════════════════════════════════════════════════════
# 1. Reviews — 실데이터 우선, 없으면 더미
# ═════════════════════════════════════════════════════════════
@st.cache_data(ttl=CACHE_TTL, show_spinner="리뷰 데이터 로드 중...")
def get_reviews(columns: tuple[str, ...] | None = None,
                sample_n: int | None = None) -> pd.DataFrame:
    """리뷰 마스터 로드.

    Args:
        columns: 사용할 컬럼만 로드 (Parquet 컬럼 프루닝). None=전체.
        sample_n: 빠른 EDA용 다운샘플. None=전체.
    """
    path = PATHS["reviews"]
    if path.exists():
        cols = list(columns) if columns else None
        df = pd.read_parquet(path, columns=cols)
        # 부분 컬럼 로드 시 스키마 체크 생략 (누락 컬럼 오경보 방지)
        if cols is None:
            result = check_schema(df, REVIEWS_SCHEMA, "reviews")
            if not result.ok:
                logger.warning(result.summary())
        if sample_n and len(df) > sample_n:
            df = df.sample(sample_n, random_state=DUMMY_SEED)
        return df

    # 더미 폴백
    logger.info(f"[DUMMY] {path.name} 미발견 → 더미 생성")
    return _generate_dummy_reviews(DUMMY_REVIEW_N if not sample_n else sample_n)


@st.cache_data(ttl=CACHE_TTL)
def get_topics() -> pd.DataFrame:
    return _load_or_dummy(PATHS["topics"], TOPICS_SCHEMA, "topics", _generate_dummy_topics)


@st.cache_data(ttl=CACHE_TTL, show_spinner="토큰 데이터 로드 중...")
def get_tokens(brand: str | None = None,
               column: str = "tokens_topic") -> pd.DataFrame:
    """형태소 분석(사용자·불용·정규화 사전 적용) 토큰 로드.

    - 워드클라우드 등 어휘 빈도 분석에 사용.
    - PATHS["tokens"] 미존재 시 PATHS["reviews"] 의 'tokens' 컬럼으로 폴백.

    Args:
        brand: 특정 브랜드만 로드. None=전체.
        column: 'tokens_topic'(BERTopic용 — stopword/길이 필터 강함) 또는 'tokens'.
    """
    path = PATHS.get("tokens", PATHS["reviews"])
    if not path.exists():
        path = PATHS["reviews"]
    if not path.exists():
        return pd.DataFrame(columns=["brand", column])

    cols = ["brand", column]
    df = pd.read_parquet(path, columns=cols)
    if brand is not None:
        df = df[df["brand"] == brand]
    return df


@st.cache_data(ttl=CACHE_TTL)
def get_topic_meta() -> pd.DataFrame:
    """토픽 메타(topic_id별 1행). topics에서 파생."""
    topics = get_topics()

    if topics.empty:
        return pd.DataFrame(columns=list(TOPIC_META_SCHEMA.keys()))

    # BERTopic 실 산출물은 'Topic' (대문자) 컬럼을 사용할 수 있음
    if "topic_id" not in topics.columns and "Topic" in topics.columns:
        topics = topics.rename(columns={"Topic": "topic_id"})

    if "topic_id" not in topics.columns:
        warn_using_dummy("토픽 메타데이터 (컬럼 누락)")
        rng = np.random.default_rng(DUMMY_SEED + 10)
        dummy_topics = [
            ("쿠셔닝/착용감", ["쿠션", "폭신", "착용감", "안정감"]),
            ("핏/보정",       ["핏", "사이즈", "라인", "보정"]),
            ("디자인/색감",   ["디자인", "색상", "컬러", "패턴"]),
            ("소재/촉감",     ["소재", "촉감", "원단", "신축성"]),
            ("재구매/추천",   ["재구매", "추천", "단골", "믿고"]),
        ]
        return pd.DataFrame([
            {
                "topic_id":   i,
                "topic_name": name,
                "n_reviews":  int(rng.integers(500, 5000)),
                "keywords":   kws,
                "axis_hint":  _axis_hint_for_topic(name),
                "representative_doc": "",
            }
            for i, (name, kws) in enumerate(dummy_topics)
        ])

    agg_kwargs: dict = {"topic_name": ("topic_name", "first")} if "topic_name" in topics.columns else {}
    id_col = "review_id" if "review_id" in topics.columns else topics.columns[0]
    agg_kwargs["n_reviews"] = (id_col, "count")
    if "topic_keywords" in topics.columns:
        agg_kwargs["keywords"] = ("topic_keywords", "first")

    meta = topics.groupby("topic_id", as_index=False).agg(**agg_kwargs)

    if "topic_name" not in meta.columns:
        meta["topic_name"] = meta["topic_id"].astype(str)
    if "keywords" not in meta.columns:
        meta["keywords"] = [[] for _ in range(len(meta))]

    meta["axis_hint"] = meta["topic_name"].apply(_axis_hint_for_topic)
    meta["representative_doc"] = ""
    return meta


@st.cache_data(ttl=CACHE_TTL)
def get_absa() -> pd.DataFrame:
    """ABSA 감성 분석 결과 로드.

    우선순위:
      1. 라벨러1 + 송원우 complement 둘 다 있으면 → concat + drop_duplicates("review_id")
      2. 하나만 있으면 → 해당 파일 단독 사용
      3. 둘 다 없으면 → 기존 absa_predictions_full.parquet 폴백
      4. 모두 없으면 → 더미
    """
    path_l1   = PATHS.get("absa_labeler1")
    path_comp = PATHS.get("absa_complement")
    has_l1    = path_l1 is not None and path_l1.exists()
    has_comp  = path_comp is not None and path_comp.exists()

    if has_l1 and has_comp:
        l1   = pd.read_parquet(path_l1)
        comp = pd.read_parquet(path_comp)
        merged = (
            pd.concat([l1, comp], ignore_index=True)
            .drop_duplicates("review_id")
        )
        result = check_schema(merged, ABSA_SCHEMA, "absa (merged)")
        if result.missing:
            logger.warning(result.summary())
        logger.info(f"[ABSA] merged: l1={len(l1):,} + complement={len(comp):,} → {len(merged):,}")
        return merged

    if has_l1:
        return _load_or_dummy(path_l1, ABSA_SCHEMA, "absa (labeler1)", _generate_dummy_absa)

    if has_comp:
        return _load_or_dummy(path_comp, ABSA_SCHEMA, "absa (complement)", _generate_dummy_absa)

    # 기존 단일 파일 폴백 (하위 호환)
    return _load_or_dummy(PATHS["absa"], ABSA_SCHEMA, "absa", _generate_dummy_absa)


@st.cache_data(ttl=CACHE_TTL)
def get_positioning() -> pd.DataFrame:
    """브랜드 단위 포지셔닝. 실파일 없으면 ABSA에서 즉시 계산."""
    path = PATHS["positioning"]
    if path.exists():
        df = pd.read_parquet(path)
        result = check_schema(df, POSITIONING_SCHEMA, "positioning")
        if result.missing:
            logger.warning(result.summary())
            warn_using_dummy(f"포지셔닝 좌표 (스키마 불일치 — 누락 컬럼: {result.missing})")
            return compute_positioning_from_absa()
        return df
    # 폴백: absa + reviews 조합으로 즉시 산출
    return compute_positioning_from_absa()


@st.cache_data(ttl=CACHE_TTL)
def get_sna() -> pd.DataFrame:
    return _load_or_dummy(PATHS["sna"], SNA_SCHEMA, "sna", _generate_dummy_sna)


# ═════════════════════════════════════════════════════════════
# 2. 파생 집계 (페이지 공용)
# ═════════════════════════════════════════════════════════════
@st.cache_data(ttl=CACHE_TTL)
def compute_brand_kpis(filters_hash: str = "") -> pd.DataFrame:
    """브랜드별 핵심 KPI — 시장 현황 페이지용.

    filters_hash 는 session 필터 변경 감지용 캐시 무효화 키.
    """
    reviews = get_reviews(columns=("review_id", "brand", "rating", "year"))
    if reviews.empty:
        return pd.DataFrame()

    grp = reviews.groupby("brand", observed=True)
    kpi = grp.agg(
        n_reviews=("review_id", "count"),
        mean_rating=("rating", "mean"),
        rating_std=("rating", "std"),
    ).reset_index()
    kpi["mean_rating"] = kpi["mean_rating"].round(2)
    kpi["rating_std"]  = kpi["rating_std"].round(2)
    return kpi.reindex([kpi.index[kpi["brand"] == b][0]
                        for b in BRAND_ORDER if b in kpi["brand"].values]).reset_index(drop=True)


@st.cache_data(ttl=CACHE_TTL)
def compute_aspect_polarity(filters_hash: str = "") -> pd.DataFrame:
    """브랜드 × 6속성 P/N/X 비율 — ABSA 페이지용.

    Returns: long-format [brand, aspect, P_ratio, N_ratio, X_ratio, n_reviews]
    """
    reviews = get_reviews(columns=("review_id", "brand"))
    absa    = get_absa()
    if absa.empty or reviews.empty:
        return pd.DataFrame()

    df = reviews.merge(absa, on="review_id", how="inner")
    rows = []
    for brand, sub in df.groupby("brand", observed=True):
        n = len(sub)
        if n < MIN_REVIEWS_FOR_BRAND_SCORE:
            continue
        for aspect in ASPECT_KEYS:
            counts = sub[aspect].value_counts(normalize=True)
            rows.append({
                "brand":  brand,
                "aspect": aspect,
                "P_ratio": float(counts.get("P", 0.0)),
                "N_ratio": float(counts.get("N", 0.0)),
                "X_ratio": float(counts.get("X", 0.0)),
                "n_reviews": n,
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=CACHE_TTL)
def compute_positioning_from_absa() -> pd.DataFrame:
    """ABSA → 브랜드 좌표 즉석 산출 (positioning_scores 부재 시 폴백).

    좌표 산출 공식:
      polarity_score = (P_ratio - N_ratio) / (P_ratio + N_ratio + ε)   ∈ [-1, 1]
      x_function     = 0.5 * (1 + functionality_score)                 ∈ [0, 1]
      y_heritage     = 0.5 * (1 + brand_heritage_score)                ∈ [0, 1]

    설계 노트:
    - minmax 정규화는 4브랜드 비교에서 항상 한 브랜드를 0, 한 브랜드를 1로
      찍는 부작용이 있어, 절대 스케일 (P-N)/(P+N) → [0,1] 선형 변환을
      사용한다. 0.5 = 중립(P=N), 1.0 = 전 긍정, 0.0 = 전 부정.
    - 해당 속성에서 ABSA 결과가 없는 브랜드는 NaN을 유지한다(0으로 채우면
      좌하단으로 잘못 시각화됨).
    """
    pol = compute_aspect_polarity()
    if pol.empty:
        return pd.DataFrame()

    func  = pol[pol["aspect"] == "functionality"].set_index("brand")
    brand = pol[pol["aspect"] == "brand_heritage"].set_index("brand")

    out = pd.DataFrame(index=BRAND_ORDER)
    eps = 1e-9
    fn_score = (func["P_ratio"] - func["N_ratio"]) / (func["P_ratio"] + func["N_ratio"] + eps)
    bh_score = (brand["P_ratio"] - brand["N_ratio"]) / (brand["P_ratio"] + brand["N_ratio"] + eps)

    # 절대 스케일 [-1,1] → [0,1] 선형 변환 (minmax 부작용 회피)
    out["x_function"] = 0.5 * (1 + fn_score)
    out["y_heritage"] = 0.5 * (1 + bh_score)

    # 신뢰구간 ±0.05 (NaN은 NaN으로 자연 전파)
    out["x_function_ci_low"]  = out["x_function"] - 0.05
    out["x_function_ci_high"] = out["x_function"] + 0.05
    out["y_heritage_ci_low"]  = out["y_heritage"] - 0.05
    out["y_heritage_ci_high"] = out["y_heritage"] + 0.05

    out["n_reviews"]   = func["n_reviews"]
    out["mean_rating"] = np.nan
    out["top_strengths"]  = [[] for _ in range(len(out))]
    out["top_weaknesses"] = [[] for _ in range(len(out))]
    out["top_topics"]     = [[] for _ in range(len(out))]
    out = out.reset_index().rename(columns={"index": "brand"})
    return out


# ═════════════════════════════════════════════════════════════
# 3. 더미 생성기 — 결정론적, 스키마 호환
# ═════════════════════════════════════════════════════════════
def _load_or_dummy(path: Path, schema: dict, name: str, dummy_fn) -> pd.DataFrame:
    if path.exists():
        df = pd.read_parquet(path)
        result = check_schema(df, schema, name)
        if result.missing:
            logger.warning(result.summary())
            warn_using_dummy(f"{name} (스키마 불일치 — 누락 컬럼: {result.missing})")
            return dummy_fn()
        return df
    logger.info(f"[DUMMY] {path.name} 미발견 → 더미 생성")
    return dummy_fn()


def _generate_dummy_reviews(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(DUMMY_SEED)
    cats = ["상의", "하의", "세트상품", "신발", "양말", "아우터"]
    sizes = ["S", "M", "L", "XL"]
    genders = ["women", "men", "unisex"]

    df = pd.DataFrame({
        "review_id": [f"R{i:07d}" for i in range(n)],
        "brand":     rng.choice(BRAND_ORDER, n, p=[0.15, 0.30, 0.35, 0.20]),
        "cat1":      rng.choice(cats, n),
        "cat2":      rng.choice(sizes, n),
        "cat3":      "",
        "gender":    rng.choice(genders, n),
        "rating":    pd.array(rng.choice([1, 2, 3, 4, 5], n, p=[0.03, 0.04, 0.08, 0.25, 0.60]), dtype="Int8"),
        "review_date": pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 800, n), unit="D"),
    })
    df["year"]  = df["review_date"].dt.year.astype("Int16")
    df["month"] = df["review_date"].dt.month.astype("Int8")
    df["content"]       = "[더미] 리뷰 본문"
    df["content_clean"] = "[더미] 정제 본문"
    df["content_len"]   = pd.array(rng.integers(10, 200, n), dtype="Int32")
    df["tokens"]        = [["더미","토큰"] for _ in range(n)]
    df["tokens_topic"]  = [["더미","토픽"] for _ in range(n)]
    return df


def _generate_dummy_topics() -> pd.DataFrame:
    """리뷰별 토픽 할당 더미. reviews 의 review_id 와 정합성 유지."""
    rev = get_reviews(columns=("review_id",))
    if rev.empty:
        return pd.DataFrame(columns=list(TOPICS_SCHEMA.keys()))

    rng = np.random.default_rng(DUMMY_SEED + 1)
    topic_pool = [
        ("쿠셔닝/착용감", ["쿠션", "폭신", "푹신", "발편안", "착용감", "안정감", "충격흡수", "발걸음"]),
        ("핏/보정",        ["핏", "사이즈", "라인", "보정", "허리", "Y존", "압박감", "라이즈"]),
        ("디자인/색감",   ["디자인", "예쁘다", "색상", "이쁘다", "패턴", "컬러", "실물", "포인트"]),
        ("소재/촉감",     ["소재", "촉감", "원단", "부드럽다", "쫀쫀", "두께", "신축성", "기모"]),
        ("재구매/추천",   ["재구매", "추천", "또 살게요", "단골", "믿고", "팬", "다시", "여러개"]),
        ("가성비/할인",   ["가격", "가성비", "할인", "세일", "저렴", "비싸다", "혜택", "쿠폰"]),
        ("배송/포장",     ["배송", "포장", "빠르다", "꼼꼼", "박스", "도착", "발송", "구김"]),
        ("운동/활동성",   ["운동", "요가", "필라테스", "골프", "러닝", "활동성", "땀", "통기성"]),
    ]
    n = len(rev)
    tids = rng.integers(0, len(topic_pool), n)
    df = pd.DataFrame({
        "review_id": rev["review_id"].values,
        "topic_id":  pd.array(tids, dtype="Int16"),
        "topic_name": [topic_pool[t][0] for t in tids],
        "topic_label_auto": [f"topic_{t}" for t in tids],
        "topic_keywords":   [topic_pool[t][1] for t in tids],
        "probability":      rng.uniform(0.3, 0.95, n).astype("float32"),
    })
    return df


def _generate_dummy_absa() -> pd.DataFrame:
    rev = get_reviews(columns=("review_id", "brand", "rating"))
    if rev.empty:
        return pd.DataFrame(columns=list(ABSA_SCHEMA.keys()))

    rng = np.random.default_rng(DUMMY_SEED + 2)
    n = len(rev)

    # 브랜드별 사전 — 휠라(헤리티지 약/기능 중), 룰루레몬(둘 다 강) 시뮬
    brand_priors = {
        "FILA":     {"functionality": [0.30, 0.10, 0.60], "brand_heritage": [0.25, 0.15, 0.60]},
        "안다르":   {"functionality": [0.45, 0.10, 0.45], "brand_heritage": [0.35, 0.10, 0.55]},
        "젝시믹스": {"functionality": [0.50, 0.08, 0.42], "brand_heritage": [0.40, 0.08, 0.52]},
        "룰루레몬": {"functionality": [0.55, 0.12, 0.33], "brand_heritage": [0.55, 0.05, 0.40]},
    }
    default_prior = [0.40, 0.10, 0.50]

    out = {"review_id": rev["review_id"].values}
    for aspect in ASPECT_KEYS:
        labels = []
        for b in rev["brand"].values:
            if aspect in ("functionality", "brand_heritage"):
                p = brand_priors.get(str(b), {}).get(aspect, default_prior)
            else:
                p = default_prior
            labels.append(rng.choice(SENTIMENT_LABELS, p=p))
        out[aspect] = pd.Categorical(labels, categories=SENTIMENT_LABELS)
        out[f"{aspect}_confidence"] = rng.uniform(0.55, 0.98, n).astype("float32")
    return pd.DataFrame(out)


def _generate_dummy_sna() -> pd.DataFrame:
    rng = np.random.default_rng(DUMMY_SEED + 3)
    keywords_pool = [
        "쿠션", "착용감", "쫀쫀", "통기성", "보정", "허리", "재구매", "추천", "디자인",
        "색감", "가성비", "사이즈", "기능성", "신축성", "발편안", "운동",
    ]
    rows = []
    for b in BRAND_ORDER:
        for kw in keywords_pool:
            rows.append({
                "keyword":    kw,
                "brand":      b,
                "centrality": float(rng.uniform(0.05, 0.95)),
                "topic_id":   int(rng.integers(0, 8)),
                "frequency":  int(rng.integers(50, 5000)),
                "polarity":   float(rng.uniform(-0.4, 0.9)),
            })
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════
# 4. 보조
# ═════════════════════════════════════════════════════════════
def _axis_hint_for_topic(name: str) -> str:
    if any(kw in name for kw in ["쿠셔닝", "기능", "활동", "운동", "통기"]):
        return "function"
    if any(kw in name for kw in ["재구매", "추천", "헤리티지", "브랜드"]):
        return "heritage"
    return "neutral"


def filters_to_hash(filters: dict) -> str:
    """session_state 의 필터 dict 를 안정적인 해시로 — 캐시 키."""
    s = "|".join(f"{k}={sorted(v) if isinstance(v, list) else v}" for k, v in sorted(filters.items()))
    return hashlib.md5(s.encode()).hexdigest()


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """공통 필터 적용기 — Graceful: 컬럼 없으면 무시."""
    if df.empty:
        return df
    out = df

    # 브랜드
    brands = filters.get("brands", [])
    if brands and "brand" in out.columns:
        out = out[out["brand"].isin(brands)]

    # 평점 (selectbox 단일값: "전체" / "1점" … "5점")
    rating_sel = filters.get("rating_sel", "전체")
    if rating_sel != "전체" and "rating" in out.columns:
        try:
            rating_val = int(rating_sel[0])
            out = out[out["rating"] == rating_val]
        except (ValueError, IndexError):
            pass

    # 연도 범위
    if "year_range" in filters and "year" in out.columns:
        lo, hi = filters["year_range"]
        out = out[(out["year"] >= lo) & (out["year"] <= hi)]

    # 카테고리1 / 2 / 3
    for col, key in [("cat1", "cat1_filters"), ("cat2", "cat2_filters"), ("cat3", "cat3_filters")]:
        vals = filters.get(key, [])
        if vals and col in out.columns:
            out = out[out[col].isin(vals)]

    # 가격 범위 (discount_price)
    if "price_range" in filters and "discount_price" in out.columns:
        lo, hi = filters["price_range"]
        out = out[(out["discount_price"] >= lo) & (out["discount_price"] <= hi)]

    return out
