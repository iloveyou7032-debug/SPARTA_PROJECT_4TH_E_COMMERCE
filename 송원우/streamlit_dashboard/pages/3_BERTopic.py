"""
3_BERTopic.py — 고객의 목소리 (BERTopic 토픽 모델링)
=====================================================
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, PATHS
from utils.data_loader import (
    get_reviews, get_topics, get_topic_meta, filters_to_hash, apply_filters,
)
from utils.session import init_session, get_filters, mark_page_visited
from utils.exceptions import safe_block, empty_state, warn_using_dummy
from components.filters import render_sidebar_filters
from components.charts import topic_keyword_treemap


st.set_page_config(page_title=f"{APP_TITLE} — BERTopic", page_icon=None, **PAGE_LAYOUT)
init_session()
mark_page_visited("voc")

st.title("3. BERTopic")
st.caption("117만 건 리뷰에서 자동 추출된 핵심 토픽")

if not PATHS["topics"].exists():
    warn_using_dummy("BERTopic 토픽 모델링")

render_sidebar_filters()
filters = get_filters()
fh = filters_to_hash(filters)

with safe_block("토픽/리뷰 로드"):
    reviews = get_reviews(columns=("review_id", "brand", "cat1", "rating", "year"))
    topics  = get_topics()
    meta    = get_topic_meta()

if topics.empty or meta.empty:
    empty_state("토픽 데이터 부재", "BERTopic 산출 후 자동 표시됩니다.")
    st.stop()

reviews_f = apply_filters(reviews, filters)
topics_f  = topics[topics["review_id"].isin(reviews_f["review_id"])]

# ── 행 1: 토픽 트리맵 + 토픽 카드 ────────────────────────────
col_a, col_b = st.columns([2, 1])
with col_a:
    with safe_block("토픽 트리맵"):
        m = topics_f.groupby("topic_id").size().rename("n_reviews_filtered").reset_index()
        meta_view = meta.merge(m, on="topic_id", how="left")
        meta_view["n_reviews"] = meta_view["n_reviews_filtered"].fillna(0).astype(int)
        st.plotly_chart(topic_keyword_treemap(meta_view), use_container_width=True)

with col_b:
    st.markdown("##### 토픽 카드")
    for _, row in meta_view.sort_values("n_reviews", ascending=False).head(8).iterrows():
        kws = ", ".join(row["keywords"][:6]) if isinstance(row["keywords"], list) else ""
        st.markdown(
            f"""<div style='border-left: 3px solid #4cc9f0; padding: 8px 12px; margin-bottom:8px;
                background:#1f1f2e22; border-radius:3px;'>
                <div style='font-weight:600;'>{row['topic_name']}</div>
                <div style='font-size:11px; color:#888;'>{int(row['n_reviews']):,} 리뷰 · {row.get('axis_hint','-')}</div>
                <div style='font-size:12px; margin-top:4px;'>{kws}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.divider()

# ── 행 2: 브랜드 x 토픽 히트맵 ──────────────────────────────
st.subheader("브랜드 x 토픽 분포")
with safe_block("브랜드 토픽 히트맵"):
    merged = topics_f.merge(reviews_f[["review_id", "brand"]], on="review_id", how="inner")
    if merged.empty:
        empty_state("매칭 결과 없음")
    else:
        ct = merged.pivot_table(
            index="topic_name", columns="brand",
            values="review_id", aggfunc="count", fill_value=0,
        )
        ct_norm = ct.div(ct.sum(axis=1), axis=0)
        fig = px.imshow(
            ct_norm,
            color_continuous_scale="Viridis",
            aspect="auto",
            labels=dict(color="비율"),
            title="토픽별 브랜드 점유율 (행 정규화)",
        )
        fig.update_layout(height=460)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── 행 3: 토픽 드릴다운 ──────────────────────────────────────
st.subheader("토픽 드릴다운")
topic_options = meta_view.sort_values("n_reviews", ascending=False)["topic_name"].tolist()
selected_topic = st.selectbox("토픽 선택", topic_options)
if selected_topic:
    tid = meta_view[meta_view["topic_name"] == selected_topic]["topic_id"].iloc[0]
    sample_ids     = topics_f[topics_f["topic_id"] == tid].nlargest(20, "probability")["review_id"]
    sample_reviews = reviews_f[reviews_f["review_id"].isin(sample_ids)]
    if sample_reviews.empty:
        empty_state("필터된 리뷰가 없는 토픽입니다.")
    else:
        cols = [c for c in ["brand", "rating", "content_clean"] if c in sample_reviews.columns]
        st.dataframe(sample_reviews[cols].head(20), use_container_width=True)
