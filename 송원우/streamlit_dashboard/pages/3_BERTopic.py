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

st.title("BERTopic")
st.caption("117만 건 리뷰에서 자동 추출된 핵심 토픽")
st.markdown(
    "<p style='font-size:12px; color:#888; margin:2px 0 2px;'>"
    "📊 홈 &nbsp;›&nbsp; 상품/고객 전략 &nbsp;›&nbsp; <strong>BERTopic</strong> "
    "&nbsp;›&nbsp; ABSA &nbsp;›&nbsp; 포지셔닝</p>",
    unsafe_allow_html=True,
)
st.caption("상품/고객 전략의 카테고리·가격 분포에서 포착된 패턴을 실제 리뷰 토픽 군집으로 검증합니다.")

if not PATHS["topics"].exists():
    warn_using_dummy("BERTopic 토픽 모델링")

render_sidebar_filters()
filters = get_filters()
fh = filters_to_hash(filters)

with safe_block("토픽/리뷰 로드"):
    reviews = get_reviews(columns=(
        "review_id", "brand", "cat1", "rating", "year",
        "review_date", "product_name", "content_clean",
    ))
    topics  = get_topics()
    meta    = get_topic_meta()

if topics.empty or meta.empty:
    empty_state("토픽 데이터 부재", "BERTopic 산출 후 자동 표시됩니다.")
    st.stop()

# BERTopic 네이티브 컬럼 정규화: 'Topic'(BERTopic 표준) 또는 'topic'(우리 parquet) → 'topic_id'
for _old in ("Topic", "topic"):
    if "topic_id" not in topics.columns and _old in topics.columns:
        topics = topics.rename(columns={_old: "topic_id"})
        break

reviews_f = apply_filters(reviews, filters)
if "review_id" in topics.columns:
    topics_f = topics[topics["review_id"].isin(reviews_f["review_id"])]
else:
    topics_f = topics.copy()

# meta_view는 col_a·col_b 모두에서 참조하므로 분기 전에 계산
with safe_block("meta_view 산출"):
    if "topic_id" in topics_f.columns:
        m = topics_f.groupby("topic_id").size().rename("n_reviews_filtered").reset_index()
        meta_view = meta.merge(m, on="topic_id", how="left")
    else:
        meta_view = meta.copy()
        meta_view["n_reviews_filtered"] = 0
    meta_view["n_reviews"] = meta_view["n_reviews_filtered"].fillna(0).astype(int)

# ── 행 1: 토픽 트리맵 + 토픽 카드 ────────────────────────────
col_a, col_b = st.columns([2, 1])
with col_a:
    with safe_block("토픽 트리맵"):
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

# ── 행 2: 브랜드 x 토픽 분포 (100% 누적 막대) ──────────────
st.subheader("브랜드 x 토픽 분포")
st.caption("두 가지 관점 — 토픽별 브랜드 점유율 / 브랜드별 토픽 비중")

from config import BRAND_COLORS, BRANDS

