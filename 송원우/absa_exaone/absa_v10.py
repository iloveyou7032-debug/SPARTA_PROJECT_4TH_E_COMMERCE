"""
absa_v10.py — Phase 2 GT v2.4 골든셋 사용 모델
=================================================

v9 대비 변경:
  - 골든셋 default path: v23 → v24 (라벨러1 boundary 150건 재라벨링 반영)
  - 그 외 로직(프롬프트/트리거/JSON Schema/후보정) 모두 v9 동일

설계 의도:
  Phase 2 첫 시도는 모델 변경 없이 데이터 품질만으로 F1 향상 검증.
  Few-shot 예시도 v2.4 골든셋에서 재선정되어 자동 갱신됨
  (build_few_shot_examples 호출 시 v24의 새 라벨 반영).

Usage (notebook):
  from absa_v10 import load_golden_set, predict_dataframe, evaluate
  golden = load_golden_set()  # v24 자동
  ...
"""
from __future__ import annotations

import sys
from pathlib import Path

ABSA_DIR = Path(__file__).resolve().parent
if str(ABSA_DIR) not in sys.path:
    sys.path.insert(0, str(ABSA_DIR))

# v9 로직 전부 재export (수정 없음)
from absa_v9 import (  # noqa: F401
    ASPECTS, LABELS,
    ASPECT_RULES, TRIGGERS_P, TRIGGERS_N,
    NEG_TONE_WORDS, WEAK_BRAND_P, _CORRECTION_SKIP,
    preprocess_texts,
    build_few_shot_examples, build_batch_examples,
    build_batch_prompt, parse_batch_response, call_exaone_batch,
    apply_trigger_correction,
    predict_one,
    evaluate, print_evaluation_report,
    diagnose_low_f1_aspect, extract_misclassified,
)
from absa_v9 import (
    load_golden_set as _load_golden_set_v9,
    predict_dataframe as _predict_dataframe_v9,
)

# v2.4 골든셋 path
V24_GOLDEN = ABSA_DIR / "absa_golden_set_1000_v24.xlsx"


def load_golden_set(path=None):
    """v9.load_golden_set 래퍼 — default를 v24로 변경.

    v24 미존재 시 명확한 에러 메시지 출력 (v23으로 fallback 안 함 — 의도적).
    """
    if path is None:
        path = V24_GOLDEN
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"v2.4 골든셋 미존재: {p}\n"
            f"  → 먼저 `python apply_relabel_v24.py` 실행하여 v24 빌드 필요."
        )
    return _load_golden_set_v9(str(p))


def predict_dataframe(df, few_shots, **kwargs):
    """v9 predict_dataframe 래퍼 — default golden_path만 v24."""
    kwargs.setdefault("golden_path", str(V24_GOLDEN))
    return _predict_dataframe_v9(df, few_shots, **kwargs)
