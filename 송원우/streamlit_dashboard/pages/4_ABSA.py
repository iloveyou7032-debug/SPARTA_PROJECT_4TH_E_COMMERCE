"""
4_ABSA.py — 브랜드 속성 평가 (EXAONE ABSA 6속성)
=================================================
"""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import APP_TITLE, PAGE_LAYOUT, BRAND_ORDER, BRANDS, PATHS, ASPECT_LABELS, ASPECTS
from utils.data_loader import compute_aspect_polarity, filters_to_hash
from utils.session import init_session, get_filters, mark_page_visited
from utils.exceptions import safe_block, empty_state, warn_using_dummy
from components.filters import render_sidebar_filters
from components.charts import aspect_polarity_diverging_bar


st.set_page_config(page_title=f"{APP_TITLE} — ABSA", page_icon=None, **PAGE_LAYOUT)
init_session()
mark_page_visited("absa")

st.title("ABSA")
st.caption("EXAONE 3.5 기반 6속성 P/N/X 분석 결과")
st.markdown(
    "<p style='font-size:12px; color:#888; margin:2px 0 2px;'>"
    "📊 홈 &nbsp;›&nbsp; 상품/고객 전략 &nbsp;›&nbsp; BERTopic &nbsp;›&nbsp; "
    "<strong>ABSA</strong> &nbsp;›&nbsp; 포지셔닝</p>",
    unsafe_allow_html=True,
)
st.caption("BERTopic이 발굴한 핵심 토픽을 6가지 속성 단위의 감성(P/N/X)으로 정량화합니다.")

with st.expander("지표 정의 — P/N/X 비율의 분모는 무엇인가요?"):
    st.markdown(
        """
- **P_ratio (긍정 비율)** = 해당 속성에서 **P로 분류된 리뷰 수 / 해당 속성이 언급된 전체 리뷰 수**
- **N_ratio (부정 비율)** = 해당 속성에서 **N으로 분류된 리뷰 수 / 해당 속성이 언급된 전체 리뷰 수**
- **X_ratio (미언급/중립 비율)** = `1 − P_ratio − N_ratio`
- 분모는 **해당 속성이 언급된 리뷰**입니다 (전체 리뷰가 아닙니다).
  - 예: 기능성 P_ratio 60% = "기능성을 언급한 리뷰 100건 중 60건이 긍정"
- X_ratio가 높은 속성은 **"해당 속성에 대한 언급 자체가 적다"**는 뜻이며,
  P/N 비율 해석 시 분모 크기(언급 수)를 함께 봐야 합니다.
        """
    )

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

# ── 레이더 차트 — 4브랜드 × 6속성 ────────────────────────────
# st.subheader("브랜드 × 6속성 레이더 차트 — 포지셔닝 비교")

# with safe_block("레이더 차트"):
#     aspect_keys = [a["key"] for a in ASPECTS]
#     labels = [ASPECT_LABELS[k] for k in aspect_keys]
#     labels_closed = labels + [labels[0]]

#     fig_radar = go.Figure()
#     for brand in BRAND_ORDER:
#         sub = polarity[polarity["brand"] == brand]
#         if sub.empty:
#             continue
#         vals = []
#         for asp in aspect_keys:
#             row = sub[sub["aspect"] == asp]
#             vals.append(float(row["P_ratio"].iloc[0]) if not row.empty else 0.0)
#         vals_closed = vals + [vals[0]]

#         color = BRANDS[brand]["color"]
#         fig_radar.add_trace(go.Scatterpolar(
#             r=vals_closed,
#             theta=labels_closed,
#             fill="toself",
#             fillcolor=color + "2E",  # ~18% opacity
#             line=dict(color=color, width=2.5),
#             name=BRANDS[brand]["label"],
#             hovertemplate="%{theta}: %{r:.1%}<extra>" + BRANDS[brand]["label"] + "</extra>",
#         ))

#     fig_radar.update_layout(
#         polar=dict(
#             radialaxis=dict(
#                 visible=True,
#                 range=[0, 1],
#                 tickformat=".0%",
#                 tickvals=[0.2, 0.4, 0.6, 0.8, 1.0],
#                 tickfont=dict(size=10),
#                 gridcolor="#D0D8EC",
#             ),
#             angularaxis=dict(
#                 tickfont=dict(size=12),
#                 gridcolor="#D0D8EC",
#             ),
#             bgcolor="#F8FAFF",
#         ),
#         height=540,
#         showlegend=True,
#         legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
#         paper_bgcolor="#FFFFFF",
#     )
#     st.plotly_chart(fig_radar, use_container_width=True)

