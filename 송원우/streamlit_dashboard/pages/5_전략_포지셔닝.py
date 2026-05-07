"""
5_전략_포지셔닝.py — 핵심 산출물 (포지셔닝 맵 + White Space)
=============================================================
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, BRANDS, BRAND_ORDER, PATHS
from utils.data_loader import (
    get_positioning, get_sna, compute_aspect_polarity, get_topic_meta,
)
from utils.session import init_session, mark_page_visited
from utils.exceptions import safe_block, warn_using_dummy, empty_state
from components.filters import render_sidebar_filters
from components.positioning_map import render_positioning_map
from components.charts import keyword_centrality_bar


st.set_page_config(page_title=f"{APP_TITLE} — 포지셔닝", page_icon=None, **PAGE_LAYOUT)
init_session()
mark_page_visited("positioning")

st.title("5. 전략 포지셔닝")
st.caption("최종 산출 — 휠라의 의류 시장 진입 좌표")

if not PATHS["positioning"].exists():
    warn_using_dummy("포지셔닝 좌표 (ABSA에서 즉석 산출 중)")

render_sidebar_filters()

# ── 데이터 ─────────────────────────────────────────────────
with safe_block("포지셔닝 데이터 로드"):
    pos        = get_positioning()
    polarity   = compute_aspect_polarity()
    topic_meta = get_topic_meta()

if pos.empty:
    empty_state("포지셔닝 산출 불가", "ABSA 결과가 도착하면 자동 계산")
    st.stop()

# ── 시뮬레이터 슬라이더 ────────────────────────────────────
st.subheader("휠라 권장 포지셔닝 시뮬레이터")
ctl = st.columns([1, 1, 2])
with ctl[0]:
    target_x = st.slider("목표 기능성", 0.0, 1.0, 0.70, 0.05,
                         help="휠라가 도달해야 할 기능성 점수")
with ctl[1]:
    target_y = st.slider("목표 헤리티지", 0.0, 1.0, 0.75, 0.05,
                         help="신발 헤리티지를 의류로 전이한 후 목표 점수")
with ctl[2]:
    show_ci = st.toggle("신뢰구간 표시", value=True)
    show_q  = st.toggle("사분면 표시",   value=True)

# ── 포지셔닝 맵 ────────────────────────────────────────────
with safe_block("포지셔닝 맵"):
    fig = render_positioning_map(
        pos_df=pos,
        polarity_df=polarity,
        topic_meta=topic_meta,
        show_ci=show_ci,
        show_quadrants=show_q,
        target_position=(target_x, target_y),
        height=680,
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 좌표 테이블 ────────────────────────────────────────────
st.subheader("브랜드 좌표 / 신뢰구간")
df_view = pos[["brand", "x_function", "y_heritage", "n_reviews"]].copy()
df_view.columns = ["브랜드", "기능성", "헤리티지", "리뷰 수"]
df_view["기능성"]   = df_view["기능성"].round(3)
df_view["헤리티지"] = df_view["헤리티지"].round(3)
st.dataframe(df_view, use_container_width=True, hide_index=True)

st.divider()

# ── SNA 키워드 ─────────────────────────────────────────────
st.subheader("브랜드별 핵심 키워드 (SNA 중심성)")
sna = get_sna()
if not sna.empty:
    cols_sna = st.columns(2)
    for i, brand in enumerate(BRAND_ORDER):
        with cols_sna[i % 2]:
            with safe_block(f"{brand} SNA"):
                st.plotly_chart(
                    keyword_centrality_bar(sna, brand, top_n=12),
                    use_container_width=True,
                )
else:
    empty_state("SNA 결과 없음")

st.divider()

# ── White Space 전략 카드 ──────────────────────────────────
st.subheader("White Space — 휠라 전략 옵션")
opt = st.columns(3)
strategies = [
    {
        "title": "Option A. 헤리티지 프리미엄",
        "color": "#7B68EE",
        "x": 0.45, "y": 0.85,
        "desc": "신발 헤리티지를 그대로 의류로 전이. 디자인·브랜드 충성도에서 룰루레몬과 직접 경쟁.",
        "risk": "기능성 약점 미해결 시 재구매율 저하",
    },
    {
        "title": "Option B. Holistic Leader",
        "color": "#FFD700",
        "x": 0.70, "y": 0.75,
        "desc": "기능성·헤리티지 동시 강화. 룰루레몬과 정면 경쟁 (현실적 목표).",
        "risk": "기능성 R&D 투자 필요 — 1~2년 시간 소요",
    },
    {
        "title": "Option C. 기능 우선 진입",
        "color": "#4CAF50",
        "x": 0.80, "y": 0.40,
        "desc": "젝시믹스/안다르 시장에 가격·기능 경쟁으로 진입. 빠른 시장 점유 확대.",
        "risk": "헤리티지 자산 활용 부족 — 차별화 약함",
    },
]
for col, s in zip(opt, strategies):
    with col:
        st.markdown(
            f"""<div style='border: 1px solid {s['color']}; border-radius:6px;
            padding:14px; height:100%; background:#1a1a2e22;'>
                <div style='color:{s['color']}; font-weight:700; font-size:15px;'>{s['title']}</div>
                <div style='font-size:11px; color:#aaa; margin-top:4px;'>좌표 ({s['x']:.2f}, {s['y']:.2f})</div>
                <p style='font-size:13px; margin-top:10px;'>{s['desc']}</p>
                <div style='font-size:11px; color:#ff7777; margin-top:8px;'>리스크: {s['risk']}</div>
            </div>""",
            unsafe_allow_html=True,
        )
