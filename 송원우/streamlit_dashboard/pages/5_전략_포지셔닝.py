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
from components.page_header import render_page_intro


st.set_page_config(page_title=f"{APP_TITLE} — 포지셔닝", page_icon=None, **PAGE_LAYOUT)
init_session()
mark_page_visited("positioning")

st.title("전략 포지셔닝")
st.caption("최종 산출 — 휠라의 의류 시장 진입 좌표")
st.markdown(
    "<p style='font-size:12px; color:#888; margin:2px 0 2px;'>"
    "홈 &nbsp;›&nbsp; 상품/고객 전략 &nbsp;›&nbsp; BERTopic &nbsp;›&nbsp; "
    "ABSA &nbsp;›&nbsp; <strong>포지셔닝</strong></p>",
    unsafe_allow_html=True,
)
st.caption("ABSA 속성 점수를 기능성 × 헤리티지 2축으로 압축하여 FILA의 의류 시장 진입 좌표를 확정합니다.")

render_page_intro(
    "기능성 × 헤리티지 2축 좌표와 신발↔의류 키워드 네트워크(PMI) 분석으로 "
    "FILA의 진입 좌표와 White Space 전략 옵션(A/B/C)을 결정합니다.",
    accent="#004B87",
)

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
    target_x = st.slider("목표 기능성", 0.0, 1.0, 0.95, 0.01,
                         help="휠라가 도달해야 할 기능성 점수")