# # 1. 차트 렌더링 코드 바로 위에 헥스 변환 함수 추가
# def hex_to_rgba(hex_color: str, alpha: float = 0.18) -> str:
#     """6자리 Hex 코드를 rgba(r, g, b, alpha) 포맷으로 변환"""
#     hex_color = hex_color.lstrip('#')
#     if len(hex_color) == 6:
#         r = int(hex_color[0:2], 16)
#         g = int(hex_color[2:4], 16)
#         b = int(hex_color[4:6], 16)
#         return f"rgba({r}, {g}, {b}, {alpha})"
#     return f"#{hex_color}"

# # 2. 레이더 차트 본문
# st.subheader("브랜드 × 6속성 레이더 차트 — 포지셔닝 비교")

# with safe_block("레이더 차트"):
#     aspect_keys = [a["key"] for a in ASPECTS]
#     labels = [ASPECT_LABELS[k] for k in aspect_keys]
#     labels_closed = labels + [labels[0]]

#     fig_radar = go.Figure()
#     for brand in BRAND_ORDER:
#         sub = polarity[polarity["brand"] == brand]
#         if sub.empty:
#             continue
#         vals = []
#         for asp in aspect_keys:
#             row = sub[sub["aspect"] == asp]
#             vals.append(float(row["P_ratio"].iloc[0]) if not row.empty else 0.0)
#         vals_closed = vals + [vals[0]]

#         color = BRANDS[brand]["color"]
#         # 수정됨: 투명도 18%가 적용된 rgba 색상 적용
#         fill_color_with_alpha = hex_to_rgba(color, alpha=0.18)

#         fig_radar.add_trace(go.Scatterpolar(
#             r=vals_closed,
#             theta=labels_closed,
#             fill="toself",
#             fillcolor=fill_color_with_alpha,  # 에러 해결!
#             line=dict(color=color, width=2.5),
#             name=BRANDS[brand]["label"],
#             hovertemplate="%{theta}: %{r:.1%}<extra>" + BRANDS[brand]["label"] + "</extra>",
#         ))

#     fig_radar.update_layout(
#         polar=dict(
#             radialaxis=dict(
#                 visible=True,
#                 range=[0, 1],
#                 tickformat=".0%",
#                 tickvals=[0.2, 0.4, 0.6, 0.8, 1.0],
#                 tickfont=dict(size=10),
#                 gridcolor="#D0D8EC",
#             ),
#             angularaxis=dict(
#                 tickfont=dict(size=12),
#                 gridcolor="#D0D8EC",
#             ),
#             bgcolor="#F8FAFF",
#         ),
#         height=540,
#         showlegend=True,
#         legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center"),
#         paper_bgcolor="#FFFFFF",
#     )
#     st.plotly_chart(fig_radar, use_container_width=True)

# ── [E] 브랜드 × 속성 P_ratio 히트맵 ─────────────────────────
st.subheader("브랜드 × 속성 감성 히트맵")
st.caption("4개 브랜드 × 6개 속성의 긍정 비율(P_ratio) — 색이 진할수록 긍정적")

_has_real_absa = (
    PATHS["absa"].exists()
    or (PATHS.get("absa_labeler1") and PATHS["absa_labeler1"].exists())
    or (PATHS.get("absa_complement") and PATHS["absa_complement"].exists())
)
if not _has_real_absa:
    st.info("실데이터 연결 후 활성화 — ABSA 추론 완료 시 자동 전환 (현재 더미 기반 미리보기)")

with safe_block("ABSA 히트맵"):
    _aspect_order  = [a["key"] for a in ASPECTS]
    _aspect_labels = [ASPECT_LABELS[k] for k in _aspect_order]
    _brand_order_f = [b for b in BRAND_ORDER if b in polarity["brand"].unique()]
    _brand_labels  = [BRANDS[b]["label"] for b in _brand_order_f]

    _pivot = (
        polarity[polarity["brand"].isin(_brand_order_f)]
        .pivot(index="brand", columns="aspect", values="P_ratio")
        .reindex(index=_brand_order_f, columns=_aspect_order)
    )

    _fig_hm = px.imshow(
        _pivot.values,
        x=_aspect_labels,
        y=_brand_labels,
        color_continuous_scale="RdYlGn",
        zmin=0.0, zmax=1.0,
        text_auto=".0%",
        aspect="auto",
        labels={"color": "P_ratio"},
    )
    _fig_hm.update_layout(
        height=260,
        margin=dict(t=20, b=20, l=10, r=10),
        coloraxis_colorbar=dict(
            tickformat=".0%",
            title="긍정 비율",
            len=0.9,
        ),
        xaxis=dict(side="bottom"),
    )
    _fig_hm.update_traces(textfont=dict(size=12))
    st.plotly_chart(_fig_hm, use_container_width=True)

