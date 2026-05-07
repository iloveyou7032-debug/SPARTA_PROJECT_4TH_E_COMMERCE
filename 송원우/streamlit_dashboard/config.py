"""
config.py — 대시보드 전역 설정
================================

브랜드 메타, 색상 팔레트, ABSA 속성, 임계값 등 모든 페이지·컴포넌트가
공유하는 상수의 단일 진실 공급원(Single Source of Truth).
"""
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 경로
# ─────────────────────────────────────────────────────────────
APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent.parent              # SPARTA_PROJECT_4TH_E_COMMERCE/
DATA_DIR = PROJECT_ROOT / "송원우" / "final_data"  # 실제 parquet 위치

# 데이터 파일명 (data contract — 모델팀과 합의)
PATHS = {
    "reviews":     DATA_DIR / "preprocessed_absa.parquet",
    "topics":      DATA_DIR / "topic_results.parquet",            # 미생성: 더미 사용
    "absa":        DATA_DIR / "absa_predictions_full.parquet",    # 미생성: 더미 사용
    "positioning": DATA_DIR / "positioning_scores.parquet",       # 미생성: 더미 사용
    "sna":         DATA_DIR / "sna_centrality.parquet",           # 미생성: 더미 사용
}

# ─────────────────────────────────────────────────────────────
# 브랜드 메타 — 자사/경쟁사 구분, 색상, 표시 이름
# ─────────────────────────────────────────────────────────────
BRANDS = {
    "FILA":   {"label": "휠라(FILA)",   "color": "#002663", "is_self": True},
    "안다르": {"label": "안다르",       "color": "#E60012", "is_self": False},
    "젝시믹스": {"label": "젝시믹스",   "color": "#FF6B35", "is_self": False},
    "룰루레몬": {"label": "룰루레몬",   "color": "#5B9BD5", "is_self": False},
}
BRAND_ORDER = ["FILA", "안다르", "젝시믹스", "룰루레몬"]
BRAND_COLORS = {b: m["color"] for b, m in BRANDS.items()}

# ─────────────────────────────────────────────────────────────
# ABSA 6속성 — 한글 ↔ 영문 키 매핑
# ─────────────────────────────────────────────────────────────
ASPECTS = [
    {"key": "fit_size",            "label": "핏/사이즈",       "axis": "x_supp"},
    {"key": "material_durability", "label": "소재/내구성",     "axis": "x_supp"},
    {"key": "functionality",       "label": "기능성",          "axis": "x_core"},
    {"key": "design",              "label": "디자인",          "axis": "y_supp"},
    {"key": "brand_heritage",      "label": "브랜드/헤리티지", "axis": "y_core"},
    {"key": "price_value",         "label": "가격/가치",       "axis": "supp"},
]
ASPECT_KEYS   = [a["key"] for a in ASPECTS]
ASPECT_LABELS = {a["key"]: a["label"] for a in ASPECTS}
LABEL_TO_KEY  = {a["label"]: a["key"] for a in ASPECTS}

SENTIMENT_LABELS = ["P", "N", "X"]   # Positive / Negative / 없음
SENTIMENT_COLOR  = {"P": "#2E7D32", "N": "#C62828", "X": "#9E9E9E"}

# ─────────────────────────────────────────────────────────────
# 시각화 임계값
# ─────────────────────────────────────────────────────────────
MIN_REVIEWS_FOR_BRAND_SCORE = 30   # 한 셀 미만 → graceful degradation
TOPIC_TOP_K_KEYWORDS = 8
POSITIONING_AXIS_RANGE = (0.0, 1.0)

# ─────────────────────────────────────────────────────────────
# 캐시 TTL (초) — 30분 기본
# ─────────────────────────────────────────────────────────────
CACHE_TTL = 1800

# ─────────────────────────────────────────────────────────────
# Streamlit page 레이아웃 공통
# ─────────────────────────────────────────────────────────────
PAGE_LAYOUT = {
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

APP_TITLE = "FILA 애슬레저 시장 진입 전략 대시보드"
APP_SUBTITLE = "117만 건 리뷰 기반 — 기능성 × 헤리티지 포지셔닝"
