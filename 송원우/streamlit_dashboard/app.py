"""
app.py — FILA 애슬레저 대시보드 홈 (거시적 요약)
=================================================

홈 화면은 필터 없는 전체 데이터 개요만 표시.
필터 및 심화 분석은 각 브랜드/분석 페이지에서 진행.

실행:
    uv run streamlit run 송원우/streamlit_dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config import APP_TITLE, APP_SUBTITLE, PAGE_LAYOUT, PATHS, BRAND_ORDER, BRANDS
from utils.session import init_session
from utils.data_loader import get_reviews, compute_brand_kpis
from utils.exceptions import data_health_check, safe_block
from components.kpi_cards import metric_grid


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=None,
    **PAGE_LAYOUT,
)

# 커스텀 CSS
css_path = APP_DIR / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

init_session()


# ─────────────────────────────────────────────────────────────
# 타이틀
# ─────────────────────────────────────────────────────────────
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)
st.divider()


# ─────────────────────────────────────────────────────────────
# 데이터 산출물 상태
# ─────────────────────────────────────────────────────────────
st.subheader("데이터 산출물 상태")
with safe_block("헬스체크"):
    health_df = data_health_check(PATHS)
    st.dataframe(health_df, use_container_width=True, hide_index=True)
    n_dummy = (health_df["존재"] == "🟡 더미").sum()
    if n_dummy > 0:
        st.info(
            f"{n_dummy}개 산출물이 더미 모드 동작 중 — "
            "`송원우/final_data/` 에 실제 Parquet 파일이 도착하면 자동 전환됩니다."
        )

st.divider()


# ─────────────────────────────────────────────────────────────
# 전체 시장 요약 KPI
# ─────────────────────────────────────────────────────────────
st.subheader("전체 시장 요약")
with safe_block("전체 KPI"):
    reviews = get_reviews(columns=("review_id", "brand", "rating", "year"))
    kpi = compute_brand_kpis(filters_hash="__all__")

    if not kpi.empty and not reviews.empty:
        total_reviews = int(kpi["n_reviews"].sum())
        avg_rating    = float(
            (kpi["mean_rating"] * kpi["n_reviews"]).sum() / kpi["n_reviews"].sum()
        )
        n_brands  = len(kpi)
        year_min  = int(reviews["year"].min())
        year_max  = int(reviews["year"].max())
        fila_mask = kpi["brand"] == "FILA"
        fila_share = (
            float(kpi[fila_mask]["n_reviews"].iloc[0] / total_reviews)
            if fila_mask.any() else 0.0
        )

        metric_grid([
            {"label": "전체 리뷰 수",   "value": f"{total_reviews:,}",    "help": "전 브랜드 합계"},
            {"label": "데이터 기간",    "value": f"{year_min}~{year_max}", "help": "review_date 기준"},
            {"label": "평균 평점",      "value": f"{avg_rating:.2f}",      "help": "리뷰 수 가중 평균"},
            {"label": "브랜드 수",      "value": str(n_brands),            "help": "분석 대상 브랜드"},
            {"label": "휠라 리뷰 비중", "value": f"{fila_share:.1%}",      "help": "리뷰 수 기준 점유율"},
        ], cols=5)

st.divider()


# ─────────────────────────────────────────────────────────────
# 브랜드별 현황 테이블
# ─────────────────────────────────────────────────────────────
st.subheader("브랜드별 데이터 현황")
with safe_block("브랜드 테이블"):
    if not kpi.empty:
        view = kpi.copy()
        view["점유율"] = (view["n_reviews"] / view["n_reviews"].sum() * 100).round(1).astype(str) + "%"
        view["mean_rating"] = view["mean_rating"].map("{:.2f}".format)
        view["rating_std"]  = view["rating_std"].map("{:.2f}".format)
        view.columns = ["브랜드", "리뷰 수", "평균 평점", "평점 표준편차", "점유율"]
        st.dataframe(view, use_container_width=True, hide_index=True)

st.divider()

# ─────────────────────────────────────────────────────────────
# 브랜드별 상세 분석 바로가기
# ─────────────────────────────────────────────────────────────
st.subheader("브랜드별 상세 분석 바로가기")
btn_cols = st.columns(4)
for col, brand in zip(btn_cols, BRAND_ORDER):
    with col:
        if st.button(
            BRANDS[brand]["label"],
            use_container_width=True,
            key=f"nav_{brand}",
            type="secondary",
        ):
            st.session_state.brands = brand
            st.switch_page("pages/1_브랜드_별_현황.py")
