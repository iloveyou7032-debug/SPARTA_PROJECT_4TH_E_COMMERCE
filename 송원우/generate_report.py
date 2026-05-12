"""
generate_report.py — FILA 애슬레저 시장 진입 전략 보고서 PDF 생성
playwright chromium 기반 HTML → PDF 변환 (한국어 지원)
"""
from __future__ import annotations
import sys
from pathlib import Path

OUT_PDF = Path(__file__).resolve().parent / "FILA_애슬레저_진입전략_보고서.pdf"

# ─────────────────────────────────────────────────────────────
# 데이터 상수 (ABSA v9 + 실측 수치)
# ─────────────────────────────────────────────────────────────
SENTIMENT = {
    "FILA":   {"핏/사이즈":+0.732,"소재/내구성":+0.277,"기능성":+0.382,"디자인":+0.611,"브랜드/헤리티지":+0.388,"가격/가치":+0.185},
    "안다르":  {"핏/사이즈":+0.839,"소재/내구성":+0.441,"기능성":+0.597,"디자인":+0.392,"브랜드/헤리티지":+0.456,"가격/가치":+0.179},
    "젝시믹스":{"핏/사이즈":+0.749,"소재/내구성":+0.375,"기능성":+0.566,"디자인":+0.405,"브랜드/헤리티지":+0.302,"가격/가치":+0.176},
    "룰루레몬":{"핏/사이즈":+0.858,"소재/내구성":+0.553,"기능성":+0.674,"디자인":+0.519,"브랜드/헤리티지":+0.487,"가격/가치":+0.104},
}
BRAND_COLORS = {"FILA":"#003087","안다르":"#D4000F","젝시믹스":"#E0561A","룰루레몬":"#1565C0"}
SALES = {
    "FILA":   {"2023":4536,"2024":4869,"2025":5127,"yoy":"+5.3%","share":"32.0%"},
    "안다르":  {"2023":1013,"2024":1453,"2025":1842,"yoy":"+26.7%","share":"11.5%"},
    "젝시믹스":{"2023":2243,"2024":2184,"2025":2180,"yoy":"-0.2%","share":"13.6%"},
    "룰루레몬":{"2023":1177,"2024":1567,"2025":2093,"yoy":"+33.6%","share":"13.0%"},
}
RATING = {"FILA":4.88,"안다르":4.78,"젝시믹스":4.92,"룰루레몬":4.83}
ASPECTS = ["핏/사이즈","소재/내구성","기능성","디자인","브랜드/헤리티지","가격/가치"]
BRANDS = ["FILA","안다르","젝시믹스","룰루레몬"]

