"""
run_phase2_pipeline.py — Phase 2 End-to-End Pipeline (1-click)
=================================================================

흐름 (라벨러1 작업 완료 후 1회 실행):
  Step 1. apply_relabel_v24      — v2.3 + 라벨러1 _NEW = v2.4 골든셋
  Step 2. v10 974건 검증셋 추론   — ~30분 (M4 Pro), 캐시 시 즉시
  Step 3. F1 측정 + v9 baseline 대비 Δ + 속성별 비교
  Step 4. 분기 자동 판정          — A(≥0.78) / B(0.74~0.78) / C(<0.74)

Usage:
  uv run python run_phase2_pipeline.py
  uv run python run_phase2_pipeline.py --relabeled custom_path.xlsx
  uv run python run_phase2_pipeline.py --rebuild-cache    # v10 재추론 강제
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ABSA_DIR = Path(__file__).resolve().parent
if str(ABSA_DIR) not in sys.path:
    sys.path.insert(0, str(ABSA_DIR))

import apply_relabel_v24 as ar
import absa_v10 as v10
from absa_v9 import (
    ASPECTS, LABELS,
    build_few_shot_examples, build_batch_examples, predict_one,
)

V10_PRED_CACHE = ABSA_DIR / "absa_v10_validation_predictions.parquet"
SEED = 42

# v9 baseline (974건 검증셋 기준, 진행보고 기록)
V9_BASELINE = 0.7032
V9_PER_ASPECT = {
    "핏/사이즈":      0.6107,
    "소재/내구성":    0.7831,
    "기능성":         0.7322,
    "디자인":         0.7432,
    "브랜드/헤리티지": 0.6019,
    "가격/가치":      0.7478,
}


# ─────────────────────────────────────────────────────────────
# Step 1
# ─────────────────────────────────────────────────────────────
def step1_build_v24(relabeled_path: Path) -> bool:
    print("\n" + "█" * 70)
    print("█  Step 1 / 4 — v2.4 골든셋 빌드")
    print("█" * 70)
    return ar.main(relabeled_path, ar.GOLDEN_V23, ar.GOLDEN_V24)


# ─────────────────────────────────────────────────────────────
# Step 2 — v10 추론
# ─────────────────────────────────────────────────────────────
def step2_v10_inference(rebuild: bool = False) -> pd.DataFrame:
    print("\n" + "█" * 70)
    print("█  Step 2 / 4 — v10 검증셋 974건 추론")
    print("█" * 70)

    if V10_PRED_CACHE.exists() and not rebuild:
        print(f"  cache 사용: {V10_PRED_CACHE.name}")
        return pd.read_parquet(V10_PRED_CACHE)

    golden = v10.load_golden_set()
    fs = build_few_shot_examples(golden, n_per_class=3, seed=SEED)
    fs_contents = {ex_c for fs_list in fs.values() for ex_c, _ in fs_list}
    val = golden[~golden["content_clean"].isin(fs_contents)].reset_index(drop=True)
    print(f"  검증셋: {len(val)}건 (Few-shot {len(fs_contents)}건 제외)")
    print(f"  v2.4 기반 Few-shot 자동 재선정됨")

    batch = build_batch_examples(golden, n_examples=6, seed=SEED)

    try:
        from tqdm import tqdm
        it = tqdm(val.iterrows(), total=len(val), desc="v10 추론")
    except ImportError:
        it = val.iterrows()

    preds = []
    start = time.time()
    for _, r in it:
        preds.append(predict_one(
            str(r["content_clean"]),
            str(r.get("tokens", "")),
            batch,
        ))
    elapsed = time.time() - start

    out = val[["sample_idx", "review_id", "content_clean"]].copy()
    for asp in ASPECTS:
        out[f"{asp}_pred"] = [p[asp] for p in preds]
    out.to_parquet(V10_PRED_CACHE, index=False)
    print(f"\n  완료: {len(out)}건 / {elapsed:.0f}s / {elapsed/len(out):.2f}s/건")
    print(f"  cache 저장: {V10_PRED_CACHE.name}")
    return out


# ─────────────────────────────────────────────────────────────
# Step 3 — F1 측정
# ─────────────────────────────────────────────────────────────
def step3_evaluate(pred_df: pd.DataFrame) -> dict:
    from sklearn.metrics import f1_score, classification_report

    print("\n" + "█" * 70)
    print("█  Step 3 / 4 — F1 측정 + v9 baseline 대비")
    print("█" * 70)

    golden = v10.load_golden_set()
    merged = pred_df.merge(
        golden[["sample_idx"] + ASPECTS],
        on="sample_idx", how="inner",
    )
    print(f"  매칭 {len(merged)}건")

    f1_per: dict[str, float] = {}
    for asp in ASPECTS:
        y_true = merged[asp].astype(str).str.upper()
        y_pred = merged[f"{asp}_pred"].astype(str).str.upper()
        f1 = f1_score(y_true, y_pred, average="macro", labels=LABELS, zero_division=0)
        f1_per[asp] = float(f1)
    macro = sum(f1_per.values()) / len(f1_per)
    delta = macro - V9_BASELINE

    print()
    print("=" * 70)
    print(f"  v10 Macro F1 = {macro:.4f}")
    print(f"  v9 baseline  = {V9_BASELINE:.4f}")
    sign = "+" if delta >= 0 else ""
    print(f"  Δ            = {sign}{delta:.4f}")
    print("=" * 70)

    print("\n  [속성별 F1 — v10 vs v9]")
    for asp in ASPECTS:
        v10f = f1_per[asp]
        v9f = V9_PER_ASPECT[asp]
        d = v10f - v9f
        flag = "✅" if d >= 0.02 else ("≈" if abs(d) < 0.02 else "❌")
        print(f"    {asp:>14s}  v10={v10f:.4f}  v9={v9f:.4f}  Δ={d:+.4f}  {flag}")

    return {"macro_f1": macro, "per_aspect": f1_per, "delta": delta, "merged": merged}


# ─────────────────────────────────────────────────────────────
# Step 4 — 분기
# ─────────────────────────────────────────────────────────────
def step4_branch(eval_result: dict) -> str:
    print("\n" + "█" * 70)
    print("█  Step 4 / 4 — 결과 분기 자동 판정")
    print("█" * 70)
    f1 = eval_result["macro_f1"]
    per = eval_result["per_aspect"]

    핏 = per["핏/사이즈"]
    브 = per["브랜드/헤리티지"]
    핏_d = 핏 - V9_PER_ASPECT["핏/사이즈"]
    브_d = 브 - V9_PER_ASPECT["브랜드/헤리티지"]

    if f1 >= 0.78:
        scenario = "A"
        print(f"\n  ✅ 시나리오 A — Macro F1 {f1:.4f} ≥ 0.78")
        print(f"     핏/사이즈 Δ {핏_d:+.4f} / 브랜드 Δ {브_d:+.4f}")
        print()
        print(f"  [다음 단계]")
        print(f"  1. Phase E 12,056 + complement 17,014 = 29,070건 v10 재추론 (~10시간 M4 Pro)")
        print(f"     → absa_phase_e_predictions.parquet / absa_fila_complement_predictions.parquet")
        print(f"       파일 교체만으로 대시보드 자동 갱신 (코드 무수정)")
        print(f"  2. 포지셔닝 좌표 재산출 (특히 FILA Y축 헤리티지 변동 확인)")
        print(f"  3. C-Level 보고서 정합성 재검토")
    elif f1 >= 0.74:
        scenario = "B"
        print(f"\n  ⚠️  시나리오 B — Macro F1 {f1:.4f} (0.74 ~ 0.78)")
        print(f"     핏/사이즈 Δ {핏_d:+.4f} / 브랜드 Δ {브_d:+.4f}")
        print()
        print(f"  [추가 옵션]")
        print(f"  1. per-aspect 분리 프롬프트 샌드박스 (1~2일, 격리)")
        print(f"     → zero-sum trade-off 깨기 시도")
        print(f"  2. boundary 100건 추가 재라벨링 (라벨러1 + 송원우 합의)")
        print(f"  3. Phase E 부분 재추론으로 인사이트 변동만 우선 확인")
    else:
        scenario = "C"
        print(f"\n  ❌ 시나리오 C — Macro F1 {f1:.4f} < 0.74")
        print(f"     예상 외 결과 — 라벨러1 _NEW 라벨 자체 점검 필요할 수 있음")
        print()
        print(f"  [긴급 검토]")
        print(f"  1. v23 vs v24 변경량 리포트 재확인 (특정 속성에서 과변경?)")
        print(f"  2. Cohen's κ 재측정 (라벨러1 vs 송원우 spot-check 30건)")
        print(f"  3. LoRA fine-tuning 또는 라벨러2 합류 IAA 강화 검토")

    return scenario


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main(relabeled_path: Path, rebuild_cache: bool = False) -> None:
    overall_start = time.time()
    print("\n" + "█" * 70)
    print("█  Phase 2 End-to-End Pipeline")
    print("█  라벨러1 _NEW → v2.4 → v10 추론 → F1 → 분기")
    print("█" * 70)

    if not step1_build_v24(relabeled_path):
        print("\n[abort] Step 1 실패 — Pipeline 중단")
        sys.exit(1)

    pred = step2_v10_inference(rebuild=rebuild_cache)
    result = step3_evaluate(pred)
    scenario = step4_branch(result)

    elapsed = time.time() - overall_start
    print()
    print("=" * 70)
    print(f"Pipeline 완료 — 총 소요 {elapsed:.0f}초 / 시나리오 {scenario}")
    print(f"산출:")
    print(f"  - {ar.GOLDEN_V24.name}")
    print(f"  - {V10_PRED_CACHE.name}")
    print("=" * 70)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Phase 2 End-to-End Pipeline")
    p.add_argument("--relabeled", default=str(ar.RELABEL_DEFAULT),
                   help="라벨러1 _NEW 작성 완료 Excel path")
    p.add_argument("--rebuild-cache", action="store_true",
                   help="v10 추론 캐시 무시하고 재추론 (Few-shot 변경 시 사용)")
    args = p.parse_args()
    main(Path(args.relabeled), rebuild_cache=args.rebuild_cache)
