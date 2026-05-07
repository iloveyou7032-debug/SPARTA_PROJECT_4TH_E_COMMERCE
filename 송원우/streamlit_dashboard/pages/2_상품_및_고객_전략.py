"""
2_상품_및_고객_전략.py — 상품 및 고객 전략 분석
================================================

정형 데이터 기반 비즈니스 분석 (preprocessed_absa.parquet 실데이터):
  1. 체형별 만족도     — 키·몸무게 구간별 평균 평점 Heatmap
  2. 가격 탄력성       — 할인율(%) vs 평균 평점 Scatter (브랜드별 프리미엄 방어력 비교)
  3. 고관여 인게이지먼트 — 포토 리뷰 비율 + 평균 도움이 돼요 + 신상품 포토 비율
  4. SKU 복잡도        — 색상 수 구간별 리뷰 수 분포 Box Plot
  5. 컬러 빈도 분석    — 브랜드별 구매 옵션 상위 컬러
  6. 리뷰 볼륨 x 평점  — 브랜드 x 카테고리 사분면 Scatter
"""
from __future__ import annotations

import sys
from pathlib import Path

import re

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, BRANDS, BRAND_ORDER, CACHE_TTL
from utils.data_loader import get_reviews
from utils.session import init_session, get_filters, mark_page_visited
from utils.exceptions import safe_block, empty_state
from components.filters import render_sidebar_filters

st.set_page_config(
    page_title=f"{APP_TITLE} — 상품·고객 전략",
    page_icon=None,
    **PAGE_LAYOUT,
)
init_session()
mark_page_visited("product_strategy")

st.title("2. 상품 및 고객 전략")
st.caption("체형 적합성 · 가격 탄력성 · 고관여 인게이지먼트 · SKU 복잡도 · 컬러 빈도 · 사분면 분석")

render_sidebar_filters()
filters = get_filters()
active_brands = [b for b in BRAND_ORDER if b in filters.get("brands", BRAND_ORDER)]
if not active_brands:
    active_brands = BRAND_ORDER

_CMAP = {b: BRANDS[b]["color"] for b in BRAND_ORDER}

# ── 실데이터 집계 함수 ───────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL)
def _body_heatmap_df(brand: str) -> pd.DataFrame:
    df = get_reviews(columns=("brand", "user_height_group", "user_weight_group", "rating"))
    df = df[
        (df["brand"] == brand) &
        (df["user_height_group"] != "unknown") &
        (df["user_weight_group"] != "unknown")
    ]
    if df.empty:
        return pd.DataFrame()
    agg = df.groupby(["user_height_group", "user_weight_group"])["rating"].agg(
        평균_평점="mean", 리뷰수="count"
    ).reset_index()
    agg.columns = ["키 구간", "몸무게 구간", "평균 평점", "리뷰 수"]
    agg["평균 평점"] = agg["평균 평점"].round(2)
    return agg


