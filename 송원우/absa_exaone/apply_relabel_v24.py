"""
apply_relabel_v24.py — _NEW 라벨 검증 + 골든셋 v2.3 → v2.4 빌드
==================================================================

입력:
  - 라벨러1이 _NEW 컬럼 작성 완료한 absa_relabel_boundary_150.xlsx
  - v2.3 골든셋 absa_golden_set_1000_v23.xlsx

출력:
  - absa_golden_set_1000_v24.xlsx (변경 150건 + 미변경 850건)
  - 변경량 리포트 (속성별 _GOLD ↔ _NEW transition matrix)

Usage:
  uv run python apply_relabel_v24.py
  uv run python apply_relabel_v24.py --relabeled custom_path.xlsx
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ABSA_DIR = Path(__file__).resolve().parent
if str(ABSA_DIR) not in sys.path:
    sys.path.insert(0, str(ABSA_DIR))

from absa_v9 import ASPECTS, LABELS

GOLDEN_V23      = ABSA_DIR / "absa_golden_set_1000_v23.xlsx"
GOLDEN_V24      = ABSA_DIR / "absa_golden_set_1000_v24.xlsx"
RELABEL_DEFAULT = ABSA_DIR / "absa_relabel_boundary_150.xlsx"


# ─────────────────────────────────────────────────────────────
# 검증
# ─────────────────────────────────────────────────────────────
def validate_new_labels(relabel_df: pd.DataFrame) -> tuple[list[int], int, list[int]]:
    """_NEW 컬럼 6속성 모두 P/N/X로 채워졌는지 검증.

    Returns:
        missing_rows: 결측 있는 행 인덱스
        n_blank_cells: 결측 칸 총 개수
        missing_sample_idx: 결측 행의 sample_idx 리스트
    """
    new_cols = [f"{a}_NEW" for a in ASPECTS]
    missing_rows: list[int] = []
    n_blank = 0
    missing_sids: list[int] = []
    for idx, row in relabel_df.iterrows():
        row_has_blank = False
        for col in new_cols:
            val = row.get(col, "")
            v = "" if pd.isna(val) else str(val).strip().upper()
            if v not in LABELS:
                n_blank += 1
                row_has_blank = True
        if row_has_blank:
            missing_rows.append(idx)
            if "sample_idx" in row:
                missing_sids.append(int(row["sample_idx"]))
    return missing_rows, n_blank, missing_sids


# ─────────────────────────────────────────────────────────────
# v2.4 병합
# ─────────────────────────────────────────────────────────────
def merge_to_v24(v23: pd.DataFrame, relabel: pd.DataFrame) -> pd.DataFrame:
    """v23에 relabel _NEW 라벨을 sample_idx 매칭하여 반영. v24 반환."""
    v24 = v23.copy()
    relabel_indexed = relabel.set_index("sample_idx")
    n_changed_rows = 0
    n_missing = 0

    for sid in relabel["sample_idx"]:
        mask = v24["sample_idx"] == sid
        if not mask.any():
            print(f"  [warn] sample_idx={sid} v23에 없음 — skip")
            n_missing += 1
            continue
        for asp in ASPECTS:
            new_val = relabel_indexed.at[sid, f"{asp}_NEW"]
            if pd.notna(new_val):
                v = str(new_val).strip().upper()
                if v in LABELS:
                    v24.loc[mask, asp] = v
        n_changed_rows += 1

    print(f"  → {n_changed_rows}건 row의 6속성 _NEW 적용 (skip {n_missing})")
    return v24


# ─────────────────────────────────────────────────────────────
# 변경량 리포트
# ─────────────────────────────────────────────────────────────
def print_change_report(v23: pd.DataFrame, v24: pd.DataFrame, relabel: pd.DataFrame) -> dict:
    """속성별 _GOLD ↔ _NEW transition matrix + 변경 건수."""
    relabeled_ids = set(relabel["sample_idx"].tolist())
    v23_sub = v23[v23["sample_idx"].isin(relabeled_ids)].set_index("sample_idx")
    v24_sub = v24[v24["sample_idx"].isin(relabeled_ids)].set_index("sample_idx")
    common = v23_sub.index.intersection(v24_sub.index)
    v23_sub = v23_sub.loc[common]
    v24_sub = v24_sub.loc[common]

    summary = {}
    print("\n" + "=" * 70)
    print("변경량 리포트 (속성별 v23 GOLD → v24 NEW)")
    print("=" * 70)

    for asp in ASPECTS:
        old = v23_sub[asp].astype(str).str.upper()
        new = v24_sub[asp].astype(str).str.upper()
        n_changed = int((old != new).sum())
        n_total = len(old)
        summary[asp] = {"changed": n_changed, "total": n_total}
        pct = n_changed / n_total * 100 if n_total else 0
        print(f"\n■ {asp:>14s}  변경 {n_changed:>3}/{n_total} ({pct:5.1f}%)")
        if n_changed > 0:
            tr = pd.crosstab(old, new, rownames=["v23 GOLD"], colnames=["v24 NEW"])
            tr_full = tr.reindex(index=LABELS, columns=LABELS, fill_value=0)
            print(tr_full)
    return summary


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main(relabeled_path: Path,
         v23_path: Path = GOLDEN_V23,
         v24_path: Path = GOLDEN_V24) -> bool:
    """전체 흐름 — 검증 실패 시 False, 성공 시 True."""
    print("=" * 70)
    print("[apply_relabel_v24]")
    print("=" * 70)
    print(f"\n[1/4] 입력 파일 로드")
    print(f"  - 라벨러1: {relabeled_path}")
    print(f"  - v23 골든셋: {v23_path}")

    if not relabeled_path.exists():
        print(f"  ✗ 라벨러1 파일 없음: {relabeled_path}")
        return False
    if not v23_path.exists():
        print(f"  ✗ v23 골든셋 없음: {v23_path}")
        return False

    relabel_df = pd.read_excel(relabeled_path, sheet_name="라벨링")
    v23 = pd.read_excel(v23_path)
    print(f"  → relabel {len(relabel_df)}건 / v23 {len(v23)}건")

    print(f"\n[2/4] _NEW 라벨 검증")
    missing_rows, n_blank, missing_sids = validate_new_labels(relabel_df)
    if missing_rows:
        print(f"  ⚠ 결측 행 {len(missing_rows)}개 / 결측 칸 {n_blank}개")
        print(f"  미작성 sample_idx (앞 15개): {missing_sids[:15]}")
        print(f"  → 라벨러1에게 미작성 행 작성 요청 후 재실행")
        return False
    print(f"  ✓ 결측 없음 — {len(relabel_df)}건 × 6속성 모두 P/N/X 작성됨")

    print(f"\n[3/4] v2.3 → v2.4 빌드")
    v24 = merge_to_v24(v23, relabel_df)

    print(f"\n[4/4] 변경량 리포트 + 저장")
    summary = print_change_report(v23, v24, relabel_df)

    v24.to_excel(v24_path, index=False)
    total_changed = sum(s["changed"] for s in summary.values())
    print(f"\n[저장] {v24_path}")
    print(f"  v24 전체: {len(v24)}건 (라벨러 검토 {len(relabel_df)}건, 라벨 변경 합계 {total_changed}칸)")
    return True


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--relabeled", default=str(RELABEL_DEFAULT))
    p.add_argument("--golden-in", default=str(GOLDEN_V23))
    p.add_argument("--golden-out", default=str(GOLDEN_V24))
    args = p.parse_args()
    ok = main(Path(args.relabeled), Path(args.golden_in), Path(args.golden_out))
    sys.exit(0 if ok else 1)