# ─────────────────────────────────────────────────────────────
# SVG 생성 유틸
# ─────────────────────────────────────────────────────────────
def grouped_bar_svg(width=680, height=320) -> str:
    """브랜드×속성 Sentiment Score 그룹 막대."""
    n_asp = len(ASPECTS)
    n_br  = len(BRANDS)
    pad_l, pad_r, pad_t, pad_b = 52, 20, 30, 80
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    group_w = plot_w / n_asp
    bar_w   = group_w * 0.18
    gap     = group_w * 0.04

    y_min, y_max = -0.1, 1.0
    y_range = y_max - y_min

    def yscale(v):
        return pad_t + plot_h * (1 - (v - y_min) / y_range)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']

    # 배경
    lines.append(f'<rect width="{width}" height="{height}" fill="#fafafa" rx="4"/>')

    # Y축 그리드
    for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = yscale(v)
        color = "#aaa" if v == 0 else "#e0e0e0"
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="{color}" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" font-size="9" fill="#666">{v:.2f}</text>')

    # 막대
    for ai, asp in enumerate(ASPECTS):
        group_cx = pad_l + group_w * (ai + 0.5)
        total_w = n_br * bar_w + (n_br-1) * gap
        for bi, brand in enumerate(BRANDS):
            val = SENTIMENT[brand][asp]
            x = group_cx - total_w/2 + bi * (bar_w + gap)
            y0 = yscale(0)
            yv = yscale(val)
            bh = abs(y0 - yv)
            by = min(y0, yv)
            c = BRAND_COLORS[brand]
            lines.append(f'<rect x="{x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{c}" opacity="0.85" rx="1"/>')

        # X축 라벨
        ly = height - pad_b + 14
        lines.append(f'<text x="{group_cx:.1f}" y="{ly}" text-anchor="middle" font-size="10" fill="#333">{asp}</text>')

    # 범례
    lx = pad_l + 4
    for bi, brand in enumerate(BRANDS):
        lines.append(f'<rect x="{lx + bi*120}" y="{height-18}" width="10" height="10" fill="{BRAND_COLORS[brand]}" rx="1"/>')
        lines.append(f'<text x="{lx + bi*120 + 13}" y="{height-9}" font-size="10" fill="#333">{brand}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def positioning_svg(width=520, height=400) -> str:
    """2D 포지셔닝 맵: X=기능성, Y=브랜드/헤리티지"""
    pad = 60
    plot_w = width - 2*pad
    plot_h = height - 2*pad
    x_min, x_max = 0.2, 0.8
    y_min, y_max = 0.2, 0.6

    def sx(v): return pad + (v - x_min) / (x_max - x_min) * plot_w
    def sy(v): return height - pad - (v - y_min) / (y_max - y_min) * plot_h

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    lines.append(f'<rect width="{width}" height="{height}" fill="#f8f9fa" rx="6"/>')

    # 그리드
    for gv in [0.3, 0.4, 0.5, 0.6, 0.7]:
        x = sx(gv); y = sy(gv)
        lines.append(f'<line x1="{x:.1f}" y1="{pad}" x2="{x:.1f}" y2="{height-pad}" stroke="#e0e0e0" stroke-width="1"/>')
        lines.append(f'<line x1="{pad}" y1="{y:.1f}" x2="{width-pad}" y2="{y:.1f}" stroke="#e0e0e0" stroke-width="1"/>')

    # 축
    lines.append(f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#999" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#999" stroke-width="1.5"/>')
    lines.append(f'<text x="{width//2}" y="{height-8}" text-anchor="middle" font-size="12" fill="#555">기능성 Sentiment Score</text>')
    lines.append(f'<text x="14" y="{height//2}" text-anchor="middle" font-size="12" fill="#555" transform="rotate(-90,14,{height//2})">브랜드 헤리티지 Score</text>')

    # White Space 영역
    ws_x, ws_y, ws_r = sx(0.55), sy(0.43), 28
    lines.append(f'<circle cx="{ws_x:.1f}" cy="{ws_y:.1f}" r="{ws_r}" fill="#FFD700" opacity="0.25" stroke="#FFD700" stroke-width="2" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{ws_x:.1f}" y="{ws_y-ws_r-6:.1f}" text-anchor="middle" font-size="11" fill="#B8860B" font-weight="bold">White Space</text>')
    lines.append(f'<text x="{ws_x:.1f}" y="{ws_y-ws_r+6:.1f}" text-anchor="middle" font-size="9" fill="#B8860B">FILA 목표 포지션</text>')

    # 각 브랜드 좌표: (기능성, 브랜드헤리티지)
    coords = {
        "FILA":   (SENTIMENT["FILA"]["기능성"],    SENTIMENT["FILA"]["브랜드/헤리티지"]),
        "안다르":  (SENTIMENT["안다르"]["기능성"],   SENTIMENT["안다르"]["브랜드/헤리티지"]),
        "젝시믹스":(SENTIMENT["젝시믹스"]["기능성"], SENTIMENT["젝시믹스"]["브랜드/헤리티지"]),
        "룰루레몬":(SENTIMENT["룰루레몬"]["기능성"], SENTIMENT["룰루레몬"]["브랜드/헤리티지"]),
    }
    offsets = {"FILA":(-14,-14),"안다르":(10,0),"젝시믹스":(10,10),"룰루레몬":(-14,14)}

    for brand, (bx, by) in coords.items():
        cx, cy = sx(bx), sy(by)
        c = BRAND_COLORS[brand]
        r = 16 if brand == "FILA" else 13
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{c}" opacity="0.9"/>')
        lines.append(f'<text x="{cx:.1f}" y="{cy+4:.1f}" text-anchor="middle" font-size="9" fill="white" font-weight="bold">{brand}</text>')
        dx, dy = offsets[brand]
        lines.append(f'<text x="{cx+dx:.1f}" y="{cy+dy+18:.1f}" text-anchor="middle" font-size="9" fill="{c}">'
                     f'({bx:.2f}, {by:.2f})</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def sales_bar_svg(width=560, height=200) -> str:
    """매출 막대 (3개년 + 브랜드별)"""
    years = ["2023","2024","2025"]
    brands = BRANDS
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    all_vals = [v for b in brands for y in years for v in [SALES[b][y]]]
    v_max = max(all_vals) * 1.1

    n_br = len(brands)
    n_yr = len(years)
    group_w = plot_w / n_br
    bar_w = group_w * 0.22
    gap   = group_w * 0.04

    def yscale(v): return pad_t + plot_h * (1 - v / v_max)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    lines.append(f'<rect width="{width}" height="{height}" fill="#fafafa" rx="4"/>')

    for gv in [1000,2000,3000,4000,5000]:
        if gv <= v_max:
            y = yscale(gv)
            lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" stroke="#e0e0e0" stroke-width="1"/>')
            lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" font-size="9" fill="#888">{gv}</text>')

    for bi, brand in enumerate(brands):
        group_cx = pad_l + group_w * (bi + 0.5)
        total_w = n_yr * bar_w + (n_yr-1) * gap
        for yi, year in enumerate(years):
            val = SALES[brand][year]
            x = group_cx - total_w/2 + yi * (bar_w + gap)
            yv = yscale(val)
            bh = height - pad_b - yv
            alpha = 0.55 + 0.15 * yi
            c = BRAND_COLORS[brand]
            lines.append(f'<rect x="{x:.1f}" y="{yv:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{c}" opacity="{alpha:.2f}" rx="1"/>')

        ly = height - pad_b + 14
        yoy = SALES[brand]["yoy"]
        color_yoy = "#c0392b" if yoy.startswith("-") else "#27ae60"
        lines.append(f'<text x="{group_cx:.1f}" y="{ly}" text-anchor="middle" font-size="11" fill="#333">{brand}</text>')
        lines.append(f'<text x="{group_cx:.1f}" y="{ly+13}" text-anchor="middle" font-size="9" fill="{color_yoy}">{yoy} (25 vs 24)</text>')

    # 범례 (연도)
    yr_colors = ["rgba(0,0,0,0.4)","rgba(0,0,0,0.55)","rgba(0,0,0,0.7)"]
    for yi, year in enumerate(years):
        lines.append(f'<rect x="{pad_l + yi*60}" y="{height-14}" width="10" height="8" fill="#555" opacity="{0.4+0.15*yi}" rx="1"/>')
        lines.append(f'<text x="{pad_l + yi*60 + 13}" y="{height-6}" font-size="9" fill="#555">{year}년</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
# HTML 보고서 빌드
# ─────────────────────────────────────────────────────────────
def build_html() -> str:
    bar_svg  = grouped_bar_svg()
    pos_svg  = positioning_svg()
    sale_svg = sales_bar_svg()

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>FILA 애슬레저 시장 진입 전략</title>
<style>
  @page {{ size: A4; margin: 16mm 18mm 16mm 18mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans CJK KR", sans-serif;
    font-size: 10pt;
    color: #222;
    line-height: 1.6;
    background: white;
  }}

  /* 표지 */
  .cover {{
    page-break-after: always;
    height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: linear-gradient(150deg, #001f5c 0%, #003087 55%, #1a5276 100%);
    color: white;
    text-align: center;
    padding: 48px;
  }}
  .cover-badge {{
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.4);
    border-radius: 20px;
    padding: 6px 20px;
    font-size: 9pt;
    letter-spacing: 2px;
    margin-bottom: 32px;
  }}
  .cover h1 {{ font-size: 26pt; font-weight: 800; letter-spacing: -0.5px; line-height: 1.3; margin-bottom: 16px; }}
  .cover h2 {{ font-size: 14pt; font-weight: 400; opacity: 0.85; margin-bottom: 48px; }}
  .cover-divider {{ width: 60px; height: 3px; background: #FFD700; margin: 0 auto 48px; border-radius: 2px; }}
  .cover-meta {{ font-size: 9pt; opacity: 0.7; line-height: 2; }}
  .cover-logo {{ font-size: 36pt; font-weight: 900; letter-spacing: 4px; color: #FFD700; margin-bottom: 8px; }}

  /* 섹션 */
  .page-break {{ page-break-before: always; }}
  h1.section-title {{
    font-size: 16pt; font-weight: 800; color: #003087;
    border-left: 5px solid #003087;
    padding-left: 12px; margin-bottom: 20px; margin-top: 0;
  }}
  h2.sub-title {{
    font-size: 12pt; font-weight: 700; color: #1a3a6b;
    border-bottom: 1.5px solid #c8d6ea;
    padding-bottom: 5px; margin: 22px 0 12px;
  }}
  h3.label {{ font-size: 10pt; font-weight: 700; color: #333; margin: 14px 0 6px; }}

  /* KPI 카드 */
  .kpi-row {{ display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; }}
  .kpi-card {{
    flex: 1; min-width: 110px;
    background: #f0f4fb; border-radius: 8px;
    padding: 14px 12px; text-align: center;
    border-top: 3px solid #003087;
  }}
  .kpi-val {{ font-size: 18pt; font-weight: 800; color: #003087; }}
  .kpi-label {{ font-size: 8pt; color: #666; margin-top: 2px; }}

  /* 표 */
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 9pt; }}
  th {{ background: #003087; color: white; padding: 7px 10px; text-align: center; font-size: 9pt; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #e8ecf4; }}
  tr:nth-child(even) td {{ background: #f5f7fb; }}
  td.brand-name {{ font-weight: 700; }}
  td.fila {{ color: #003087; font-weight: 700; }}
  td.num {{ text-align: right; }}
  td.pos {{ color: #27ae60; font-weight: 600; }}
  td.neg {{ color: #c0392b; font-weight: 600; }}

  /* 인사이트 박스 */
  .insight-box {{
    background: #eef3fb; border-left: 4px solid #003087;
    border-radius: 0 6px 6px 0;
    padding: 12px 16px; margin: 14px 0;
  }}
  .insight-box.red {{ background: #fdf0ef; border-left-color: #c0392b; }}
  .insight-box.gold {{ background: #fffbea; border-left-color: #d4ac0d; }}
  .insight-box.green {{ background: #edfaf1; border-left-color: #27ae60; }}
  .insight-box strong {{ color: #003087; }}
  .insight-box.red strong {{ color: #c0392b; }}
  .insight-box.gold strong {{ color: #9a7d0a; }}
  .insight-box.green strong {{ color: #1e8449; }}

  /* 전략 카드 */
  .strategy-card {{
    border: 1.5px solid #c8d6ea; border-radius: 8px;
    padding: 16px 18px; margin: 14px 0;
  }}
  .strategy-num {{
    display: inline-block; background: #003087; color: white;
    border-radius: 50%; width: 22px; height: 22px;
    text-align: center; line-height: 22px; font-size: 10pt;
    font-weight: 700; margin-right: 8px; margin-bottom: 6px;
  }}
  .strategy-title {{ font-size: 12pt; font-weight: 700; color: #003087; display: inline; }}
  .strategy-sub {{ font-size: 8.5pt; color: #888; margin-left: 30px; margin-bottom: 8px; }}
  .strategy-body {{ font-size: 9.5pt; color: #333; line-height: 1.7; margin-left: 30px; }}

  /* 로드맵 */
  .roadmap {{ display: flex; gap: 10px; margin: 14px 0; }}
  .roadmap-phase {{
    flex: 1; border-radius: 8px; padding: 12px;
    border: 1.5px solid #c8d6ea;
  }}
  .roadmap-phase h4 {{ font-size: 9.5pt; font-weight: 700; color: #003087; margin-bottom: 6px; }}
  .roadmap-phase ul {{ list-style: none; padding: 0; }}
  .roadmap-phase li {{ font-size: 8.5pt; color: #444; padding: 2px 0; }}
  .roadmap-phase li::before {{ content: "▸ "; color: #003087; }}
  .phase-badge {{
    font-size: 7.5pt; background: #003087; color: white;
    border-radius: 3px; padding: 1px 6px; margin-bottom: 6px;
    display: inline-block;
  }}

  /* 감성 점수 표 색상 */
  .score-high {{ background: #d5f5e3; color: #1e8449; font-weight: 700; text-align: center; }}
  .score-mid  {{ background: #fef9e7; color: #7d6608; text-align: center; }}
  .score-low  {{ background: #fdedec; color: #922b21; text-align: center; }}
  .score-neg  {{ background: #f5b7b1; color: #922b21; font-weight: 700; text-align: center; }}

  /* SVG 래퍼 */
  .chart-wrap {{ width: 100%; overflow: hidden; margin: 12px 0; }}
  .chart-caption {{ font-size: 8.5pt; color: #888; text-align: center; margin-top: 4px; }}

  /* 각주 */
  .footnote {{ font-size: 7.5pt; color: #999; margin-top: 8px; }}

  p {{ margin: 8px 0; }}
  ul.body-list {{ padding-left: 16px; margin: 8px 0; }}
  ul.body-list li {{ margin: 4px 0; font-size: 9.5pt; }}

  .highlight {{ color: #003087; font-weight: 700; }}
  .badge {{
    display: inline-block; font-size: 8pt;
    background: #003087; color: white;
    border-radius: 3px; padding: 1px 7px; margin: 0 2px;
  }}
  .badge.red {{ background: #c0392b; }}
  .badge.green {{ background: #1e8449; }}
  .badge.gold {{ background: #b7950b; }}

  .two-col {{ display: flex; gap: 18px; }}
  .two-col > div {{ flex: 1; }}

  /* 페이지 번호 (헤더/푸터) */
  @page {{ @bottom-right {{ content: counter(page) " / " counter(pages); font-size: 8pt; color: #aaa; }} }}
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════════════════
     표지
═══════════════════════════════════════════════════════════ -->
<div class="cover">
  <div class="cover-logo">FILA</div>
  <div class="cover-badge">STRATEGIC INTELLIGENCE REPORT</div>
  <h1>애슬레저 시장 진입 전략<br/>데이터 기반 경쟁 분석</h1>
  <h2>Korean Athleisure Market Entry Strategy<br/>Consumer Intelligence &amp; Positioning Analysis</h2>
  <div class="cover-divider"></div>
  <div class="cover-meta">
    분석 기간　2024 – 2025<br/>
    분석 대상　젝시믹스 · 안다르 · 룰루레몬 · FILA<br/>
    리뷰 데이터　1,170,000+ 건<br/>
    주요 방법론　BERTopic · ABSA(EXAONE 3.5 7.8B) · Positioning Map<br/>
    작성　송원우 · 2026년 5월
  </div>
</div>


<!-- ═══════════════════════════════════════════════════════════
     Executive Summary
═══════════════════════════════════════════════════════════ -->
<section>
  <h1 class="section-title">Executive Summary</h1>

  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-val">1.17M</div>
      <div class="kpi-label">분석 리뷰 수</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">49</div>
      <div class="kpi-label">BERTopic 토픽</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">0.70</div>
      <div class="kpi-label">ABSA Macro F1</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">0.71</div>
      <div class="kpi-label">Cohen's κ</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">6</div>
      <div class="kpi-label">분석 속성 수</div>
    </div>
  </div>

  <div class="insight-box gold">
    <strong>핵심 결론</strong> — FILA는 신발 헤리티지에서 파생된 <strong>디자인 강점(+0.611)</strong>과 높은 평균 평점(4.88)을 보유하고 있으나,
    <strong>기능성(+0.382)</strong>과 <strong>소재/내구성(+0.277)</strong>에서 경쟁사 대비 유의미한 격차가 존재한다.
    이 격차를 좁히고, 경쟁사들이 공통으로 취약한 <strong>핏/사이즈 Unmet Need</strong>를 선점하는 것이
    FILA 애슬레저 성공의 핵심 조건이다.
  </div>

  <p>본 보고서는 국내 주요 애슬레저 4개 브랜드(젝시믹스·안다르·룰루레몬·FILA)의 소비자 리뷰 데이터를
  다층적으로 분석하여 FILA 애슬레저 시장 진입을 위한 데이터 기반 전략을 제시한다.</p>

  <h2 class="sub-title">3가지 전략 방향</h2>
  <table>
    <tr>
      <th style="width:5%">#</th>
      <th style="width:30%">전략</th>
      <th>실행 방향</th>
      <th style="width:18%">기대 효과</th>
    </tr>
    <tr>
      <td style="text-align:center;font-weight:800;color:#003087">①</td>
      <td><strong>핏/사이즈 Unmet Need 선점</strong></td>
      <td>전체 1위 토픽(163,711건, 핏/사이즈) 해소 → 체형 맞춤 핏 솔루션</td>
      <td style="text-align:center">고객 이탈 방어 + 초기 충성고객 확보</td>
    </tr>
    <tr>
      <td style="text-align:center;font-weight:800;color:#c0392b">②</td>
      <td><strong>디자인 헤리티지 → 의류 전이</strong></td>
      <td>신발 디자인 PMI 전이 효과(Gap +0.273) 활용 → 헤리티지 컬렉션</td>
      <td style="text-align:center">브랜드 인지도 제고 + 차별화</td>
    </tr>
    <tr>
      <td style="text-align:center;font-weight:800;color:#27ae60">③</td>
      <td><strong>기능성 격차 해소</strong></td>
      <td>룰루레몬 대비 -0.292 gap 해소 → 소재 R&amp;D + Tech 라인</td>
      <td style="text-align:center">중장기 프리미엄 포지셔닝</td>
    </tr>
  </table>
</section>


<!-- ═══════════════════════════════════════════════════════════
     1. 시장 현황
═══════════════════════════════════════════════════════════ -->
<section class="page-break">
  <h1 class="section-title">1. 시장 현황 및 경쟁 구도</h1>

  <h2 class="sub-title">1.1 브랜드별 매출 현황</h2>
  <div class="chart-wrap">{sale_svg}</div>
  <p class="chart-caption">단위: 억 원 | 룰루레몬 2025년 추산(*) | 출처: 각사 공시 및 업계 추정</p>

  <table>
    <tr>
      <th>브랜드</th>
      <th>2023</th>
      <th>2024</th>
      <th>2025(E)</th>
      <th>YoY (25 vs 24)</th>
      <th>시장점유율</th>
      <th>평균 평점</th>
    </tr>
    <tr>
      <td class="brand-name fila">FILA</td>
      <td class="num">4,536</td>
      <td class="num">4,869</td>
      <td class="num">5,127</td>
      <td class="num pos">+5.3%</td>
      <td class="num">32.0%</td>
      <td class="num">4.88</td>
    </tr>
    <tr>
      <td class="brand-name" style="color:#D4000F">안다르</td>
      <td class="num">1,013</td>
      <td class="num">1,453</td>
      <td class="num">1,842</td>
      <td class="num pos">+26.7%</td>
      <td class="num">11.5%</td>
      <td class="num">4.78</td>
    </tr>
    <tr>
      <td class="brand-name" style="color:#E0561A">젝시믹스</td>
      <td class="num">2,243</td>
      <td class="num">2,184</td>
      <td class="num">2,180</td>
      <td class="num neg">-0.2%</td>
      <td class="num">13.6%</td>
      <td class="num">4.92</td>
    </tr>
    <tr>
      <td class="brand-name" style="color:#1565C0">룰루레몬</td>
      <td class="num">1,177</td>
      <td class="num">1,567</td>
      <td class="num">2,093*</td>
      <td class="num pos">+33.6%</td>
      <td class="num">13.0%</td>
      <td class="num">4.83</td>
    </tr>
  </table>

  <div class="two-col">
    <div>
      <div class="insight-box red">
        <strong>젝시믹스 경고 신호</strong> — YoY -0.2% 정체. 기능성 중심 포지셔닝의 한계 도달.
        핏/사이즈 불만 축적이 이탈 원인으로 추정.
      </div>
    </div>
    <div>
      <div class="insight-box green">
        <strong>룰루레몬 고성장</strong> — +33.6% 고성장. 프리미엄 기능성 + 브랜드 경험 결합 전략이
        소비자 충성도로 이어지는 패턴 확인.
      </div>
    </div>
  </div>

  <h2 class="sub-title">1.2 분석 방법론 및 데이터</h2>
  <table>
    <tr><th style="width:30%">분석 단계</th><th>방법론</th><th>규모</th></tr>
    <tr><td>전처리</td><td>Kiwi 형태소 분석 + 애슬레저 도메인 사전</td><td>1,168,758 리뷰 (preprocessed_absa.parquet)</td></tr>
    <tr><td>토픽 모델링 (전체)</td><td>BERTopic (ko-sroberta-multitask + HDBSCAN + c-TF-IDF)</td><td>49개 토픽 / 1,110,129 리뷰</td></tr>
    <tr><td>토픽 모델링 (저평점)</td><td>저평점(1~2점) 별도 BERTopic 모델</td><td>30개 토픽 / 9,445 리뷰</td></tr>
    <tr><td>감성 분석</td><td>EXAONE 3.5 7.8B Ollama 로컬 + 6속성 Few-shot ABSA</td><td>29,070건 추론 (12,056 균형 + 17,014 FILA 보완)</td></tr>
    <tr><td>검증</td><td>Macro F1 = 0.7032 / Cohen's κ = 0.7141</td><td>973건 홀드아웃</td></tr>
    <tr><td>포지셔닝</td><td>ABSA 6속성 → 2D 좌표계 (기능성 × 브랜드 헤리티지)</td><td>4브랜드</td></tr>
  </table>
</section>


<!-- ═══════════════════════════════════════════════════════════
     2. 소비자 인식 분석 (BERTopic + ABSA)
═══════════════════════════════════════════════════════════ -->
<section class="page-break">
  <h1 class="section-title">2. 소비자 인식 분석</h1>

  <h2 class="sub-title">2.1 BERTopic — 핵심 토픽 분포 (49개 토픽, 2026-05-12 최신)</h2>
  <table>
    <tr>
      <th style="width:5%">순위</th>
      <th style="width:35%">토픽명</th>
      <th style="width:18%">속성 분류</th>
      <th style="width:10%">리뷰 수</th>
      <th>주요 키워드</th>
    </tr>
    <tr>
      <td style="text-align:center">1</td>
      <td><strong>[사이즈/핏] 하의, 색상, 크다</strong></td>
      <td style="text-align:center"><span class="badge red">핏/사이즈</span></td>
      <td style="text-align:right">163,711</td>
      <td>가격대비맘, 힙함, 부츠안, 흰색스커트, 가격대비원단</td>
    </tr>
    <tr>
      <td style="text-align:center">2</td>
      <td>[기능성] 운동, 색상, 러닝</td>
      <td style="text-align:center"><span class="badge">기능성</span></td>
      <td style="text-align:right">56,873</td>
      <td>런부스트레이서백, 런부스트포켓, 흰색계열, 사주</td>
    </tr>
    <tr>
      <td style="text-align:center">3</td>
      <td>[사이즈/핏] 팬티, 착용감, 하의</td>
      <td style="text-align:center"><span class="badge red">핏/사이즈</span></td>
      <td style="text-align:right">47,680</td>
      <td>흠집, 3부레깅스, 라벨시그니처, 라인자국</td>
    </tr>
    <tr>
      <td style="text-align:center">4</td>
      <td>[소재] 착용감, 색상, 소재</td>
      <td style="text-align:center"><span class="badge gold">소재/내구성</span></td>
      <td style="text-align:right">43,353</td>
      <td>가리지못하다, 서스테이너블라운드, 석유냄새</td>
    </tr>
    <tr>
      <td style="text-align:center">5</td>
      <td>[기능성] 시원하다, 여름, 소재</td>
      <td style="text-align:center"><span class="badge">기능성</span></td>
      <td style="text-align:right">41,176</td>
      <td>흐늘거리다, 휴대폰주머니, 힙업되, 휴가철</td>
    </tr>
  </table>
  <p class="footnote">* 49개 토픽 / 1,110,129건 (노이즈 토픽 -1 제외 676,951건 기준). 핏/사이즈 합산 232,759건(1·3위), 기능성 합산 98,049건(2·5위).</p>

  <div class="insight-box">
    <strong>전체 시장 속성 분포</strong> — 핏/사이즈 <strong>42.1%</strong> | 기능성 29.2% | 소재/내구성 16.1% | 디자인 10.8% | 가격/가치 1.1% | 품질/내구성 0.6%.
    핏·기능성 두 축이 전체 발화의 <strong>71%</strong> 점유 — 의류 시장 진입 시 두 축 동시 충족이 필수 조건.
  </div>

  <div class="insight-box red">
    <strong>FILA의 토픽 구조 진단 (12,553건)</strong> —
    핏/사이즈 48.9% / 소재 21.0% / 디자인 18.9% / <strong>기능성 8.3%</strong>.
    시장 평균 기능성 비중 <strong>29.2%</strong> 대비 약 <strong>1/3 수준</strong>으로 의류 기능성 담론에서 빈자리.
    또한 FILA 1위 토픽이 <strong>"[사이즈/핏] 슈즈, 양말, 삭스" (신발 카테고리, 4,739건)</strong> — 의류 토픽으로의 자연 전이가 약함.
  </div>

  <div class="insight-box gold">
    <strong>저평점 9,445건 클러스터링 (별도 BERTopic 모델, 30토픽)</strong> —
    핏/사이즈 <strong>46.4%</strong> + 품질/내구성 <strong>36.8%</strong> = 합산 <strong>83%</strong>가 저평점 원인.
    Top 토픽: [사이즈/핏] 교환·작다·반품(3,195건) → [기능성] 보풀·세탁·양말(1,155건) → [사이즈/핏] 크다·불편·가슴(673건).
    <strong>의류 진입 시 사이즈 표 정확화 + 세탁 후 형태 안정성이 1순위 방어선</strong>.
  </div>

  <h3 class="label">브랜드별 BERTopic Aspect 비중 (균형 213K 샘플 기준)</h3>
  <table>
    <tr>
      <th>브랜드</th>
      <th>핏/사이즈</th>
      <th>기능성</th>
      <th>소재/내구성</th>
      <th>디자인</th>
      <th>가격/가치</th>
      <th>품질/내구성</th>
    </tr>
    <tr>
      <td class="brand-name" style="color:#003087">FILA</td>
      <td class="num">44.2%</td>
      <td class="num neg">9.7%</td>
      <td class="num">22.8%</td>
      <td class="num pos">19.5%</td>
      <td class="num">2.1%</td>
      <td class="num">1.8%</td>
    </tr>
    <tr>
      <td class="brand-name">안다르</td>
      <td class="num pos">55.6%</td>
      <td class="num">27.2%</td>
      <td class="num">11.7%</td>
      <td class="num">3.6%</td>
      <td class="num">0.7%</td>
      <td class="num">1.2%</td>
    </tr>
    <tr>
      <td class="brand-name">젝시믹스</td>
      <td class="num">24.8%</td>
      <td class="num">33.9%</td>
      <td class="num pos">25.3%</td>
      <td class="num">12.8%</td>
      <td class="num">1.6%</td>
      <td class="num">1.7%</td>
    </tr>
    <tr>
      <td class="brand-name">룰루레몬</td>
      <td class="num">24.9%</td>
      <td class="num pos">46.7%</td>
      <td class="num">19.9%</td>
      <td class="num">6.1%</td>
      <td class="num">0.9%</td>
      <td class="num">1.5%</td>
    </tr>
  </table>
  <p class="footnote">* 노이즈 토픽 제외, 브랜드별 행 합계 100%. 빨강=시장 평균 대비 현저히 낮음 / 초록=상대적 강점.</p>

  <div class="insight-box red">
    <strong>FILA vs 룰루레몬 — 의류 담론 구조의 정반대</strong> —
    룰루레몬은 기능성 발화 <strong>46.7%</strong>로 1위 / FILA는 <strong>9.7%</strong>로 4브랜드 중 최저.
    반대로 FILA는 디자인 발화 <strong>19.5%</strong>로 1위 (룰루레몬 6.1%, 안다르 3.6%). 진입 시 옵션:
    (A) 디자인 강점 유지 + 기능성 메시지 R&D 강화 / (B) 기능성 진입 후 디자인은 헤리티지로 차별화.
  </div>

  <h2 class="sub-title">2.2 ABSA — 브랜드×속성 감성 점수 (Sentiment = P - N)</h2>
  <div class="chart-wrap">{bar_svg}</div>
  <p class="chart-caption">Sentiment Score = 긍정 비율(P) − 부정 비율(N) | 균형 샘플: 4브랜드 × 3,014건</p>

  <table>
    <tr>
      <th>브랜드</th>
      <th>핏/사이즈</th>
      <th>소재/내구성</th>
      <th>기능성</th>
      <th>디자인</th>
      <th>브랜드/헤리티지</th>
      <th>가격/가치</th>
    </tr>
    {"".join(
      f'<tr><td class="brand-name" style="color:{BRAND_COLORS[b]}">{b}</td>'
      + "".join(
        f'<td class="{"score-high" if v >= 0.6 else "score-mid" if v >= 0.4 else "score-low"}">{v:+.3f}</td>'
        for v in SENTIMENT[b].values()
      )
      + "</tr>"
      for b in BRANDS
    )}
  </table>
  <p class="footnote">색상: 초록(≥0.6 강점) / 노랑(0.4~0.6 중간) / 빨강(&lt;0.4 약점)</p>

  <h3 class="label">브랜드별 핵심 인사이트</h3>
  <div class="two-col">
    <div>
      <div class="insight-box">
        <strong>FILA</strong> — 디자인(+0.611)이 경쟁사 대비 압도적 강점.
        기능성(+0.382)·소재(+0.277)는 4개 브랜드 중 최저.
        브랜드 헤리티지(+0.388)는 젝시믹스보다 높음.
      </div>
      <div class="insight-box red">
        <strong>젝시믹스</strong> — 기능성(+0.566)에서 강점이나 브랜드 헤리티지(+0.302)가 가장 낮음.
        소비자가 "가성비 기능복"으로 인식 — 프리미엄 전환 어려움.
      </div>
    </div>
    <div>
      <div class="insight-box green">
        <strong>룰루레몬</strong> — 기능성(+0.674), 소재(+0.553), 브랜드(+0.487) 전 항목 1위.
        단, 가격/가치(+0.104)가 가장 낮음 — 가격 저항감 존재.
      </div>
      <div class="insight-box">
        <strong>안다르</strong> — 핏/사이즈(+0.839) 1위 + 브랜드(+0.456) 강세.
        기능성(+0.597) 준수. 디자인(+0.392)은 약점.
        "실용적 국내 프리미엄"으로 빠르게 성장 중.
      </div>
    </div>
  </div>
</section>


<!-- ═══════════════════════════════════════════════════════════
     3. FILA 브랜드 에퀴티 진단
═══════════════════════════════════════════════════════════ -->
<section class="page-break">
  <h1 class="section-title">3. FILA 브랜드 에퀴티 진단</h1>

  <h2 class="sub-title">3.1 신발 → 의류 Spillover Gap 분석</h2>
  <p>FILA 신발 리뷰와 의류 리뷰를 속성별로 비교하여 PMI(Pointwise Mutual Information) 기반
  브랜드 전이 가능성을 분석했다.</p>

  <table>
    <tr><th>속성</th><th>신발 Score</th><th>의류 Score</th><th>Spillover Gap (의류 - 신발)</th><th>해석</th></tr>
    <tr>
      <td>디자인</td>
      <td class="num">0.611</td>
      <td class="num">0.884</td>
      <td class="num pos">+0.273</td>
      <td><strong>전이 가능성 최고</strong> — 신발 디자인 팬이 의류 디자인도 기대</td>
    </tr>
    <tr>
      <td>브랜드/헤리티지</td>
      <td class="num">0.388</td>
      <td class="num">0.512</td>
      <td class="num pos">+0.124</td>
      <td>로고·감성 언급이 의류에서도 증가</td>
    </tr>
    <tr>
      <td>핏/사이즈</td>
      <td class="num">0.732</td>
      <td class="num">0.659</td>
      <td class="num neg">-0.073</td>
      <td>의류에서 핏 관련 불만 상대적 증가</td>
    </tr>
    <tr>
      <td>기능성</td>
      <td class="num">0.382</td>
      <td class="num">0.298</td>
      <td class="num neg">-0.084</td>
      <td>의류에서 기능성 약점 더욱 부각</td>
    </tr>
  </table>

  <div class="insight-box gold">
    <strong>전략적 시사점</strong> — 디자인(+0.273 gap)과 브랜드 헤리티지(+0.124 gap)는 신발→의류 자연스러운 전이가 가능.
    반면 기능성(-0.084)과 핏(-0.073)은 의류에서 더 취약해지는 속성 — 별도 투자 필요.
  </div>

  <h2 class="sub-title">3.2 FILA 강약점 요약</h2>
  <div class="two-col">
    <div>
      <h3 class="label">강점 (Strength)</h3>
      <ul class="body-list">
        <li><strong>디자인 감성</strong> — +0.611 (경쟁사 최고 수준, 안다르 +0.392 대비 +0.219)</li>
        <li><strong>신발 헤리티지 브랜드 자산</strong> — 1991년 이탈리아 헤리티지 + 테니스·농구 레거시</li>
        <li><strong>高평점</strong> — 4.88점, 기존 고객 만족도 견조</li>
        <li><strong>대형 유통 채널</strong> — 시장점유율 32%, 오프라인 접점 우위</li>
      </ul>
    </div>
    <div>
      <h3 class="label">약점 (Weakness)</h3>
      <ul class="body-list">
        <li><strong>기능성 최저</strong> — +0.382 (룰루레몬 +0.674 대비 -0.292 gap)</li>
        <li><strong>소재/내구성 최저</strong> — +0.277 (룰루레몬 +0.553 대비 -0.276 gap)</li>
        <li><strong>애슬레저 전문 인식 부족</strong> — "패션 브랜드"로의 소비자 고정관념</li>
        <li><strong>의류 핏 약점</strong> — 신발 대비 핏 점수 하락(-0.073)</li>
      </ul>
    </div>
  </div>
</section>


<!-- ═══════════════════════════════════════════════════════════
     4. 2D 포지셔닝 맵 + White Space
═══════════════════════════════════════════════════════════ -->
<section class="page-break">
  <h1 class="section-title">4. 브랜드 포지셔닝 맵 &amp; White Space</h1>

  <div class="two-col" style="align-items:flex-start">
    <div style="flex:1.1">
      <div class="chart-wrap">{pos_svg}</div>
      <p class="chart-caption">X축: 기능성 Sentiment Score | Y축: 브랜드/헤리티지 Score<br/>
      원 크기: FILA 진입 목표 포지션(Yellow = White Space)</p>
    </div>
    <div style="flex:0.9">
      <h2 class="sub-title">브랜드별 포지션</h2>
      <table>
        <tr><th>브랜드</th><th>기능성</th><th>헤리티지</th><th>포지션</th></tr>
        <tr>
          <td style="color:#1565C0;font-weight:700">룰루레몬</td>
          <td style="text-align:center">0.674</td>
          <td style="text-align:center">0.487</td>
          <td>프리미엄 기능+브랜드</td>
        </tr>
        <tr>
          <td style="color:#D4000F;font-weight:700">안다르</td>
          <td style="text-align:center">0.597</td>
          <td style="text-align:center">0.456</td>
          <td>국내 프리미엄</td>
        </tr>
        <tr>
          <td style="color:#E0561A;font-weight:700">젝시믹스</td>
          <td style="text-align:center">0.566</td>
          <td style="text-align:center">0.302</td>
          <td>가성비 기능복</td>
        </tr>
        <tr>
          <td style="color:#003087;font-weight:700">FILA (현재)</td>
          <td style="text-align:center">0.382</td>
          <td style="text-align:center">0.388</td>
          <td>브랜드 미활용</td>
        </tr>
      </table>

      <div class="insight-box gold" style="margin-top:16px">
        <strong>White Space (X≈0.55, Y≈0.43)</strong><br/>
        룰루레몬과 직접 충돌 없는 중강도 기능성 + 헤리티지 축.
        안다르·젝시믹스보다 강한 브랜드 인식, 룰루레몬보다 접근 가능한 가격대.
        FILA 기존 신발 팬베이스가 자연스럽게 유입 가능한 포지션.
      </div>

      <h3 class="label">현재 → 목표 이동 벡터</h3>
      <table>
        <tr><th>축</th><th>현재</th><th>목표</th><th>변화량</th></tr>
        <tr>
          <td>기능성 (X)</td>
          <td class="num">0.382</td>
          <td class="num">0.550</td>
          <td class="num pos">+0.168</td>
        </tr>
        <tr>
          <td>헤리티지 (Y)</td>
          <td class="num">0.388</td>
          <td class="num">0.430</td>
          <td class="num pos">+0.042</td>
        </tr>
      </table>
    </div>
  </div>
</section>


<!-- ═══════════════════════════════════════════════════════════
     5. 전략적 제언
═══════════════════════════════════════════════════════════ -->
<section class="page-break">
  <h1 class="section-title">5. 전략적 제언 (Actionable Recommendations)</h1>

  <!-- 전략 1 -->
  <div class="strategy-card">
    <div>
      <span class="strategy-num">①</span>
      <span class="strategy-title">핏/사이즈 Unmet Need 선점 — "맞는 옷" 포지셔닝</span>
    </div>
    <div class="strategy-sub">기회: BERTopic 1·2위 토픽 합산 183,070건 | 경쟁사 공통 약점</div>
    <div class="strategy-body">
      <strong>배경:</strong> 상위 2개 BERTopic이 모두 핏/사이즈 관련이며,
      소비자들이 가장 많이 언급하는 불만. 경쟁사들(젝시믹스, 안다르 포함)도 해결하지 못한 Unmet Need.<br/><br/>
      <strong>실행:</strong><br/>
      • 체형 데이터 기반 AI 사이즈 추천 시스템 도입 (신발 사이즈 알고리즘 → 의류 전환)<br/>
      • 다양한 체형 범위(XS~3XL) + 키/몸무게별 핏 가이드 상세화<br/>
      • 하의 라인 집중 개발 (1위 토픽: 하의·바지·슬랙스)<br/>
      • 무료 반품 정책 + 사이즈 교환 간소화<br/><br/>
      <strong>KPI:</strong> 핏/사이즈 Sentiment Score +0.739 → +0.85 이상, 반품률 감소
    </div>
  </div>

  <!-- 전략 2 -->
  <div class="strategy-card">
    <div>
      <span class="strategy-num" style="background:#c0392b">②</span>
      <span class="strategy-title">디자인 헤리티지 전이 — "Heritage Athleisure" 컬렉션</span>
    </div>
    <div class="strategy-sub">기회: FILA 디자인 Spillover Gap +0.273 | 경쟁사 대비 디자인 강점 +0.219</div>
    <div class="strategy-body">
      <strong>배경:</strong> FILA 디자인 감성(+0.611)이 경쟁사(젝시믹스 +0.405, 안다르 +0.392) 대비
      압도적으로 높으며, 신발→의류 PMI 분석에서 디자인 전이 가능성이 가장 큰 속성(Gap +0.273)으로 확인.<br/><br/>
      <strong>실행:</strong><br/>
      • 신발 시그니처 디자인 요소(F-box 로고, 컬러 배합) → 의류 라인 연계<br/>
      • 테니스·농구 헤리티지 → 스포츠 레트로 감성 의류 시리즈 출시<br/>
      • 인플루언서 콜라보 시리즈 (스트리트·스포츠 크로스오버)<br/>
      • "신발+의류 세트룩" 마케팅 콘텐츠로 기존 신발 팬베이스 유입<br/><br/>
      <strong>KPI:</strong> 디자인 언급 리뷰 비중 증가, 의류 첫 구매 전환율 상승
    </div>
  </div>

  <!-- 전략 3 -->
  <div class="strategy-card">
    <div>
      <span class="strategy-num" style="background:#27ae60">③</span>
      <span class="strategy-title">기능성 격차 해소 — "FILA TECH" 소재 기술 라인</span>
    </div>
    <div class="strategy-sub">과제: 기능성 Gap -0.292 (룰루레몬 대비) | 소재/내구성 Gap -0.276</div>
    <div class="strategy-body">
      <strong>배경:</strong> 기능성(+0.382)과 소재/내구성(+0.277)이 경쟁사 대비 최저치.
      White Space 목표 포지션(기능성 0.55) 도달을 위해 +0.168 향상이 필요.
      단기적으로는 마케팅으로 인식을 개선하되, 중기적으로는 소재 R&amp;D 투자가 필수.<br/><br/>
      <strong>실행:</strong><br/>
      • FILA TECH 서브라인 론칭: 흡습속건·4-way stretch·항균 소재 중심<br/>
      • 운동 종목별(요가/러닝/필라테스) 특화 기능 설계 + 상세 스펙 표기<br/>
      • 소재 품질 인증 취득 및 제품 페이지에 기능 영상 콘텐츠 배치<br/>
      • 기존 신발 성능 R&amp;D 역량(충격흡수, 통기 기술)을 의류 소재로 연장<br/><br/>
      <strong>KPI:</strong> 기능성 Score +0.382 → +0.55, 소재 관련 긍정 리뷰 비율 향상
    </div>
  </div>
</section>


<!-- ═══════════════════════════════════════════════════════════
     6. 실행 로드맵
═══════════════════════════════════════════════════════════ -->
<section class="page-break">
  <h1 class="section-title">6. 실행 로드맵 &amp; 기대 성과</h1>

  <div class="roadmap">
    <div class="roadmap-phase">
      <div class="phase-badge">Phase 1 — 즉시 (0~6개월)</div>
      <h4>기반 구축</h4>
      <ul>
        <li>핏/사이즈 가이드 전면 개편</li>
        <li>무료 반품·사이즈 교환 정책</li>
        <li>신발 팬 대상 의류 크로스셀 캠페인</li>
        <li>Heritage 컬렉션 기획 착수</li>
        <li>소재 파트너십 협의</li>
      </ul>
    </div>
    <div class="roadmap-phase">
      <div class="phase-badge">Phase 2 — 단기 (6~18개월)</div>
      <h4>포지셔닝 확립</h4>
      <ul>
        <li>Heritage Athleisure 시리즈 론칭</li>
        <li>FILA TECH 기능성 서브라인 출시</li>
        <li>AI 사이즈 추천 베타 서비스</li>
        <li>스포츠 레트로 마케팅 캠페인</li>
        <li>인플루언서 콜라보 시리즈 3회</li>
      </ul>
    </div>
    <div class="roadmap-phase">
      <div class="phase-badge">Phase 3 — 중기 (18~36개월)</div>
      <h4>프리미엄 도달</h4>
      <ul>
        <li>기능성 Score 0.55 달성 목표</li>
        <li>White Space 포지션 안착</li>
        <li>애슬레저 전문 브랜드 인식 확립</li>
        <li>매출 애슬레저 비중 20%+ 목표</li>
        <li>글로벌 확장 기반 마련</li>
      </ul>
    </div>
  </div>

  <h2 class="sub-title">기대 성과 요약</h2>
  <table>
    <tr>
      <th>지표</th>
      <th>현재 (2025)</th>
      <th>목표 (2027)</th>
      <th>전략 레버</th>
    </tr>
    <tr>
      <td>기능성 Sentiment</td>
      <td class="num">+0.382</td>
      <td class="num pos">+0.55</td>
      <td>FILA TECH 소재 라인</td>
    </tr>
    <tr>
      <td>디자인 Sentiment</td>
      <td class="num">+0.611</td>
      <td class="num pos">+0.68</td>
      <td>Heritage 컬렉션 강화</td>
    </tr>
    <tr>
      <td>핏/사이즈 Sentiment</td>
      <td class="num">+0.732</td>
      <td class="num pos">+0.85</td>
      <td>AI 사이즈 추천 + 체형 다양화</td>
    </tr>
    <tr>
      <td>포지셔닝 좌표 (기능성)</td>
      <td class="num">X = 0.382</td>
      <td class="num pos">X = 0.55</td>
      <td>White Space 진입</td>
    </tr>
    <tr>
      <td>포지셔닝 좌표 (헤리티지)</td>
      <td class="num">Y = 0.388</td>
      <td class="num pos">Y = 0.43</td>
      <td>브랜드 마케팅 강화</td>
    </tr>
  </table>

  <div class="insight-box gold">
    <strong>종합 결론</strong> — FILA는 디자인과 브랜드 헤리티지라는 차별화된 자산을 보유하고 있으며,
    이를 기반으로 룰루레몬과 직접 경쟁하지 않는 <strong>"헤리티지 기능복" White Space</strong>를 선점할 수 있다.
    단기적으로는 핏/사이즈 Unmet Need 해소와 디자인 자산 활용으로 초기 팬베이스를 형성하고,
    중기적으로 기능성 R&amp;D 투자를 통해 진정한 애슬레저 브랜드로 진화하는 2단계 전략이 최적이다.
  </div>

  <p class="footnote" style="margin-top:24px">
    본 보고서는 소비자 리뷰 텍스트 데이터 기반 분석이며, 오프라인 판매 데이터·생산비용·유통 마진 등은 미반영.
    전략 수립 시 재무 타당성 및 시장조사 데이터와 병행 검토를 권장.
    분석 기준일: 2026년 5월.
  </p>
</section>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# PDF 변환 (playwright)
# ─────────────────────────────────────────────────────────────
def generate_pdf():
    from playwright.sync_api import sync_playwright

    print("[1/2] HTML 보고서 빌드 중...")
    html = build_html()

    print("[2/2] PDF 변환 중 (playwright chromium)...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(OUT_PDF),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()

    print(f"\n✓ 저장 완료: {OUT_PDF}")
    print(f"  파일 크기: {OUT_PDF.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    generate_pdf()
