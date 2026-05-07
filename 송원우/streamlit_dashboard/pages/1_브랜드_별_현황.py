"""
1_브랜드_별_현황.py — 브랜드별 상세 현황 (4개 브랜드 통합 단일 페이지)
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, BRAND_ORDER
from utils.session import init_session
from components.brand_page import render_brand_page

st.set_page_config(
    page_title=f"{APP_TITLE} — 브랜드별 현황",
    page_icon=None,
    **PAGE_LAYOUT,
)
init_session()

render_brand_page(BRAND_ORDER[0])
