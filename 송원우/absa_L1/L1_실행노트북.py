# %% [markdown]
# # L1 실행 노트북 — ABSA 파이프라인 End-to-End
#
# **사용법**: VSCode 또는 Jupyter에서 셀(`# %%`) 단위 실행.
# **선행 작업**: `송원우/L1_작업매뉴얼.md` 정독 + Phase A 라벨링 완료.
# **위치**: 프로젝트 루트(`SPARTA_PROJECT_4TH_E_COMMERCE/`)에서 실행.

# %% [markdown]
# ## 0. 환경 및 모듈 임포트

# %%
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, classification_report

sys.path.insert(0, './송원우')
import absa
importlib.reload(absa)

print(f'absa.py 로드 완료. 속성 수: {len(absa.ASPECTS)}')

# %% [markdown]
# ─────────────────────────────────────────────────────────────────────
# ## Phase B-1. Gate 1: Cross-Overlap κ 측정
#
# **선행**: `송원우/final_data/absa_overlap_validation_L1_DONE.xlsx` 저장 완료
# (Phase A — 100건 라벨링 완료 후 파일명 변경하여 저장)

# %%
DONE_PATH = '송원우/final_data/absa_overlap_validation_L1_DONE.xlsx'
ANS_PATH  = '송원우/final_data/_overlap_answer_key_v23_DO_NOT_OPEN_BEFORE_LABELING.xlsx'

l1 = pd.read_excel(DONE_PATH, sheet_name='1_검증라벨링', header=1)
ans = pd.read_excel(ANS_PATH)

# 채움 검증
fn_done = l1['기능성_라벨러1'].notna().sum()
br_done = l1['브랜드_라벨러1'].notna().sum()
print(f'기능성 채움: {fn_done}/100')
print(f'브랜드 채움: {br_done}/100')
assert fn_done == 100 and br_done == 100, '미라벨링 행 존재 — Phase A 미완료'

# 병합
m = l1.merge(ans, on='sample_idx')
print(f'병합 결과: {len(m)}건')

# %%
def report_kappa(a, b, name):
    a, b = a.astype(str), b.astype(str)
    k = cohen_kappa_score(a, b)
    agree = int((a == b).sum())
    grade = ('Almost Perfect' if k >= 0.81 else
             'Substantial'    if k >= 0.61 else
             'Moderate'       if k >= 0.41 else 'Fair/Slight')
    print(f'\n[{name}]  κ = {k:.4f}  ({grade})  일치 {agree}/{len(a)}')
    print(pd.crosstab(a, b, rownames=['L1'], colnames=['L2(v23)'], margins=True))
    print(classification_report(b, a, digits=3, zero_division=0))
    return k

print('═' * 60)
print('  Gate 1 — Cross-Overlap κ')
print('═' * 60)
k_fn = report_kappa(m['기능성_라벨러1'],  m['기능성_L2(v23)'],   '기능성')
k_br = report_kappa(m['브랜드_라벨러1'],  m['브랜드_L2(v23)'],   '브랜드/헤리티지')

macro = float(np.mean([k_fn, k_br]))
print(f'\n>> Macro κ = {macro:.4f}')
print('>> 판정:')
if macro >= 0.81:
    verdict = '✅ Almost Perfect — Phase C 즉시 진입'
elif macro >= 0.65:
    verdict = '✅ Substantial — Phase C 진입'
elif macro >= 0.50:
    verdict = '⚠️ Moderate — 불일치 분석 후 송원우 합의 미팅'
else:
    verdict = '❌ 미달 — 가이드라인 v2.3 patch 필수, Phase C 진입 금지'
print(f'   {verdict}')

# %% [markdown]
# ## Phase B-2. 불일치 케이스 추출 (κ < 0.65 시)

# %%
mismatch_fn = m[m['기능성_라벨러1'] != m['기능성_L2(v23)']][[
    'sample_idx', 'brand', 'rating', 'content_clean',
    '기능성_라벨러1', '기능성_L2(v23)', '메모',
]]
mismatch_br = m[m['브랜드_라벨러1'] != m['브랜드_L2(v23)']][[
    'sample_idx', 'brand', 'rating', 'content_clean',
    '브랜드_라벨러1', '브랜드_L2(v23)', '메모',
]]

print(f'기능성 불일치: {len(mismatch_fn)}건')
print(f'브랜드 불일치: {len(mismatch_br)}건')

with pd.ExcelWriter('송원우/final_data/overlap_mismatch.xlsx') as w:
    mismatch_fn.to_excel(w, sheet_name='기능성_불일치', index=False)
    mismatch_br.to_excel(w, sheet_name='브랜드_불일치', index=False)
