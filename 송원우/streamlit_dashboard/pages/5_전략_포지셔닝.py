"""
5_전략_포지셔닝.py — 핵심 산출물 (포지셔닝 맵 + White Space)
=============================================================
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, BRANDS, BRAND_ORDER, PATHS, CACHE_TTL
from utils.data_loader import (
    get_positioning, get_sna, compute_aspect_polarity, get_topic_meta, get_reviews,
)
from utils.session import init_session, mark_page_visited
from utils.exceptions import safe_block, warn_using_dummy, empty_state
from components.filters import render_sidebar_filters
from components.positioning_map import render_positioning_map
from components.charts import keyword_centrality_bar


st.set_page_config(page_title=f"{APP_TITLE} — 포지셔닝", page_icon=None, **PAGE_LAYOUT)
init_session()
mark_page_visited("positioning")

st.title("전략 포지셔닝")
st.caption("최종 산출 — 휠라의 의류 시장 진입 좌표")
st.markdown(
    "<p style='font-size:12px; color:#888; margin:2px 0 2px;'>"
    "📊 홈 &nbsp;›&nbsp; 상품/고객 전략 &nbsp;›&nbsp; BERTopic &nbsp;›&nbsp; "
    "ABSA &nbsp;›&nbsp; <strong>포지셔닝</strong></p>",
    unsafe_allow_html=True,
)
st.caption("ABSA 속성 점수를 기능성 × 헤리티지 2축으로 압축하여 FILA의 의류 시장 진입 좌표를 확정합니다.")

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

# ── 좌표 산출법 ────────────────────────────────────────────
with st.expander("좌표 산출법 — 기능성/헤리티지 점수는 어떻게 계산되나요?"):
    st.markdown(
        """
**ABSA 6속성 중 2개 속성의 P/N 비율을 사용합니다.**

| 축 | 사용 속성 | 공식 |
|---|---|---|
| **기능성 (X)** | `functionality` | `polarity = (P_ratio − N_ratio) / (P_ratio + N_ratio)` → `x = 0.5 × (1 + polarity)` |
| **헤리티지 (Y)** | `brand_heritage` | 동일 공식, `brand_heritage` 속성으로 산출 |

- **0.5 = 중립** (긍정·부정 동률), **1.0 = 전 긍정**, **0.0 = 전 부정**
- minmax 정규화는 사용하지 않습니다 — 4브랜드 비교에서 항상 한 브랜드를 0/1로 강제하는 부작용 회피
- 해당 속성에서 ABSA 결과가 없는 브랜드는 **NaN("산출 불가")**로 처리하며 맵에 그리지 않습니다
- 신뢰구간(CI)은 ±0.05 고정 (실제 ABSA 부트스트랩 도착 시 교체 예정)

