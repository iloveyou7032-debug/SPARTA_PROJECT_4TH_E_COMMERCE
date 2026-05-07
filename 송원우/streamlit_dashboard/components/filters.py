"""
filters.py — 사이드바 필터 위젯
================================

모든 분석 페이지(P1~P7)가 공유하는 필터 UI.
session_state 에 직접 바인딩되며, 페이지 전환 후에도 선택값이 유지됨.

위젯 구성:
  · 브랜드       : multiselect
  · 연도 범위    : slider
  · 평점         : selectbox
  · 카테고리1    : checkbox (옵션 제공 시)
  · 카테고리2    : checkbox (옵션 제공 시)
  · 카테고리3    : checkbox (옵션 제공 시)
  · 가격 범위    : slider (min/max 제공 시)
"""
from __future__ import annotations

import streamlit as st

from config import BRAND_ORDER, BRANDS
from utils.session import filters_summary, reset_filters


def render_sidebar_filters(
    *,
    cat1_options: list[str] | None = None,
    cat2_options: list[str] | None = None,
    cat3_options: list[str] | None = None,
    price_min: int = 0,
    price_max: int = 500_000,
    lock_brand: str | None = None,       # 브랜드 페이지에서 해당 브랜드 고정 시 사용
) -> None:
    """사이드바 필터 렌더링. 분석 페이지 진입부에서 1회 호출."""

    sb = st.sidebar
    sb.markdown("### 필터")

    # ── 브랜드 ────────────────────────────────────────────────
    if lock_brand:
        sb.markdown(f"**브랜드**: {BRANDS[lock_brand]['label']}")
        st.session_state.brands = lock_brand   # 단일 문자열 유지
    else:
        # 분석 페이지: multiselect (session_state.brands가 string이면 list로 정규화)
        raw = st.session_state.brands
        current_list = [raw] if isinstance(raw, str) else (raw if raw else BRAND_ORDER)
        st.session_state.brands = current_list  # multiselect는 list여야 함
        sb.multiselect(
            "브랜드",
            options=BRAND_ORDER,
            default=current_list,
            key="brands",
            format_func=lambda b: BRANDS[b]["label"],
        )

    # ── 연도 범위 ─────────────────────────────────────────────
    sb.slider(
        "연도 범위",
        min_value=2022,
        max_value=2026,
        value=tuple(st.session_state.year_range),
        step=1,
        key="year_range",
    )

    # ── 평점 ──────────────────────────────────────────────────
    rating_options = ["전체", "1점", "2점", "3점", "4점", "5점"]
    current_rating = st.session_state.rating_sel
    if current_rating not in rating_options:
        current_rating = "전체"
    sb.selectbox(
        "평점",
        options=rating_options,
        index=rating_options.index(current_rating),
        key="rating_sel",
    )

    # ── 카테고리1 체크박스 ────────────────────────────────────
    if cat1_options:
        with sb.expander("카테고리1", expanded=False):
            new_cat1 = []
            for opt in cat1_options:
                cb_key = f"_cb_cat1_{opt}"
                if cb_key not in st.session_state:
                    st.session_state[cb_key] = (opt in st.session_state.cat1_filters)
                if st.checkbox(opt, key=cb_key):
                    new_cat1.append(opt)
            st.session_state.cat1_filters = new_cat1

    # ── 카테고리2 체크박스 ────────────────────────────────────
    if cat2_options:
        with sb.expander("카테고리2", expanded=False):
            new_cat2 = []
            for opt in cat2_options:
                cb_key = f"_cb_cat2_{opt}"
                if cb_key not in st.session_state:
                    st.session_state[cb_key] = (opt in st.session_state.cat2_filters)
                if st.checkbox(opt, key=cb_key):
                    new_cat2.append(opt)
            st.session_state.cat2_filters = new_cat2

    # ── 카테고리3 체크박스 ────────────────────────────────────
    if cat3_options:
        with sb.expander("카테고리3", expanded=False):
            new_cat3 = []
            for opt in cat3_options:
                cb_key = f"_cb_cat3_{opt}"
                if cb_key not in st.session_state:
                    st.session_state[cb_key] = (opt in st.session_state.cat3_filters)
                if st.checkbox(opt, key=cb_key):
                    new_cat3.append(opt)
            st.session_state.cat3_filters = new_cat3

    # ── 가격 범위 ─────────────────────────────────────────────
    if price_max > price_min:
        # 저장된 값이 현재 페이지 범위를 벗어나면 클램핑
        stored_lo, stored_hi = st.session_state.price_range
        clamped_lo = max(price_min, min(stored_lo, price_max))
        clamped_hi = min(price_max, max(stored_hi, price_min))
        if clamped_lo > clamped_hi:
            clamped_lo, clamped_hi = price_min, price_max
        if (clamped_lo, clamped_hi) != (stored_lo, stored_hi):
            st.session_state.price_range = (clamped_lo, clamped_hi)

        sb.slider(
            "가격 범위 (원)",
            min_value=price_min,
            max_value=price_max,
            value=tuple(st.session_state.price_range),
            step=5_000,
            format="%d원",
            key="price_range",
        )

    # ── 하단 요약 + 초기화 ────────────────────────────────────
    sb.divider()
    sb.caption(f"**적용 중**: {filters_summary()}")
    if sb.button("필터 초기화", use_container_width=True):
        reset_filters()
        st.rerun()
