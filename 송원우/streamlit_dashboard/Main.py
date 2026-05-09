"""
app.py — FILA 애슬레저 대시보드 홈 (전체 요약 + 브랜드별 현황 통합)
====================================================================

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

from config import APP_TITLE, APP_SUBTITLE, PAGE_LAYOUT, BRAND_ORDER, BRANDS, ASPECT_LABELS
from utils.session import init_session
from utils.data_loader import get_reviews, compute_brand_kpis, compute_aspect_polarity
from utils.exceptions import safe_block
from components.kpi_cards import metric_grid
from components.brand_page import render_brand_page


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=None,
    **PAGE_LAYOUT,
)

css_path = APP_DIR / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

init_session()


# ─── 타이틀 ───────────────────────────────────────────────────
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)
st.markdown(
    "<p style='font-size:12px; color:#888; margin:2px 0 6px;'>"
    "📊 <strong>홈</strong> &nbsp;›&nbsp; 상품/고객 전략 &nbsp;›&nbsp; "
    "BERTopic &nbsp;›&nbsp; ABSA &nbsp;›&nbsp; 포지셔닝</p>",
    unsafe_allow_html=True,
)
st.divider()


# ─── 전체 시장 요약 KPI ────────────────────────────────────────
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


# ─── 핵심 인사이트 카드 (전략 hook) ─────────────────────────────
st.subheader("핵심 전략 인사이트")
with safe_block("인사이트 카드"):
    # 동적 인사이트 1: FILA 리뷰 점유율 vs 평점 위치
    fila_rating_card = "데이터 부족"
    fila_rating_desc = "—"
    if not kpi.empty:
        fila_row = kpi[kpi["brand"] == "FILA"]
        if not fila_row.empty:
            fila_r = float(fila_row["mean_rating"].iloc[0])
            rating_rank = (kpi["mean_rating"] >= fila_r).sum()
            fila_rating_card = f"FILA 평점 {fila_r:.2f} (전체 중 {int(rating_rank)}위)"
            fila_rating_desc = (
                f"리뷰 점유율은 **{fila_share:.1%}**에 그치지만 평점은 상위권 — "
                "**브랜드 인지·노출 부족**이 1차 병목"
            )

    # 동적 인사이트 2: ABSA 기반 FILA 강·약점
    aspect_card = "ABSA 결과 부재"
    aspect_desc = "ABSA 산출 후 자동 갱신"
    try:
        polarity = compute_aspect_polarity(filters_hash="__all__")
        fila_pol = polarity[polarity["brand"] == "FILA"] if not polarity.empty else polarity
        if not fila_pol.empty:
            top_strength = fila_pol.nlargest(1, "P_ratio").iloc[0]
            top_weak     = fila_pol.nlargest(1, "N_ratio").iloc[0]
            s_label = ASPECT_LABELS.get(top_strength["aspect"], top_strength["aspect"])
            w_label = ASPECT_LABELS.get(top_weak["aspect"], top_weak["aspect"])
            aspect_card = f"강점 {s_label} / 약점 {w_label}"
            aspect_desc = (
                f"**{s_label}** 긍정 {top_strength['P_ratio']:.0%} vs "
                f"**{w_label}** 부정 {top_weak['N_ratio']:.0%} — "
                "의류 확장 시 약점 속성 우선 보강 필요"
            )
    except Exception:
        pass

    # 정적 인사이트 3 (사업 가설 — 검증 후 dynamic 전환 예정)
    expansion_card = "신발 헤리티지 → 의류 전이"
    expansion_desc = (
        "FILA 신발 자산은 **레트로·헤리티지 강점**, 의류 시장은 "
        "**기능성·소재 신뢰**가 핵심 — 두 축의 교차점에 White Space 존재"
    )

    insight_cols = st.columns(3)
    cards = [
        ("📊 시장 위치",     fila_rating_card,  fila_rating_desc,   "#003087"),
        ("🎯 속성 강·약점",  aspect_card,       aspect_desc,        "#D4000F"),
        ("🚀 전략 가설",     expansion_card,    expansion_desc,     "#7B68EE"),
    ]
    for col, (icon_title, headline, desc, color) in zip(insight_cols, cards):
        with col:
            st.markdown(
                f"""<div style='border-top: 4px solid {color}; padding: 12px 14px;
                background: {color}11; border-radius: 4px; height: 100%;'>
                    <div style='font-size: 12px; color: {color}; font-weight: 600;'>{icon_title}</div>
                    <div style='font-size: 16px; font-weight: 700; margin-top: 6px;'>{headline}</div>
                    <div style='font-size: 13px; margin-top: 8px; line-height: 1.5;'>{desc}</div>
                </div>""",
                unsafe_allow_html=True,
            )

st.divider()


# ─── 브랜드별 현황 테이블 ──────────────────────────────────────
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


# ─── 브랜드별 상세 분석 (P1 통합) ─────────────────────────────
render_brand_page(BRAND_ORDER[0])