**보완 예정:** BERTopic 토픽 점유율(기능 토픽 vs 헤리티지 토픽) 가중치, SNA 키워드 중심성 반영
        """
    )

# ── 좌표 테이블 ────────────────────────────────────────────
st.subheader("브랜드 좌표")
df_view = pos[["brand", "x_function", "y_heritage", "n_reviews"]].copy()
df_view.columns = ["브랜드", "기능성", "헤리티지", "리뷰 수"]

# NaN → "산출 불가" 표시 (0으로 시각화 시 좌하단 오인 방지)
def _fmt_score(v):
    return "산출 불가" if pd.isna(v) else f"{v:.3f}"
df_view["기능성"]   = df_view["기능성"].apply(_fmt_score)
df_view["헤리티지"] = df_view["헤리티지"].apply(_fmt_score)
st.dataframe(df_view, use_container_width=True, hide_index=True)
na_brands = pos[pos["x_function"].isna() | pos["y_heritage"].isna()]["brand"].tolist()
if na_brands:
    st.caption(f"⚠ 산출 불가 브랜드: {', '.join(na_brands)} — 해당 속성에서 ABSA 결과 부재")

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

# ─────────────────────────────────────────────────────────────
# FILA 신발 × 의류 연결 분석 (PMI + 연결·매개 중심성)
# ─────────────────────────────────────────────────────────────
st.subheader("FILA 신발 → 의류 연결 분석 (PMI 기반 키워드 네트워크)")
st.caption(
    "FILA 리뷰 토큰에서 PMI(점별 상호정보량) 기반 의미 있는 단어쌍 추출 → "
    "연결 중심성(허브 단어)·매개 중심성(브릿지 단어) 계산"
)

# 신발/의류 시드 단어
_SHOE_SEEDS = {
    "신발", "운동화", "스니커즈", "슈즈", "깔창", "밑창", "굽", "인솔",
    "착화감", "발볼", "발등", "발목", "끈", "하이탑",
}
_APPAREL_SEEDS = {
    "레깅스", "티셔츠", "바지", "상의", "하의", "셔츠", "반팔", "긴팔",
    "조거", "재킷", "니트", "기모", "맨투맨", "원피스", "스커트", "반바지",
}


@st.cache_data(ttl=CACHE_TTL)
def _compute_pmi_centrality(
    top_vocab: int = 250,
    min_pair_count: int = 3,
    min_pmi: float = 0.5,
) -> pd.DataFrame:
    df = get_reviews(columns=("brand", "tokens"))
    fila = df[df["brand"] == "FILA"]["tokens"].dropna()

    docs = [str(t).split() for t in fila]

    word_counts: Counter = Counter(w for doc in docs for w in doc)
    total_words = sum(word_counts.values()) or 1

    vocab = {
        w for w, c in word_counts.most_common(top_vocab)
        if len(w) > 1 and not w.isdigit() and c >= min_pair_count
    }

    cooc: Counter = Counter()
    for doc in docs:
        words = [w for w in doc if w in vocab]
        for i, w1 in enumerate(words):
            for w2 in words[i + 1: i + 4]:
                if w1 != w2:
                    cooc[tuple(sorted([w1, w2]))] += 1

    total_cooc = sum(cooc.values()) or 1

    G = nx.Graph()
    for (w1, w2), c in cooc.items():
        if c < min_pair_count:
            continue
        pmi = (
            math.log2(c / total_cooc)
            - math.log2(word_counts[w1] / total_words)
            - math.log2(word_counts[w2] / total_words)
        )
        if pmi >= min_pmi:
            G.add_edge(w1, w2, weight=float(pmi), count=c)

    if len(G.nodes) < 3:
        return pd.DataFrame()

    degree_c  = nx.degree_centrality(G)
    # k 샘플링으로 대형 그래프 속도 개선 (노드 수 300 이하면 정확 계산)
    k_sample = None if len(G.nodes) <= 300 else 100
    between_c = nx.betweenness_centrality(G, normalized=True, k=k_sample)

    def _cat(w: str) -> str:
        if w in _SHOE_SEEDS:    return "신발"
        if w in _APPAREL_SEEDS: return "의류"
        return "공통"

    rows = [
        {
            "키워드":    node,
            "연결 중심성": round(degree_c.get(node, 0), 4),
            "매개 중심성": round(between_c.get(node, 0), 4),
            "빈도":      word_counts.get(node, 0),
            "카테고리":   _cat(node),
        }
        for node in G.nodes()
    ]
    return pd.DataFrame(rows)


with safe_block("PMI 파라미터"):
    pmi_c1, pmi_c2, pmi_c3 = st.columns(3)
    with pmi_c1:
        top_vocab_sel = st.slider("어휘 크기 (상위 N 단어)", 100, 400, 250, 50,
                                  key="pmi_vocab")
    with pmi_c2:
        min_pair_sel = st.slider("최소 동시 출현 횟수", 2, 20, 3, 1,
                                 key="pmi_minpair")
    with pmi_c3:
        min_pmi_sel = st.slider("최소 PMI 임계값", 0.0, 3.0, 0.5, 0.1,
                                key="pmi_threshold")

with st.spinner("PMI 그래프 산출 중… (최초 1회만 소요, 이후 캐시)"):
    pmi_df = _compute_pmi_centrality(
        top_vocab=top_vocab_sel,
        min_pair_count=min_pair_sel,
        min_pmi=min_pmi_sel,
    )

if pmi_df.empty:
    empty_state("PMI 결과 없음", "임계값을 낮추거나 어휘 크기를 늘려 주세요.")
else:
    st.caption(
        f"그래프 노드: {len(pmi_df):,}개 단어 | "
        f"신발: {(pmi_df['카테고리']=='신발').sum()}개 / "
        f"의류: {(pmi_df['카테고리']=='의류').sum()}개 / "
        f"공통: {(pmi_df['카테고리']=='공통').sum()}개"
    )

    _CAT_COLOR = {"신발": "#003087", "의류": "#D4000F", "공통": "#888888"}

    col_deg, col_bet = st.columns(2)

    with col_deg:
        top_deg = pmi_df.nlargest(15, "연결 중심성").sort_values("연결 중심성")
        fig_deg = px.bar(
            top_deg, x="연결 중심성", y="키워드",
            orientation="h",
            color="카테고리",
            color_discrete_map=_CAT_COLOR,
            title="연결 중심성 Top 15 — 허브 키워드",
            labels={"연결 중심성": "연결 중심성 (Degree)", "키워드": ""},
            hover_data={"빈도": True, "카테고리": True},
        )
        fig_deg.update_layout(height=480, showlegend=True,
                              legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_deg, use_container_width=True)
        st.caption("가장 많은 단어와 연결된 허브 키워드 — 브랜드 경험의 중심축")

    with col_bet:
        top_bet = pmi_df.nlargest(15, "매개 중심성").sort_values("매개 중심성")
        fig_bet = px.bar(
            top_bet, x="매개 중심성", y="키워드",
            orientation="h",
            color="카테고리",
            color_discrete_map=_CAT_COLOR,
            title="매개 중심성 Top 15 — 브릿지 키워드",
            labels={"매개 중심성": "매개 중심성 (Betweenness)", "키워드": ""},
            hover_data={"빈도": True, "카테고리": True},
        )
        fig_bet.update_layout(height=480, showlegend=True,
                              legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_bet, use_container_width=True)
        st.caption("신발↔의류 군집 사이를 이어주는 가교 키워드 — 브랜드 확장 전환점")

    # 연결 중심성 vs 매개 중심성 산점도
    st.subheader("키워드 포지셔닝 — 연결 중심성 × 매개 중심성")
    fig_scatter = px.scatter(
        pmi_df[pmi_df["빈도"] >= 10].nlargest(80, "연결 중심성"),
        x="연결 중심성", y="매개 중심성",
        size="빈도", color="카테고리",
        color_discrete_map=_CAT_COLOR,
        text="키워드",
        hover_data={"빈도": True, "카테고리": True},
        labels={
            "연결 중심성": "연결 중심성 (허브 강도)",
            "매개 중심성": "매개 중심성 (브릿지 강도)",
        },
        title="키워드 네트워크 포지셔닝 맵 (빈도 상위 80개)",
        size_max=40,
    )
    fig_scatter.update_traces(textposition="top center", textfont_size=9)
    fig_scatter.update_layout(height=560)
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.caption(
        "우상단: 허브이자 브릿지 — 신발·의류 양쪽 네트워크를 연결하는 전략적 전환 키워드"
    )

    with st.expander("PMI 네트워크 데이터 전체 보기"):
        st.dataframe(
            pmi_df.sort_values("연결 중심성", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

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
        "color": "#E0561A",
        "x": 0.70, "y": 0.75,
        "desc": "기능성·헤리티지 동시 강화. 룰루레몬과 정면 경쟁 (현실적 목표).",
        "risk": "기능성 R&D 투자 필요 — 1~2년 시간 소요",
    },
    {
        "title": "Option C. 기능 우선 진입",
        "color": "#2E7D32",
        "x": 0.80, "y": 0.40,
        "desc": "젝시믹스/안다르 시장에 가격·기능 경쟁으로 진입. 빠른 시장 점유 확대.",
        "risk": "헤리티지 자산 활용 부족 — 차별화 약함",
    },
]
for col, s in zip(opt, strategies):
    with col:
        st.markdown(
            f"""<div style='border: 2px solid {s['color']}; border-radius:8px;
            padding:16px; height:100%; background:{s['color']}11;'>
                <div style='color:{s['color']}; font-weight:700; font-size:15px;'>{s['title']}</div>
                <div style='font-size:11px; color:#666; margin-top:4px;'>좌표 ({s['x']:.2f}, {s['y']:.2f})</div>
                <p style='font-size:13px; margin-top:10px; color:#222;'>{s['desc']}</p>
                <div style='font-size:11px; color:#C62828; margin-top:8px;'>리스크: {s['risk']}</div>
            </div>""",
            unsafe_allow_html=True,
        )