print('✓ 저장: 송원우/final_data/overlap_mismatch.xlsx')

# %% [markdown]
# ─────────────────────────────────────────────────────────────────────
# ## Phase C-1. absa.py 골격 동작 확인

# %%
importlib.reload(absa)

golden = absa.load_golden_set()
print(f'골든셋: {len(golden)}건')

# Stage1 트리거 매칭 스모크 테스트
sample_content = golden.iloc[0]['content_clean']
s1 = absa.stage1_trigger_match(sample_content)
print(f'샘플 리뷰: {sample_content[:80]}...')
print(f'Stage1 결과: {s1}')

# %% [markdown]
# ## Phase C-2. Few-shot 빌드 (라벨러1 구현 후 실행)

# %%
# [L1 구현 완료 후 실행]
# few_shots = absa.build_few_shot_examples(golden, n_per_class=3)
# for aspect, examples in few_shots.items():
#     print(f'\n[{aspect}] Few-shot {len(examples)}건')
#     for content, label in examples[:3]:
#         print(f'  ({label}) {content[:60]}...')

# %% [markdown]
# ## Phase C-3. 골든셋 분할 (학습/검증)

# %%
# Few-shot pool: 속성별 P/N/X 각 5건 = sample_idx 추출
# 나머지 ~910건이 검증용
# [L1 채우기]: build_few_shot_examples 결과의 sample_idx를 제외한 나머지로 valid 분할

# valid_mask = ~golden['sample_idx'].isin(few_shot_idxs)
# valid = golden[valid_mask].reset_index(drop=True)
# print(f'검증 셋: {len(valid)}건')

# %% [markdown]
# ─────────────────────────────────────────────────────────────────────
# ## Phase D. Gate 2: 모델 검증 (Macro-F1)
#
# **선행**: absa.py의 build_prompt / call_exaone / predict_dataframe 구현 완료

# %%
# importlib.reload(absa)
#
# # 검증 셋 추론
# pred = absa.predict_dataframe(valid, few_shots)
# pred.to_csv('송원우/final_data/absa_predictions_validation.csv', index=False)

# %%
# # 평가
# eval_result = absa.evaluate(pred, valid)
# absa.print_evaluation_report(eval_result)
#
# # Gate 2 판정
# if eval_result['macro_f1'] >= 0.70:
#     print('\n✅ Gate 2 통과 → Phase E 진입')
# else:
#     low = absa.diagnose_low_f1_aspect(eval_result, threshold=0.60)
#     print(f'\n⚠️ Gate 2 미달. F1 < 0.60 속성: {low}')
#     print('→ Few-shot 5→10건 보강 또는 트리거 사전 보강 후 재실행')

# %% [markdown]
# ## Phase D-2. 오분류 진단 (F1 미달 속성)

# %%
# # 예: 브랜드/헤리티지 F1 미달 시
# miss = absa.extract_misclassified(pred, valid, aspect='브랜드/헤리티지')
# miss.to_excel('송원우/final_data/misclassified_브랜드.xlsx', index=False)
# print(miss.head(20))

# %% [markdown]
# ─────────────────────────────────────────────────────────────────────
# ## Phase E. 전체 1.16M 데이터 추론
#
# **선행**: Gate 2 통과 (Macro-F1 ≥ 0.70)

# %%
# absa.predict_full_pipeline(
#     parquet_path='송원우/final_data/preprocessed_absa.parquet',
#     output_path='송원우/final_data/absa_predictions_full.parquet',
#     golden_path='송원우/final_data/absa_golden_set_1000_v23.xlsx',
#     chunk_size=10_000,
#     checkpoint_every=100_000,
# )

# %% [markdown]
# ## Phase E-2. 전체 결과 분포 확인

# %%
# full = pd.read_parquet('송원우/final_data/absa_predictions_full.parquet')
# print(f'전체 추론 완료: {len(full):,}건\n')
# for aspect in absa.ASPECTS:
#     dist = full[aspect].value_counts(normalize=True).round(3)
#     print(f'[{aspect}] {dict(dist)}')

# %% [markdown]
# ─────────────────────────────────────────────────────────────────────
# ## 인계 체크리스트
#
# - [ ] `absa_overlap_validation_L1_DONE.xlsx`
# - [ ] `overlap_mismatch.xlsx` (Gate 1 시)
# - [ ] `absa.py` (구현 완료본)
# - [ ] `absa_predictions_validation.csv` (Gate 2)
# - [ ] `absa_predictions_full.parquet` (Phase E)
# - [ ] `L1_검증보고서.md` (κ, F1, 결정 기록)
