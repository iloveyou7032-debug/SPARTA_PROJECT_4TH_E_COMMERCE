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


@st.cache_data(ttl=CACHE_TTL)
def get_topic_meta() -> pd.DataFrame:
    """토픽 메타(topic_id별 1행). topics에서 파생."""
    topics = get_topics()
    if topics.empty:
        return pd.DataFrame(columns=list(TOPIC_META_SCHEMA.keys()))
    meta = (topics
            .groupby("topic_id", as_index=False)
            .agg(topic_name=("topic_name", "first"),
                 n_reviews=("review_id", "count"),
                 keywords=("topic_keywords", "first")))
    meta["axis_hint"] = meta["topic_name"].apply(_axis_hint_for_topic)
    meta["representative_doc"] = ""  # 실데이터에서는 모델팀이 채움
    return meta


@st.cache_data(ttl=CACHE_TTL)
def get_absa() -> pd.DataFrame:
    return _load_or_dummy(PATHS["absa"], ABSA_SCHEMA, "absa", _generate_dummy_absa)


@st.cache_data(ttl=CACHE_TTL)
def get_positioning() -> pd.DataFrame:
    """브랜드 단위 포지셔닝. 실파일 없으면 ABSA에서 즉시 계산."""
    path = PATHS["positioning"]
    if path.exists():
        df = pd.read_parquet(path)
        result = check_schema(df, POSITIONING_SCHEMA, "positioning")
        if not result.ok:
            logger.warning(result.summary())
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

    공식 (단순):
      x_function = (P_func - N_func) / (P + N + ε)  → [0,1] minmax
      y_heritage = (P_brand - N_brand) / (P + N + ε) → [0,1] minmax
    """
    pol = compute_aspect_polarity()
    if pol.empty:
        return pd.DataFrame()

    func = pol[pol["aspect"] == "functionality"].set_index("brand")
    brand = pol[pol["aspect"] == "brand_heritage"].set_index("brand")

    out = pd.DataFrame(index=BRAND_ORDER)
    eps = 1e-9
    out["x_function_raw"] = (func["P_ratio"] - func["N_ratio"]) / (func["P_ratio"] + func["N_ratio"] + eps)
    out["y_heritage_raw"] = (brand["P_ratio"] - brand["N_ratio"]) / (brand["P_ratio"] + brand["N_ratio"] + eps)

    # 0~1 정규화 (4점 brand 비교용 minmax)
    for col in ["x_function_raw", "y_heritage_raw"]:
        s = out[col]
        out[col.replace("_raw", "")] = (s - s.min()) / (s.max() - s.min() + eps)
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
        if not result.ok:
            logger.warning(result.summary())
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
        "rating":    rng.choice([1, 2, 3, 4, 5], n, p=[0.03, 0.04, 0.08, 0.25, 0.60]).astype("Int8"),
        "review_date": pd.to_datetime("2024-01-01") + pd.to_timedelta(rng.integers(0, 800, n), unit="D"),
    })
    df["year"]  = df["review_date"].dt.year.astype("Int16")
    df["month"] = df["review_date"].dt.month.astype("Int8")
    df["content"]       = "[더미] 리뷰 본문"
    df["content_clean"] = "[더미] 정제 본문"
    df["content_len"]   = rng.integers(10, 200, n).astype("Int32")
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
        "topic_id":  tids.astype("Int16"),
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
