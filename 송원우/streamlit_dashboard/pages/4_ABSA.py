"""
4_ABSA.py — 브랜드 속성 평가 (EXAONE ABSA 6속성)
=================================================
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, BRAND_ORDER, BRANDS, PATHS, ASPECT_LABELS
from utils.data_loader import (
    get_reviews, get_absa, compute_aspect_polarity, filters_to_hash, apply_filters,
)
from utils.session import init_session, get_filters, mark_page_visited
from utils.exceptions import safe_block, empty_state, warn_using_dummy
from components.filters import render_sidebar_filters
from components.charts import aspect_polarity_grouped_bar, aspect_polarity_diverging_bar


st.set_page_config(page_title=f"{APP_TITLE} — ABSA", page_icon=None, **PAGE_LAYOUT)
init_session()
mark_page_visited("absa")

st.title("4. ABSA")
st.caption("EXAONE 3.5 기반 6속성 P/N/X 분석 결과")

if not PATHS["absa"].exists():
    warn_using_dummy("ABSA 감성 분석")

render_sidebar_filters()
filters = get_filters()
fh = filters_to_hash(filters)

# ── 데이터 ─────────────────────────────────────────────────
with safe_block("ABSA 데이터 로드"):
    polarity = compute_aspect_polarity(filters_hash=fh)

if polarity.empty:
    empty_state("ABSA 결과 없음", "EXAONE 추론 완료 후 자동 갱신")
    st.stop()

# ── 행 1: 브랜드 x 6속성 그룹 막대 ──────────────────────────
st.subheader("브랜드 x 6속성 긍정(P) 비율")
with safe_block("그룹 막대"):
    st.plotly_chart(aspect_polarity_grouped_bar(polarity), use_container_width=True)
st.caption("호버 시 N(부정), X(없음) 비율 및 표본 수 확인 가능")

st.divider()

# ── 행 2: 브랜드 선택 → 발산 막대 ───────────────────────────
st.subheader("브랜드 강·약점 발산 분석")
sel_brand = st.radio(
    "브랜드 선택",
    options=[b for b in BRAND_ORDER if b in polarity["brand"].unique()],
    format_func=lambda b: BRANDS[b]["label"],
    horizontal=True,
)
with safe_block("발산 막대"):
    st.plotly_chart(aspect_polarity_diverging_bar(polarity, sel_brand), use_container_width=True)

st.divider()

# ── 행 3: 강점·약점 Top3 카드 ────────────────────────────────
st.subheader("브랜드별 강점·약점 Top3")
active_brands = [b for b in BRAND_ORDER if b in polarity["brand"].unique()]
cols = st.columns(len(active_brands))
for col, brand in zip(cols, active_brands):
    sub   = polarity[polarity["brand"] == brand]
    top_p = sub.nlargest(3, "P_ratio")
    top_n = sub.nlargest(3, "N_ratio")
    color = BRANDS[brand]["color"]
    with col:
        st.markdown(
            f"<div style='border-top: 4px solid {color}; padding-top:8px;'>"
            f"<h4 style='margin:0;'>{BRANDS[brand]['label']}</h4></div>",
            unsafe_allow_html=True,
        )
        st.markdown("**강점**")
        for _, r in top_p.iterrows():
            st.markdown(f"- {ASPECT_LABELS[r['aspect']]} `{r['P_ratio']:.1%}`")
        st.markdown("**약점**")
        for _, r in top_n.iterrows():
            st.markdown(f"- {ASPECT_LABELS[r['aspect']]} `{r['N_ratio']:.1%}`")

# ── 원시 데이터 ──────────────────────────────────────────────
with st.expander("ABSA 집계 원시 데이터"):
    df_view = polarity.copy()
    df_view["aspect"] = df_view["aspect"].map(ASPECT_LABELS)
    for c in ["P_ratio", "N_ratio", "X_ratio"]:
        df_view[c] = (df_view[c] * 100).round(1).astype(str) + "%"
    st.dataframe(df_view, use_container_width=True)