with safe_block("브랜드 토픽 분포"):
    # topics_f에 brand 컬럼이 있으면 병합 충돌(brand_x/brand_y)이 생기므로 먼저 제거
    _tf = topics_f.drop(columns=["brand"], errors="ignore")
    merged = _tf.merge(reviews_f[["review_id", "brand"]], on="review_id", how="inner")
    # pivot에 필요한 topic_name 확보
    if "topic_name" not in merged.columns and "topic_id" in merged.columns:
        merged = merged.merge(
            meta[["topic_id", "topic_name"]].drop_duplicates(), on="topic_id", how="left"
        )
    if merged.empty or "brand" not in merged.columns or "topic_name" not in merged.columns:
        empty_state("매칭 결과 없음")
    else:
        ct = merged.pivot_table(
            index="topic_name", columns="brand",
            values="review_id", aggfunc="count", fill_value=0,
        )

        view_mode = st.radio(
            "정규화 방향",
            ["토픽별 브랜드 점유율 (행 정규화)", "브랜드별 토픽 비중 (열 정규화)"],
            horizontal=True,
            key="topic_brand_norm_mode",
        )

        if view_mode.startswith("토픽별"):
            # 행 정규화: 한 토픽 안에서 어느 브랜드가 더 차지하는가
            ct_norm = ct.div(ct.sum(axis=1).replace(0, 1), axis=0)
            long_df = ct_norm.reset_index().melt(
                id_vars="topic_name", var_name="brand", value_name="ratio"
            )
            long_df["count"] = long_df.apply(
                lambda r: int(ct.loc[r["topic_name"], r["brand"]]), axis=1,
            )
            fig_bt = px.bar(
                long_df,
                x="topic_name", y="ratio", color="brand",
                color_discrete_map=BRAND_COLORS,
                labels={"topic_name": "토픽", "ratio": "비율", "brand": "브랜드"},
                title="토픽별 브랜드 점유율 (각 토픽 내 브랜드 분포)",
                hover_data={"count": ":,", "ratio": ":.1%"},
            )
            fig_bt.update_layout(barmode="stack", yaxis_tickformat=".0%", height=480,
                                 xaxis_tickangle=-30,
                                 legend=dict(orientation="h", y=-0.25))
        else:
            # 열 정규화: 한 브랜드 안에서 어느 토픽이 더 큰가
            ct_norm = ct.div(ct.sum(axis=0).replace(0, 1), axis=1)
            long_df = ct_norm.reset_index().melt(
                id_vars="topic_name", var_name="brand", value_name="ratio"
            )
            long_df["count"] = long_df.apply(
                lambda r: int(ct.loc[r["topic_name"], r["brand"]]), axis=1,
            )
            fig_bt = px.bar(
                long_df,
                x="brand", y="ratio", color="topic_name",
                labels={"brand": "브랜드", "ratio": "비율", "topic_name": "토픽"},
                title="브랜드별 토픽 비중 (각 브랜드 내 토픽 분포)",
                hover_data={"count": ":,", "ratio": ":.1%"},
            )
            fig_bt.update_layout(barmode="stack", yaxis_tickformat=".0%", height=480,
                                 legend=dict(orientation="h", y=-0.25))

        st.plotly_chart(fig_bt, use_container_width=True)

st.divider()

# ── 행 3: 토픽 드릴다운 ──────────────────────────────────────
st.subheader("토픽 드릴다운")
topic_options = meta_view.sort_values("n_reviews", ascending=False)["topic_name"].tolist()
selected_topic = st.selectbox("토픽 선택", topic_options)
if selected_topic and "topic_id" in topics_f.columns:
    tid = meta_view[meta_view["topic_name"] == selected_topic]["topic_id"].iloc[0]
    sub = topics_f[topics_f["topic_id"] == tid].copy()
    if "probability" in sub.columns:
        sub = sub.nlargest(20, "probability")
        prob_map = sub.set_index("review_id")["probability"].to_dict()
    else:
        sub = sub.head(20)
        prob_map = {}
    sample_ids     = sub["review_id"] if "review_id" in sub.columns else pd.Series(dtype="object")
    sample_reviews = reviews_f[reviews_f["review_id"].isin(sample_ids)].copy()
    if sample_reviews.empty:
        empty_state("필터된 리뷰가 없는 토픽입니다.")
    else:
        # 토픽 메타 정보 부착
        sample_reviews["토픽명"] = selected_topic
        if prob_map:
            sample_reviews["토픽 확률"] = sample_reviews["review_id"].map(prob_map).round(3)
        # 컬럼 순서 정렬: 작성일 → 브랜드 → 상품명 → 카테고리 → 평점 → 토픽명 → 토픽확률 → 본문
        col_order = []
        rename_map = {}
        for src, dst in [
            ("review_date",   "작성일"),
            ("brand",         "브랜드"),
            ("product_name",  "상품명"),
            ("cat1",          "카테고리"),
            ("rating",        "평점"),
            ("토픽명",        "토픽명"),
            ("토픽 확률",     "토픽 확률"),
            ("content_clean", "리뷰 원문"),
        ]:
            if src in sample_reviews.columns:
                col_order.append(src)
                rename_map[src] = dst
        view = sample_reviews[col_order].rename(columns=rename_map).head(20)
        st.caption(f"표시 컬럼: {', '.join(rename_map.values())} | 토픽 확률 내림차순 상위 20건")
        st.dataframe(view, use_container_width=True, hide_index=True)
elif selected_topic:
    empty_state("드릴다운 불가", "topic_id 컬럼이 없습니다.")
