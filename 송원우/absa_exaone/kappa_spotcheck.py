"""
kappa_spotcheck.py — Spot-check 30건 결과 일치율(Agreement) + κ 측정
=====================================================================

입력:
  absa_spotcheck_30_completed.xlsx — 송원우_LABEL 작성 완료된 파일

출력:
  콘솔 — Agreement rate + 속성별 + 변경 방향별 + confusion matrix + 분기
  absa_spotcheck_30_kappa_report.xlsx — 분쟁 케이스 우선 정렬 + 요약

핵심 지표 — "라벨러1 동의 비율" (Agreement Rate, AR):
  추출된 30건은 모두 라벨러1이 X로 라벨한 케이스.
  → 송원우가 X로 응답한 비율 = 라벨러1 동의 비율
  → AR = (송원우=X) / 30
  Cohen's κ는 single-class 문제로 0에 수렴하므로 보조 지표로만 사용.

판정 기준 (AR 기반):
  AR ≥ 0.75 — H1 채택: v24 옳음 (라벨러1 적극 동의) → LoRA 경로
  AR 0.50~0.75 — 중간: 가이드라인 재정렬 + boundary 100건 추가 라벨링
  AR < 0.50 — H2 채택: 라벨러1 too strict → v23 baseline 유지 권장

Usage:
  uv run python kappa_spotcheck.py
  uv run python kappa_spotcheck.py --input custom_path.xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

ABSA_DIR = Path(__file__).resolve().parent

DEFAULT_INPUT  = ABSA_DIR / "absa_spotcheck_30_completed.xlsx"
DEFAULT_REPORT = ABSA_DIR / "absa_spotcheck_30_kappa_report.xlsx"
LABELS = ["P", "N", "X"]


# ─────────────────────────────────────────────────────────────
# 검증
# ─────────────────────────────────────────────────────────────
def validate(df: pd.DataFrame) -> bool:
    if "송원우_LABEL" not in df.columns:
        print(f"[abort] '송원우_LABEL' 컬럼 없음")
        return False

    df["송원우_LABEL"] = df["송원우_LABEL"].astype(str).str.strip().str.upper()
    blanks = df["송원우_LABEL"].isin(["", "NAN", "NONE"])
    if blanks.any():
        print(f"[abort] 송원우_LABEL 미작성 {blanks.sum()}건")
        if "spotcheck_id" in df.columns:
            print(f"  미작성 spotcheck_id: {df.loc[blanks, 'spotcheck_id'].tolist()}")
        return False

    invalid = ~df["송원우_LABEL"].isin(LABELS)
    if invalid.any():
        print(f"[abort] 송원우_LABEL 오타 {invalid.sum()}건 (P/N/X 만 허용)")
        if "spotcheck_id" in df.columns:
            print(df.loc[invalid, ["spotcheck_id", "송원우_LABEL"]].to_string(index=False))
        return False
    return True


# ─────────────────────────────────────────────────────────────
# 메인 측정 함수
# ─────────────────────────────────────────────────────────────
def measure(input_path: Path, report_path: Path) -> dict:
    print("=" * 70)
    print("[kappa_spotcheck] 라벨러1 vs 송원우 일치성 측정")
    print("=" * 70)
    print(f"\n입력: {input_path.name}")

    df = pd.read_excel(input_path, sheet_name="라벨링")
    print(f"  → {len(df)}건")

    if not validate(df):
        sys.exit(1)

    df["v24_라벨러1"] = df["v24_라벨러1"].astype(str).str.upper()
    df["v23_GOLD"]    = df["v23_GOLD"].astype(str).str.upper()

    y_label1 = df["v24_라벨러1"].tolist()
    y_swu    = df["송원우_LABEL"].tolist()

    overall_kappa = cohen_kappa_score(y_label1, y_swu, labels=LABELS)
    AR = (df["v24_라벨러1"] == df["송원우_LABEL"]).mean()
    n_x = int((df["송원우_LABEL"] == "X").sum())

    print()
    print("=" * 70)
    print(f"  Agreement Rate (AR) = {AR*100:5.1f}%  ({n_x}/{len(df)} 송원우=X)")
    print(f"  Cohen's κ           = {overall_kappa:+.4f}  (single-class 한계로 보조용)")
    print("=" * 70)

    # 속성별 AR
    print("\n  [속성별 Agreement — 라벨러1 동의 비율]")
    per_aspect = {}
    for asp in df["속성"].unique():
        sub = df[df["속성"] == asp]
        if len(sub) < 1:
            continue
        agree = (sub["v24_라벨러1"] == sub["송원우_LABEL"]).mean()
        try:
            k = cohen_kappa_score(sub["v24_라벨러1"], sub["송원우_LABEL"], labels=LABELS)
        except Exception:
            k = float("nan")
        per_aspect[asp] = {"AR": float(agree), "kappa": float(k), "n": int(len(sub))}
        print(f"    {asp:>14s}  AR={agree*100:5.1f}%  ({int(agree*len(sub))}/{len(sub)})")

    # 변경 방향별 (P→X, N→X) 분석
    print("\n  [변경 방향별 — 송원우 의사결정 분포]")
    for direction in ["P", "N"]:
        sub = df[df["v23_GOLD"] == direction]
        n = len(sub)
        if n == 0:
            continue
        agree_label1 = int((sub["송원우_LABEL"] == "X").sum())
        agree_v23    = int((sub["송원우_LABEL"] == direction).sum())
        other        = n - agree_label1 - agree_v23
        print(f"    {direction}→X 변경 케이스 (n={n})")
        print(f"      라벨러1 동의 (송원우=X)        : {agree_label1:>3}건 ({agree_label1/n*100:5.1f}%)")
        print(f"      v23 동의 (송원우={direction})              : {agree_v23:>3}건 ({agree_v23/n*100:5.1f}%)")
        print(f"      제3 라벨                       : {other:>3}건 ({other/n*100:5.1f}%)")

    # Confusion matrix (라벨러1 vs 송원우)
    print("\n  [Confusion Matrix — 라벨러1(행) vs 송원우(열)]")
    cm = confusion_matrix(y_label1, y_swu, labels=LABELS)
    print(f"    {'':>14s}  " + "  ".join(f"{l:>5s}" for l in LABELS))
    for i, l in enumerate(LABELS):
        print(f"    {l:>14s}  " + "  ".join(f"{cm[i,j]:>5d}" for j in range(len(LABELS))))

    # 분기 판정 (AR 기반)
    print("\n" + "=" * 70)
    print("판정")
    print("=" * 70)
    if AR >= 0.75:
        verdict = "H1: v24 옳음"
        msg = (
            f"\n  ✅ H1 채택 (AR={AR*100:.1f}% ≥ 75%)\n"
            f"     → 송원우도 X 동의 — 라벨러1 _NEW 신뢰성 높음\n"
            f"     → 모델 v9가 v23 over-labeling에 과적합 → F1 하락은 모델 측 문제\n"
            f"\n  [다음 단계]\n"
            f"     1. LoRA fine-tuning (v24 974 train / 100 valid) ~3-4시간\n"
            f"     2. 또는 v10 prediction 후처리 임계값 조정 (P/N over-detect 보정)\n"
            f"     3. 인사이트: Phase E 재추론 시 포지셔닝 좌표 변동 가능"
        )
    elif AR >= 0.50:
        verdict = "중간"
        msg = (
            f"\n  ⚠️  중간 영역 (AR={AR*100:.1f}%, 50~75%)\n"
            f"     → 라벨링 기준에 부분적 차이 — 분쟁 케이스 토론 필요\n"
            f"     → 송원우 = v23 동의 비율이 30~50% 사이라면 P/X 경계 케이스가 모호\n"
            f"\n  [다음 단계]\n"
            f"     1. 분쟁 케이스 (보고서 \"결과\" 시트 disagree=True) 라벨러1과 토론\n"
            f"     2. 가이드라인 정렬 (특히 P→X 경계 케이스 5~10건 사례 명시)\n"
            f"     3. boundary 100건 추가 재라벨링 (라벨러1 + 송원우 합의 protocol)"
        )
    else:
        verdict = "H2: 라벨러1 too strict"
        msg = (
            f"\n  ❌ H2 채택 (AR={AR*100:.1f}% < 50%)\n"
            f"     → 송원우는 대부분 v23(P/N) 편 — 라벨러1 X 변환은 과도함\n"
            f"     → v24 신뢰성 낮음, v23 유지 권장\n"
            f"\n  [다음 단계]\n"
            f"     1. 라벨링 가이드라인 재정의 (P/X 경계 사례 명시 + 예시 다수)\n"
            f"     2. 라벨러2 합류 IAA 강화 (3인 합의 protocol)\n"
            f"     3. 단기적: v9 baseline 유지 + 모델 측 LoRA 단독 진행 (v23 골든셋)"
        )
    print(msg)

    # 분쟁 케이스 정렬 + Excel 저장
    df["disagree"] = df["v24_라벨러1"] != df["송원우_LABEL"]
    df_sorted = df.sort_values(["disagree", "속성"], ascending=[False, True])

    n_disagree = int(df["disagree"].sum())

    summary_rows = [
        {"항목": "Agreement Rate (AR)", "값": f"{AR*100:.1f}%"},
        {"항목": "송원우=X 건수",        "값": f"{n_x}/{len(df)}"},
        {"항목": "Cohen's κ (보조)",     "값": f"{overall_kappa:+.4f}"},
        {"항목": "판정",                "값": verdict},
        {"항목": "분쟁 건수",           "값": n_disagree},
        {"항목": "─ P→X 케이스 ─",     "값": ""},
        {"항목": "  라벨러1 동의 (송원우=X)",  "값": int(((df["v23_GOLD"]=="P") & (df["송원우_LABEL"]=="X")).sum())},
        {"항목": "  v23 동의 (송원우=P)",     "값": int(((df["v23_GOLD"]=="P") & (df["송원우_LABEL"]=="P")).sum())},
        {"항목": "  제3 라벨 (송원우=N)",     "값": int(((df["v23_GOLD"]=="P") & (df["송원우_LABEL"]=="N")).sum())},
        {"항목": "─ N→X 케이스 ─",     "값": ""},
        {"항목": "  라벨러1 동의 (송원우=X)",  "값": int(((df["v23_GOLD"]=="N") & (df["송원우_LABEL"]=="X")).sum())},
        {"항목": "  v23 동의 (송원우=N)",     "값": int(((df["v23_GOLD"]=="N") & (df["송원우_LABEL"]=="N")).sum())},
        {"항목": "  제3 라벨 (송원우=P)",     "값": int(((df["v23_GOLD"]=="N") & (df["송원우_LABEL"]=="P")).sum())},
        {"항목": "─ 속성별 AR ─",      "값": ""},
    ]
    for asp, info in per_aspect.items():
        summary_rows.append({"항목": f"  {asp}", "값": f"AR {info['AR']*100:.0f}% (n={info['n']})"})

    with pd.ExcelWriter(report_path, engine="openpyxl") as w:
        pd.DataFrame(summary_rows).to_excel(w, sheet_name="요약", index=False)
        df_sorted.to_excel(w, sheet_name="결과", index=False)

    print(f"\n[저장] {report_path}")
    print(f"  - '요약' 시트: κ + 핵심 지표")
    print(f"  - '결과' 시트: 분쟁 우선 정렬 ({n_disagree}건)")

    return {
        "AR": float(AR),
        "kappa": float(overall_kappa),
        "verdict": verdict,
        "per_aspect": per_aspect,
    }


# ─────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=str(DEFAULT_INPUT))
    p.add_argument("--report", default=str(DEFAULT_REPORT))
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[abort] 입력 파일 없음: {input_path}")
        print(f"  → 송원우_LABEL 작성 후 'absa_spotcheck_30_completed.xlsx' 로 저장")
        sys.exit(1)

    measure(input_path, Path(args.report))