with ctl[1]:
    target_y = st.slider("목표 헤리티지", 0.0, 1.0, 0.95, 0.01,
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
    st.caption(f"산출 불가 브랜드: {', '.join(na_brands)} — 해당 속성에서 ABSA 결과 부재")

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
    "연결 중심성(얼마나 많은 단어와 연결되는지)·매개 중심성(서로 다른 단어 그룹을 이어주는 정도) 계산"
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
_PMI_STOPWORDS: frozenset[str] = frozenset([
    "있다", "없다", "좋다", "같다", "하다", "이다", "되다", "많다",
    "너무", "진짜", "정말", "그냥", "조금", "약간", "엄청", "완전", "매우", "많이",
    "느낌", "생각", "마음", "이거", "저거", "그런", "이런", "저런", "어떤",
    "것", "수", "때", "거", "게", "걸", "더", "안", "못", "또", "다", "잘",
    "좋아", "좋아요", "있어", "없어", "같아", "합니다", "됩니다",
    "구매", "주문", "배송", "포장", "리뷰", "상품", "제품",
    "이번", "이후", "기존", "받다", "오다", "보다", "주다",
])


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
        and w not in _PMI_STOPWORDS
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
            "키워드":   node,
            "연결 중심성": round(degree_c.get(node, 0), 4),
            "매개 중심성": round(between_c.get(node, 0), 4),
            "빈도":     word_counts.get(node, 0),
            "카테고리":  _cat(node),
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
            title="연결 중심성 Top 15",
            labels={"연결 중심성": "연결 중심성", "키워드": ""},
            hover_data={"빈도": True, "카테고리": True},
        )
        fig_deg.update_layout(height=480, showlegend=True,
                              legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_deg, use_container_width=True)
        st.caption("연결 중심성: 한 단어가 얼마나 많은 다른 단어와 연결되어 있는지 — 수치가 높을수록 브랜드 경험의 중심 단어")
        st.caption("※ 가장 많은 단어들과 짝지어져서 언급된 핵심 단어입니다.")

    with col_bet:
        top_bet = pmi_df.nlargest(15, "매개 중심성").sort_values("매개 중심성")
        fig_bet = px.bar(
            top_bet, x="매개 중심성", y="키워드",
            orientation="h",
            color="카테고리",
            color_discrete_map=_CAT_COLOR,
            title="매개 중심성 Top 15",
            labels={"매개 중심성": "매개 중심성", "키워드": ""},
            hover_data={"빈도": True, "카테고리": True},
        )
        fig_bet.update_layout(height=480, showlegend=True,
                              legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig_bet, use_container_width=True)
        st.caption("매개 중심성: 신발 단어 그룹과 의류 단어 그룹 사이를 얼마나 잘 이어주는지 — 브랜드 확장의 전환점이 되는 단어")
        st.caption("※ 서로 다른 주제나 흩어진 단어들을 중간에서 이어주는 다리 역할의 단어입니다.")

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
            "연결 중심성": "연결 중심성 (많이 연결된 단어)",
            "매개 중심성": "매개 중심성 (다리 역할 단어)",
        },
        title="키워드 네트워크 포지셔닝 맵 (빈도 상위 80개)",
        size_max=40,
    )
    fig_scatter.update_traces(textposition="top center", textfont_size=9)
    fig_scatter.update_layout(height=560)
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.caption(
        "우상단: 허브이자 가교 — 신발·의류 양쪽 네트워크를 연결하는 전략적 전환 키워드"
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
st.caption(
    "기준점: FILA 현 좌표 **(0.91, 0.98)** — 헤리티지 1위, 기능성 4위. "
    "룰루레몬 (0.96, 0.95) / 젝시믹스 (0.94, 0.92) / 안다르 (0.93, 0.95). "
    "단, 좌표는 '언급 시 긍정 강도' — **발화량 자체(BERTopic)**는 FILA 기능성 9.7% vs 룰루레몬 46.7%로 4배 차이"
)
opt = st.columns(3)
strategies = [
    {
        "title": "Option A. Heritage Defender (수성형)",
        "color": "#7B68EE",
        "x": 0.94, "y": 0.98,
        "delta": "Δx +0.03 / Δy 0",
        "desc": (
            "현재 **헤리티지 1위(y=0.98)** 자산을 그대로 유지하면서, "
            "기능성 좌표를 룰루레몬과의 격차(Δx 0.054)의 절반인 +0.03만 좁힌다. "
            "디자인 P_ratio +0.611(4브랜드 1위) + 발화 19.5%(룰루레몬 6.1%의 3배) 활용 — "
            "**디자인·헤리티지 컬렉션 + PDP 기능 메시지 보강**으로 R&D 부담 없이 단기 실행"
        ),
        "risk": (
            "기능성 발화량 9.7% 미해결. 룰루레몬이 헤리티지로 따라오면 1위 흔들림. "
            "차별화는 단기 유지, 천장 존재"
        ),
    },
    {
        "title": "Option B. Holistic Leader (정상 도전)",
        "color": "#E0561A",
        "x": 0.96, "y": 0.97,
        "delta": "Δx +0.05 / Δy −0.01",
        "desc": (
            "**룰루레몬의 기능성 좌표 0.962를 직접 매치**하면서 헤리티지도 0.97 유지 — "
            "유일하게 좌표상 4브랜드 우상단을 동시 점유. "
            "BERTopic 기능성 **발화 점유율 9.7% → 30%** 12개월 KPI 설정, "
            "쿨링·압박·통기성 R&D + 광고·인플루언서 일관 노출 + 헤리티지 디자인 분리 유지"
        ),
        "risk": (
            "R&D + 마케팅 동시 투자로 CAPEX·OPEX 가장 큼. "
            "12~24개월 회수, 메시지 일관성 실패 시 두 축 동시 약화 위험"
        ),
    },
    {
        "title": "Option C. Function Catch-up (기능 추격)",
        "color": "#2E7D32",
        "x": 0.95, "y": 0.93,
        "delta": "Δx +0.04 / Δy −0.05",
        "desc": (
            "기능성 좌표를 안다르·젝시믹스 수준(0.93~0.94) 위로 끌어올리되 "
            "헤리티지는 안다르 수준(0.95)으로 의도적 양보. "
            "**저평점 9.4K의 핏 46.4% + 품질 36.8% = 83% 원인 즉시 차단** — "
            "사이즈 가이드 + 50회 세탁 후 형태 인증 + 기능성 라벨링으로 단기 반품률·CS 부담 절감"
        ),
        "risk": (
            "디자인 +0.611·헤리티지 0.98 활용 부족 → 차별화 약화. "
            "기능성 경쟁(룰루레몬·젝시믹스) 영역 직접 진입 — 마진율 압박"
        ),
    },
]
for col, s in zip(opt, strategies):
    with col:
        st.markdown(
            f"""<div style='border: 2px solid {s['color']}; border-radius:8px;
            padding:16px; height:100%; background:{s['color']}11;'>
                <div style='color:{s['color']}; font-weight:700; font-size:15px;'>{s['title']}</div>
                <div style='font-size:11px; color:#666; margin-top:4px;'>목표 좌표 ({s['x']:.2f}, {s['y']:.2f}) · {s['delta']}</div>
                <p style='font-size:13px; margin-top:10px; color:#222;'>{s['desc']}</p>
                <div style='font-size:11px; color:#C62828; margin-top:8px;'>리스크: {s['risk']}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("---")
st.markdown(
    "<div style='background:#F0F4FF; border-left:4px solid #003087; "
    "padding:14px 18px; border-radius:0 6px 6px 0;'>"
    "<strong>권장 진입 경로 — 12~24개월 3-Phase 로드맵</strong><br/><br/>"
    "<strong>Phase 1 (0–6개월) · Option C 단기 액션</strong>: "
    "사이즈표 정확화 + 50회 세탁 후 형태 인증 + 기능성 라벨링 — "
    "저평점 핏+품질 83% 즉시 차단, 반품률·CS 부담 단기 절감. "
    "지표: 1~2점 비율, 반품률, CS 인입 건수.<br/><br/>"
    "<strong>Phase 2 (6–18개월) · Option A 헤리티지 컬렉션</strong>: "
    "디자인 +0.611·발화 19.5% 강점 자산화 — 신발 디자인 헤리티지 의류 컬렉션 출시 + "
    "헤리티지 마케팅으로 좌표 (0.94, 0.98) 도달. "
    "지표: 디자인 P_ratio, 헤리티지 토픽 점유율, 컬렉션 매출.<br/><br/>"
    "<strong>Phase 3 (18–24개월) · Option B Holistic 전환</strong>: "
    "기능성 R&D 출시 + 광고·인플루언서 일관 노출 — "
    "BERTopic 기능성 발화 9.7% → 30% 도달 시 좌표 (0.96, 0.97)로 룰루레몬 정상 도전. "
    "지표: 기능성 발화 점유율, 기능성 P_ratio, 재구매율."
    "</div>",
    unsafe_allow_html=True,
)