@st.cache_data(ttl=CACHE_TTL)
def _price_elasticity_df(brand: str) -> pd.DataFrame:
    df = get_reviews(columns=("brand", "original_price", "discount_price", "rating"))
    df = df[
        (df["brand"] == brand) &
        (df["original_price"] > 0) &
        (df["discount_price"] > 0)
    ].copy()
    if df.empty:
        return pd.DataFrame()
    df["할인율 (%)"] = (
        (df["original_price"] - df["discount_price"]) / df["original_price"] * 100
    ).clip(0, 100)
    # 5% 구간 집계 — scatter 가독성 및 추세선 안정성 확보
    df["구간"] = (df["할인율 (%)"] // 5 * 5).round(0)
    agg = df.groupby("구간").agg(
        평균_평점=("rating", "mean"),
        리뷰_수=("rating", "count"),
    ).reset_index()
    agg.columns = ["할인율 (%)", "평균 평점", "리뷰 수"]
    agg["평균 평점"] = agg["평균 평점"].round(2)
    return agg


@st.cache_data(ttl=CACHE_TTL)
def _engagement_df() -> pd.DataFrame:
    df = get_reviews(columns=("brand", "has_image", "helpful_count", "is_new"))
    df = df.copy()
    df["is_new_bool"] = df["is_new"].isin(["True", "1.0"]).astype(int)
    rows = []
    for brand in BRAND_ORDER:
        sub = df[df["brand"] == brand]
        if sub.empty:
            continue
        photo_ratio = float(sub["has_image"].mean())
        helpful_avg = float(sub["helpful_count"].mean())
        new_sub = sub[sub["is_new_bool"] == 1]
        new_photo = float(new_sub["has_image"].mean()) if len(new_sub) > 0 else 0.0
        rows.append({
            "브랜드":           BRANDS[brand]["label"],
            "brand_key":        brand,
            "포토 리뷰 비율":   round(photo_ratio, 4),
            "평균 도움이 돼요":  round(helpful_avg, 2),
            "신상품 포토 비율":  round(new_photo, 4),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=CACHE_TTL)
def _sku_review_counts_df(brand: str) -> pd.DataFrame:
    df = get_reviews(columns=("review_id", "brand", "product_id", "color_count"))
    df = df[(df["brand"] == brand) & (df["color_count"] > 0)]
    if df.empty:
        return pd.DataFrame()
    prod = df.groupby("product_id").agg(
        리뷰_수=("review_id", "count"),
        color_count=("color_count", "first"),
    ).reset_index()

    def _bucket(c: float) -> str:
        if c <= 1:  return "1가지"
        if c <= 3:  return "2~3가지"
        if c <= 6:  return "4~6가지"
        if c <= 10: return "7~10가지"
        return "11가지 이상"

    prod["색상 수 구간"] = prod["color_count"].apply(_bucket)
    return prod[["색상 수 구간", "리뷰_수"]].rename(columns={"리뷰_수": "리뷰 수"})


@st.cache_data(ttl=CACHE_TTL)
def _color_freq_df(brand: str) -> pd.DataFrame:
    df = get_reviews(columns=("brand", "purchase_option_color"))
    df = df[(df["brand"] == brand) & (df["purchase_option_color"] != "unknown")]
    if df.empty:
        return pd.DataFrame()
    # 복합색(쉼표 구분) → 첫 번째 색상만 사용
    colors = df["purchase_option_color"].str.split(",").str[0].str.strip()
    counts = colors.value_counts().head(10).reset_index()
    counts.columns = ["컬러", "언급 수"]
    return counts


@st.cache_data(ttl=CACHE_TTL)
def _quadrant_df() -> pd.DataFrame:
    df = get_reviews(columns=("review_id", "brand", "cat1", "rating"))
    df = df[df["cat1"].notna() & (df["cat1"] != "")]
    if df.empty:
        return pd.DataFrame()
    agg = df.groupby(["brand", "cat1"]).agg(
        리뷰수=("review_id", "count"),
        평균평점=("rating", "mean"),
    ).reset_index()
    agg.columns = ["brand_key", "카테고리", "리뷰 수", "평균 평점"]
    agg["브랜드"] = agg["brand_key"].map(lambda b: BRANDS[b]["label"])
    agg["평균 평점"] = agg["평균 평점"].round(2)
    return agg


# ─────────────────────────────────────────────────────────────
# 1. 체형별 만족도 Heatmap
# ─────────────────────────────────────────────────────────────
st.subheader("체형별 만족도")
st.caption("키·몸무게 구간별 평균 평점 — 사이즈 사각지대(White Space) 및 핵심 체형 타겟 탐색")

sel_brand_body = st.selectbox(
    "브랜드 선택",
    options=active_brands,
    format_func=lambda b: BRANDS[b]["label"],
    key="body_brand_sel",
)
with safe_block("체형 Heatmap"):
    body_df = _body_heatmap_df(sel_brand_body)
    if body_df.empty:
        empty_state("체형 데이터 없음", "user_height_group / user_weight_group 값 확인 필요")
    else:
        pivot = body_df.pivot_table(
            index="몸무게 구간", columns="키 구간",
            values="평균 평점", aggfunc="mean",
        )
        # 첫 번째 숫자 기준 정렬 ("139cm 이하", "140~144cm", "190cm 이상" 등 모든 형식 대응)
        def _first_num(s: str) -> int:
            m = re.search(r"\d+", s)
            return int(m.group()) if m else 0

        height_order = sorted(pivot.columns.tolist(), key=_first_num)
        weight_order = sorted(pivot.index.tolist(), key=_first_num)
        pivot = pivot.reindex(index=weight_order, columns=height_order)
        fig_body = px.imshow(
            pivot,
            color_continuous_scale="RdYlGn",
            zmin=1, zmax=5,
            aspect="auto",
            text_auto=".2f",
            labels=dict(color="평균 평점", x="키 구간", y="몸무게 구간"),
            title=f"{BRANDS[sel_brand_body]['label']} — 체형별 평균 평점",
        )
        fig_body.update_layout(height=420)
        st.plotly_chart(fig_body, use_container_width=True)
        st.caption(f"집계 기준: {len(body_df):,}개 체형 셀 / unknown 제외")

st.divider()

# ─────────────────────────────────────────────────────────────
# 2. 가격 탄력성 Scatter (X: 할인율%)
# ─────────────────────────────────────────────────────────────
st.subheader("가격 탄력성")
st.caption(
    "할인율(%) vs 평균 평점 — 룰루레몬(노세일)과 국내 브랜드(상시 할인) 간 "
    "프리미엄 방어력 및 최적 프로모션 강도 비교"
)

with safe_block("가격 탄력성 Scatter"):
    pe_cols = st.columns(len(active_brands))
    for col, brand in zip(pe_cols, active_brands):
        with col:
            pe_df = _price_elasticity_df(brand)
            if pe_df.empty:
                empty_state(f"{BRANDS[brand]['label']} 데이터 없음")
            else:
                fig_pe = px.scatter(
                    pe_df,
                    x="할인율 (%)", y="평균 평점",
                    size="리뷰 수",
                    color_discrete_sequence=[BRANDS[brand]["color"]],
                    opacity=0.70,
                    trendline="lowess",
                    labels={"할인율 (%)": "할인율 (%)", "평균 평점": "평점"},
                    title=BRANDS[brand]["label"],
                )
                fig_pe.update_layout(height=340, showlegend=False)
                st.plotly_chart(fig_pe, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────────────────────
# 3. 고관여 고객 인게이지먼트
# ─────────────────────────────────────────────────────────────
st.subheader("고관여 고객 인게이지먼트")
st.caption(
    "포토 리뷰 비율(has_image) · 평균 도움이 돼요(helpful_count) · 신상품 출시 포토 비율(is_new) "
    "— 브랜드별 팬덤 화력 및 UGC 질 비교"
)

with safe_block("인게이지먼트"):
    eng_df = _engagement_df()
    if eng_df.empty:
        empty_state("인게이지먼트 데이터 없음")
    else:
        e1, e2, e3 = st.columns(3)

        with e1:
            fig_e1 = px.bar(
                eng_df,
                x="브랜드", y="포토 리뷰 비율",
                color="brand_key",
                color_discrete_map=_CMAP,
                title="포토 리뷰 비율 (has_image)",
                labels={"포토 리뷰 비율": "비율"},
                text=eng_df["포토 리뷰 비율"].apply(lambda x: f"{x:.1%}"),
            )
            y_max = max(eng_df["포토 리뷰 비율"].max() * 1.2, 0.1)
            fig_e1.update_layout(height=360, showlegend=False, yaxis_tickformat=".0%", yaxis_range=[0, y_max])
            fig_e1.update_traces(textposition="outside")
            st.plotly_chart(fig_e1, use_container_width=True)

        with e2:
            fig_e2 = px.bar(
                eng_df,
                x="브랜드", y="평균 도움이 돼요",
                color="brand_key",
                color_discrete_map=_CMAP,
                title="평균 도움이 돼요 (helpful_count)",
                labels={"평균 도움이 돼요": "평균 수"},
                text=eng_df["평균 도움이 돼요"].apply(lambda x: f"{x:.2f}"),
            )
            y_max2 = max(eng_df["평균 도움이 돼요"].max() * 1.3, 0.5)
            fig_e2.update_layout(height=360, showlegend=False, yaxis_range=[0, y_max2])
            fig_e2.update_traces(textposition="outside")
            st.plotly_chart(fig_e2, use_container_width=True)

        with e3:
            fig_e3 = px.bar(
                eng_df,
                x="브랜드", y="신상품 포토 비율",
                color="brand_key",
                color_discrete_map=_CMAP,
                title="신상품 출시 포토 비율 (is_new=True)",
                labels={"신상품 포토 비율": "비율"},
                text=eng_df["신상품 포토 비율"].apply(lambda x: f"{x:.1%}"),
            )
            y_max3 = max(eng_df["신상품 포토 비율"].max() * 1.2, 0.1)
            fig_e3.update_layout(height=360, showlegend=False, yaxis_tickformat=".0%", yaxis_range=[0, y_max3])
            fig_e3.update_traces(textposition="outside")
            st.plotly_chart(fig_e3, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────────────────────
# 4. SKU 복잡도 — 색상 수 구간 x 리뷰 수 Box Plot
# ─────────────────────────────────────────────────────────────
st.subheader("SKU 복잡도 분석")
st.caption("색상 수 구간별 리뷰 수 분포 — 컬러 라인업 확장이 판매 성과에 미치는 영향")

with safe_block("SKU Box Plot"):
    sku_cols = st.columns(len(active_brands))
    _sku_order = ["1가지", "2~3가지", "4~6가지", "7~10가지", "11가지 이상"]
    for col, brand in zip(sku_cols, active_brands):
        with col:
            sku_df = _sku_review_counts_df(brand)
            if sku_df.empty:
                empty_state(f"{BRANDS[brand]['label']} 데이터 없음")
            else:
                fig_sku = px.box(
                    sku_df,
                    x="색상 수 구간",
                    y="리뷰 수",
                    color_discrete_sequence=[BRANDS[brand]["color"]],
                    title=BRANDS[brand]["label"],
                    labels={"색상 수 구간": "컬러 수", "리뷰 수": "리뷰 수"},
                    category_orders={"색상 수 구간": _sku_order},
                )
                fig_sku.update_layout(height=340, showlegend=False)
                st.plotly_chart(fig_sku, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────────────────────
# 5. 컬러 빈도 분석
# ─────────────────────────────────────────────────────────────
st.subheader("컬러 빈도 분석")
st.caption(
    "구매 옵션 컬러(purchase_option_color) 언급 빈도 Top 10 "
    "— 브랜드별 주력 컬러 팔레트 파악 및 휠라 초기 컬러 전략 수립"
)

with safe_block("컬러 Bar"):
    cf_cols = st.columns(len(active_brands))
    for col, brand in zip(cf_cols, active_brands):
        with col:
            cf_df = _color_freq_df(brand)
            if cf_df.empty:
                empty_state(f"{BRANDS[brand]['label']} 데이터 없음")
            else:
                fig_cf = px.bar(
                    cf_df.sort_values("언급 수"),
                    x="언급 수", y="컬러", orientation="h",
                    title=BRANDS[brand]["label"],
                    color_discrete_sequence=[BRANDS[brand]["color"]],
                    labels={"언급 수": "언급 수", "컬러": ""},
                )
                fig_cf.update_layout(height=380, showlegend=False)
                st.plotly_chart(fig_cf, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────────────────────
# 6. 리뷰 볼륨 x 평점 사분면
# ─────────────────────────────────────────────────────────────
st.subheader("리뷰 볼륨 x 평점 사분면")
st.caption(
    "브랜드 x 카테고리별 리뷰 수(볼륨) vs 평균 평점(만족도) "
    "— 고성장·고만족 카테고리 탐색 및 휠라 진입 기회 영역 식별"
)

with safe_block("사분면 Scatter"):
    quad_df = _quadrant_df()
    if quad_df.empty:
        empty_state("사분면 데이터 없음")
    else:
        # active_brands 필터 적용
        quad_df = quad_df[quad_df["brand_key"].isin(active_brands)]
        med_x = float(quad_df["리뷰 수"].median())
        med_y = float(quad_df["평균 평점"].median())

        fig_q = px.scatter(
            quad_df,
            x="리뷰 수", y="평균 평점",
            color="브랜드",
            color_discrete_map={BRANDS[b]["label"]: BRANDS[b]["color"] for b in BRAND_ORDER},
            text="카테고리",
            labels={"리뷰 수": "리뷰 수 (볼륨)", "평균 평점": "평균 평점 (만족도)"},
            title="브랜드 x 카테고리 — 리뷰 볼륨 vs 평점",
            hover_data={"브랜드": True, "카테고리": True, "리뷰 수": True, "평균 평점": True},
        )
        fig_q.add_hline(y=med_y, line_dash="dot", line_color="gray", opacity=0.5)
        fig_q.add_vline(x=med_x, line_dash="dot", line_color="gray", opacity=0.5)
        fig_q.update_traces(textposition="top center", textfont_size=10, marker_size=12)
        fig_q.update_layout(height=540, hovermode="closest")
        st.plotly_chart(fig_q, use_container_width=True)