st.divider()

# 1. 헬퍼 함수 (투명도 처리)
def hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
        return f"rgba({r}, {g}, {b}, {alpha})"
    return f"rgba(100, 100, 100, {alpha})"

# 2. 레이더 차트 섹션 시작
st.subheader("브랜드별 속성 평가 - 긍정 vs 부정 입체 비교")

# 레이아웃 분할 (좌: 긍정, 우: 부정)
col_left, col_right = st.columns(2)

aspect_keys = [a["key"] for a in ASPECTS]
labels = [ASPECT_LABELS[k] for k in aspect_keys]
labels_closed = labels + [labels[0]]

# 공통 레이아웃 설정 함수 (축 범위 고정)
def update_radar_layout(fig, title):
    fig.update_layout(
        title=dict(text=title, x=0.5, xanchor="center", font=dict(size=16)),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1.0],      # 중요: 긍정/부정 스케일을 100%로 통일
                tickformat=".0%",
                gridcolor="#ECEFF4"
            ),
            bgcolor="#F8FAFF"
        ),
        height=450,
        margin=dict(t=60, b=40, l=40, r=40),
        showlegend=True,
        legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
    )

# --- [왼쪽: 긍정(Positive) 레이더] ---
with col_left:
    fig_p = go.Figure()
    for brand in BRAND_ORDER:
        sub = polarity[polarity["brand"] == brand]
        if sub.empty: continue
        
        # P_ratio 데이터 추출
        vals = [float(sub[sub["aspect"] == asp]["P_ratio"].iloc[0]) if not sub[sub["aspect"] == asp].empty else 0.0 for asp in aspect_keys]
        vals_closed = vals + [vals[0]]
        
        color = BRANDS[brand]["color"]
        fig_p.add_trace(go.Scatterpolar(
            r=vals_closed, theta=labels_closed,
            fill="toself",
            fillcolor=hex_to_rgba(color, 0.2),
            line=dict(color=color, width=2),
            name=BRANDS[brand]["label"]
        ))
    
    update_radar_layout(fig_p, "긍정적 요인 (Positive)")
    st.plotly_chart(fig_p, use_container_width=True)

# --- [오른쪽: 부정(Negative) 레이더] ---
with col_right:
    fig_n = go.Figure()
    for brand in BRAND_ORDER:
        sub = polarity[polarity["brand"] == brand]
        if sub.empty: continue
        
        # N_ratio 데이터 추출
        vals = [float(sub[sub["aspect"] == asp]["N_ratio"].iloc[0]) if not sub[sub["aspect"] == asp].empty else 0.0 for asp in aspect_keys]
        vals_closed = vals + [vals[0]]
        
        color = BRANDS[brand]["color"]
        fig_n.add_trace(go.Scatterpolar(
            r=vals_closed, theta=labels_closed,
            fill="toself",
            fillcolor=hex_to_rgba(color, 0.2),
            line=dict(color=color, width=2),
            name=BRANDS[brand]["label"]
        ))
    
    update_radar_layout(fig_n, "부정적 요인 (Negative)")
    st.plotly_chart(fig_n, use_container_width=True)

st.caption("면적이 넓을수록 해당 속성에서 감성 비율이 높음. 꼭짓점 호버로 수치 확인.")

st.divider()

# ── 브랜드 선택 → 발산 막대 ──────────────────────────────────
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

# ── 강점·약점 Top3 카드 ───────────────────────────────────────
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

st.divider()

# ── 대표 리뷰 예시 (속성 × 감성 단위) ────────────────────────
st.subheader("대표 리뷰 예시")
st.caption("속성·감성 조합별 실제 리뷰를 확인 — 모델 결과의 납득성 검증")

with safe_block("대표 리뷰"):
    rc1, rc2, rc3 = st.columns([1, 1, 1])
    with rc1:
        ex_brand = st.selectbox(
            "브랜드",
            options=[b for b in BRAND_ORDER if b in polarity["brand"].unique()],
            format_func=lambda b: BRANDS[b]["label"],
            key="ex_brand",
        )
    with rc2:
        ex_aspect = st.selectbox(
            "속성",
            options=[a["key"] for a in ASPECTS],
            format_func=lambda k: ASPECT_LABELS[k],
            key="ex_aspect",
        )
    with rc3:
        ex_polarity = st.radio(
            "감성", ["P", "N"], horizontal=True, key="ex_polarity",
            format_func=lambda x: "긍정 (P)" if x == "P" else "부정 (N)",
        )

    # ABSA 원본에서 해당 조합 매칭
    from utils.data_loader import get_absa, get_reviews
    try:
        absa = get_absa()
        reviews_for_ex = get_reviews(columns=("review_id", "brand", "rating", "content_clean"))

        if ex_aspect in absa.columns and not absa.empty:
            ex_match = absa[absa[ex_aspect] == ex_polarity][["review_id", f"{ex_aspect}_confidence"]]
            sample = (
                ex_match.merge(
                    reviews_for_ex[reviews_for_ex["brand"] == ex_brand],
                    on="review_id", how="inner",
                )
                .sort_values(f"{ex_aspect}_confidence", ascending=False)
                .head(5)
            )
            if sample.empty:
                empty_state("해당 조합 리뷰 없음")
            else:
                st.caption(f"신뢰도 상위 {len(sample)}건 (최대 5건)")
                for _, row in sample.iterrows():
                    conf = row.get(f"{ex_aspect}_confidence", 0)
                    rating = row.get("rating", "-")
                    text = str(row.get("content_clean", "")).strip()[:300]
                    polarity_color = "#2E7D32" if ex_polarity == "P" else "#C62828"
                    st.markdown(
                        f"""<div style='border-left: 3px solid {polarity_color};
                        padding: 8px 12px; margin: 6px 0;
                        background: rgba(128,128,128,0.06); border-radius: 3px;'>
                            <div style='font-size: 11px; color: #888;'>
                                ⭐ {rating} · 신뢰도 {conf:.2f}
                            </div>
                            <div style='margin-top: 4px;'>{text}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
        else:
            empty_state(f"속성 '{ex_aspect}' 컬럼 없음")
    except Exception as exc:
        empty_state("대표 리뷰 조회 실패", str(exc))

st.divider()

# ── [E] FILA 부정 리뷰 핵심 키워드 카드 ──────────────────────
st.subheader("FILA 부정 리뷰 핵심 키워드")
_has_complement = PATHS.get("absa_complement") and PATHS["absa_complement"].exists()
if not _has_complement:
    st.info(
        "FILA complement 추론 완료 후 활성화 — "
        "`absa_fila_complement_predictions.parquet` 생성 시 자동 전환"
    )
else:
    with safe_block("FILA 부정 리뷰 카드"):
        from utils.data_loader import get_absa as _get_absa, get_reviews as _get_reviews
        import collections

        _absa_full = _get_absa()
        _reviews_fila = _get_reviews(
            columns=("review_id", "brand", "content_clean")
        )
        _reviews_fila = _reviews_fila[_reviews_fila["brand"] == "FILA"]

        _neg_aspect_cols = [
            k for k in [a["key"] for a in ASPECTS]
            if k in _absa_full.columns
        ]
        _neg_cards = []
        for _asp in _neg_aspect_cols:
            _neg_ids = _absa_full[_absa_full[_asp] == "N"]["review_id"]
            _neg_texts = (
                _reviews_fila[_reviews_fila["review_id"].isin(_neg_ids)]["content_clean"]
                .dropna()
                .astype(str)
            )
            if _neg_texts.empty:
                continue
            _words = " ".join(_neg_texts).split()
            _top3 = [w for w, _ in collections.Counter(_words).most_common(30)
                     if len(w) > 1 and not w.isdigit()][:3]
            _neg_cards.append((ASPECT_LABELS[_asp], _top3, len(_neg_ids)))

        if _neg_cards:
            _nc_cols = st.columns(len(_neg_cards))
            for _col, (_asp_label, _kws, _cnt) in zip(_nc_cols, _neg_cards):
                with _col:
                    st.markdown(
                        f"<div style='border-top:3px solid #C62828; padding:10px 12px;"
                        f"background:#C6282811; border-radius:4px;'>"
                        f"<div style='font-size:11px; color:#C62828; font-weight:600;'>"
                        f"FILA 부정 — {_asp_label} ({_cnt:,}건)</div>"
                        f"<div style='font-size:14px; font-weight:700; margin-top:6px;'>"
                        f"{' · '.join(_kws) if _kws else '—'}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("FILA 부정 리뷰 데이터 없음")

st.divider()

# ── 원시 데이터 ──────────────────────────────────────────────
with st.expander("ABSA 집계 원시 데이터"):
    df_view = polarity.copy()
    df_view["aspect"] = df_view["aspect"].map(ASPECT_LABELS)
    for c in ["P_ratio", "N_ratio", "X_ratio"]:
        df_view[c] = (df_view[c] * 100).round(1).astype(str) + "%"
    st.dataframe(df_view, use_container_width=True)
