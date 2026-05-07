"""
absa.py — ABSA 캐스케이드 파이프라인 (Stage1 트리거매칭 + Stage2 EXAONE)
============================================================================

역할:
    한국어 애슬레저 리뷰의 6속성 P/N/X 감성 분석.
    Stage1: 트리거 사전 매칭 (rule-based, 빠름) — 매칭 없으면 X로 즉시 결정.
    Stage2: Ollama EXAONE 3.5 7.8B Few-shot — 매칭 케이스 정밀 분류.

작성: 송원우 (골격) / 라벨러1 (구현)
환경: uv run python, Ollama 로컬 EXAONE 3.5 7.8B

[L1 채우기] 표시 함수만 구현하면 end-to-end 동작.
"""
from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────

ASPECTS = ['핏/사이즈', '소재/내구성', '기능성', '디자인', '브랜드/헤리티지', '가격/가치']

LABELS = ['P', 'N', 'X']

# Stage1 트리거 사전 — absa_relabel.py에서 v2.2 기준으로 재활용
# [L1 채우기] absa_relabel.py 의 트리거 사전을 import하거나 복사하여 v2.2 캘리브레이션 합의 반영
TRIGGERS: dict[str, dict[str, list[str]]] = {
    '핏/사이즈': {
        'P': [],  # [L1 채우기] 가이드라인 v2.2 §3.1 P 트리거
        'N': [],  # [L1 채우기] 가이드라인 v2.2 §3.1 N 트리거
    },
    '소재/내구성': {'P': [], 'N': []},
    '기능성':       {'P': [], 'N': []},
    '디자인':       {'P': [], 'N': []},
    '브랜드/헤리티지': {
        'P': ['재구매', '또 살', '다시 구매', '추천', '단골', '믿고', '애용', '팬', '계속 살'],
        'N': ['실망', '안 사요', '비추', '기대 이하', '브랜드 망', '안 입어'],
    },
    '가격/가치':    {'P': [], 'N': []},
}

# 가이드라인 §3.{aspect} 발췌문 (프롬프트 inject용)
ASPECT_RULES: dict[str, str] = {
    '기능성': (
        '의류 착용감은 핏/사이즈로 분류, 신발/양말 착용감(쿠셔닝/폭신함)은 기능성. '
        '끈/밴드 소재 강성 문제는 소재/내구성으로 분리.'
    ),
    '브랜드/헤리티지': (
        '재구매·추천·팬 명시만 P. 제품 만족(디자인/핏/포장/촉감) ≠ 브랜드 긍정 → X.'
    ),
    # [L1 채우기] 나머지 4속성 special rule
}


# ─────────────────────────────────────────────────────────────────────
# 1. 데이터 로드 / Few-shot 빌드
# ─────────────────────────────────────────────────────────────────────

def load_golden_set(path: str | Path = '송원우/final_data/absa_golden_set_1000_v23.xlsx') -> pd.DataFrame:
    """v2.3 골든셋 로드 + 컬럼 검증.

    Returns:
        DataFrame with columns: sample_idx, content_clean, brand, rating, *ASPECTS
    """
    df = pd.read_excel(path)
    required = {'sample_idx', 'content_clean'} | set(ASPECTS)
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'골든셋에 컬럼 누락: {missing}')
    return df


def build_few_shot_examples(
    golden_df: pd.DataFrame,
    n_per_class: int = 3,
    seed: int = 42,
) -> dict[str, list[tuple[str, str]]]:
    """
    골든셋에서 속성별 Few-shot 예시 추출.

    [L1 채우기]:
    - 속성별로 P/N/X 라벨 각 n_per_class건씩 추출
    - 우선순위:
        1) 캘리브레이션 합의 사례 (sample_idx in {10, 74, 502}) 우선 포함
        2) 길이 다양성 (단문 1건 + 중간 1건 + 장문 1건)
        3) 브랜드 분산 (FILA / 젝시믹스 / 안다르 / 룰루레몬 균등)
    - random_state=seed 고정 (reproducibility)

    Returns:
        {aspect: [(content, label), ...]}  — 각 aspect당 3*n_per_class 건
    """
    raise NotImplementedError('[L1 채우기]')


# ─────────────────────────────────────────────────────────────────────
# 2. Stage1 — 트리거 매칭 (rule-based)
# ─────────────────────────────────────────────────────────────────────

def stage1_trigger_match(content: str) -> dict[str, str]:
    """
    트리거 사전 매칭으로 6속성 1차 분류.

    Returns:
        {aspect: 'P' | 'N' | 'X' | 'AMBIGUOUS'}
        - 'P': P 트리거만 매칭
        - 'N': N 트리거만 매칭
        - 'AMBIGUOUS': P+N 동시 매칭 → Stage2로 위임
        - 'X': 매칭 없음 → 즉시 결정
    """
    result = {}
    for aspect, trig in TRIGGERS.items():
        p_hit = any(kw in content for kw in trig.get('P', []))
        n_hit = any(kw in content for kw in trig.get('N', []))
        if p_hit and n_hit:
            result[aspect] = 'AMBIGUOUS'
        elif p_hit:
            result[aspect] = 'P'
        elif n_hit:
            result[aspect] = 'N'
        else:
            result[aspect] = 'X'
    return result


# ─────────────────────────────────────────────────────────────────────
# 3. Stage2 — EXAONE Few-shot
# ─────────────────────────────────────────────────────────────────────

def build_prompt(
    content: str,
    aspect: str,
    few_shots: list[tuple[str, str]],
) -> str:
    """
    EXAONE Few-shot 프롬프트 빌드.

    [L1 채우기]:
    - 시스템 지시문 + aspect 정의
    - TRIGGERS[aspect]['P'/'N'] 키워드 inject
    - ASPECT_RULES[aspect] (special rule) inject
    - few_shots 5건 포맷 ("리뷰: ... \\n답: P/N/X")
    - target content + "답:"으로 마무리
    - 출력 제한: "답은 P, N, X 중 하나만 출력. 다른 설명 금지"

    예시 출력 형식:
        한국어 애슬레저 리뷰의 [{aspect}] 속성 감성을 P/N/X로 분류.
        규칙:
        - P 트리거: ...
        - N 트리거: ...
        - 특별 룰: {ASPECT_RULES[aspect]}
        - 답은 P, N, X 중 하나만 출력. 설명 금지.

        리뷰: "{ex1}"
        답: P
        ...
        리뷰: "{target}"
        답:
    """
    raise NotImplementedError('[L1 채우기]')


def call_exaone(
    prompt: str,
    model: str = 'exaone3.5:7.8b',
    temperature: float = 0.1,
    max_tokens: int = 5,
) -> str:
    """
    Ollama 동기 호출 → P/N/X 단일 토큰 반환.

    [L1 채우기]:
    - import ollama
    - ollama.generate(model=model, prompt=prompt, options={...})
    - 응답 파싱: 첫 토큰에서 'P', 'N', 'X' 추출
    - 파싱 실패 시 'X' fallback + 로그
    """
    raise NotImplementedError('[L1 채우기]')


async def call_exaone_async(prompt: str, model: str = 'exaone3.5:7.8b') -> str:
    """
    Ollama 비동기 호출 — 병렬 처리용.

    [L1 채우기]:
    - import ollama  (AsyncClient)
    - asyncio 기반 동시 요청 (concurrency=4 권고)
    """
    raise NotImplementedError('[L1 채우기]')


# ─────────────────────────────────────────────────────────────────────
# 4. End-to-end 추론
# ─────────────────────────────────────────────────────────────────────

def predict_one(
    content: str,
    few_shots: dict[str, list[tuple[str, str]]],
) -> dict[str, str]:
    """
    리뷰 1건 → 6속성 P/N/X 예측.

    Stage1 X / P / N 결과는 그대로 채택.
    AMBIGUOUS 또는 단방향 매칭(false trigger 검증 목적)만 Stage2 호출.
    """
    s1 = stage1_trigger_match(content)
    out: dict[str, str] = {}
    for aspect, label in s1.items():
        if label == 'X':
            out[aspect] = 'X'
        elif label == 'AMBIGUOUS':
            prompt = build_prompt(content, aspect, few_shots[aspect])
            out[aspect] = call_exaone(prompt)
        else:
            # P 또는 N 단방향 매칭 — false trigger 방지를 위해 LLM 검증
            # (속도 우선이면 그대로 채택하고 이 분기 생략 가능)
            prompt = build_prompt(content, aspect, few_shots[aspect])
            llm = call_exaone(prompt)
            out[aspect] = llm if llm in LABELS else label
    return out


def predict_dataframe(
    df: pd.DataFrame,
    few_shots: dict[str, list[tuple[str, str]]],
    content_col: str = 'content_clean',
    show_progress: bool = True,
) -> pd.DataFrame:
    """
    DataFrame 일괄 추론.

    [L1 채우기]:
    - tqdm으로 진행률 표시
    - 옵션: async 병렬 처리 (대용량 시)
    - 결과 DataFrame: input + ASPECTS 6컬럼 추가
    """
    raise NotImplementedError('[L1 채우기]')


def predict_full_pipeline(
    parquet_path: str | Path = '송원우/final_data/preprocessed_absa.parquet',
    output_path: str | Path = '송원우/final_data/absa_predictions_full.parquet',
    golden_path: str | Path = '송원우/final_data/absa_golden_set_1000_v23.xlsx',
    chunk_size: int = 10_000,
    checkpoint_every: int = 100_000,
) -> None:
    """
    전체 1.16M 데이터 추론 + 중간 저장.

    [L1 채우기]:
    - golden_set으로 few_shots 빌드
    - parquet chunk-by-chunk 로드
    - chunk별 predict_dataframe()
    - 매 checkpoint_every 건마다 parquet append
    - 완료 후 최종 합본 저장
    - 장애 복구: output_path 존재 시 마지막 review_id 이후부터 재개
    """
    raise NotImplementedError('[L1 채우기]')


# ─────────────────────────────────────────────────────────────────────
# 5. 검증 (Macro-F1, Confusion Matrix)
# ─────────────────────────────────────────────────────────────────────

def evaluate(
    pred_df: pd.DataFrame,
    gold_df: pd.DataFrame,
    join_key: str = 'sample_idx',
) -> dict:
    """
    예측 vs 골든셋 비교 → Macro-F1, 속성별 F1, Confusion Matrix.

    Returns:
        {
            'macro_f1': float,
            'per_aspect_f1': {aspect: float},
            'per_aspect_report': {aspect: classification_report str},
            'confusion': {aspect: pd.DataFrame},
        }
    """
    from sklearn.metrics import f1_score, classification_report, confusion_matrix

    merged = pred_df.merge(gold_df, on=join_key, suffixes=('_pred', '_gold'))
    out: dict = {'per_aspect_f1': {}, 'per_aspect_report': {}, 'confusion': {}}

    f1_scores = []
    for aspect in ASPECTS:
        y_true = merged[f'{aspect}_gold'].astype(str)
        y_pred = merged[f'{aspect}_pred'].astype(str)

        f1 = f1_score(y_true, y_pred, average='macro', labels=LABELS, zero_division=0)
        f1_scores.append(f1)
        out['per_aspect_f1'][aspect] = f1
        out['per_aspect_report'][aspect] = classification_report(
            y_true, y_pred, labels=LABELS, digits=3, zero_division=0
        )
        out['confusion'][aspect] = pd.crosstab(
            y_true, y_pred, rownames=['gold'], colnames=['pred'], margins=True
        )

    out['macro_f1'] = float(np.mean(f1_scores))
    return out


def print_evaluation_report(eval_result: dict) -> None:
    """평가 결과 콘솔 출력."""
    print('═' * 60)
    print(f"  Macro-F1: {eval_result['macro_f1']:.4f}")
    print('═' * 60)
    for aspect in ASPECTS:
        f1 = eval_result['per_aspect_f1'][aspect]
        flag = '✅' if f1 >= 0.60 else '⚠️ ' if f1 >= 0.45 else '❌'
        print(f'  {flag} {aspect:<14} F1={f1:.4f}')
    print()
    for aspect in ASPECTS:
        print(f'\n[{aspect}] Confusion Matrix:')
        print(eval_result['confusion'][aspect])
        print(f'\n[{aspect}] Classification Report:')
        print(eval_result['per_aspect_report'][aspect])


# ─────────────────────────────────────────────────────────────────────
# 6. 진단 헬퍼 (Few-shot 보강 / 트리거 보강 의사결정)
# ─────────────────────────────────────────────────────────────────────

def diagnose_low_f1_aspect(
    eval_result: dict,
    threshold: float = 0.60,
) -> list[str]:
    """F1 < threshold 속성 리스트 반환 → Few-shot 보강 대상."""
    return [a for a, f1 in eval_result['per_aspect_f1'].items() if f1 < threshold]


def extract_misclassified(
    pred_df: pd.DataFrame,
    gold_df: pd.DataFrame,
    aspect: str,
    join_key: str = 'sample_idx',
) -> pd.DataFrame:
    """특정 속성 오분류 케이스 추출 → 트리거 보강 후보."""
    m = pred_df.merge(gold_df, on=join_key, suffixes=('_pred', '_gold'))
    miss = m[m[f'{aspect}_pred'] != m[f'{aspect}_gold']]
    return miss[[join_key, 'content_clean', f'{aspect}_pred', f'{aspect}_gold']]


if __name__ == '__main__':
    # 스모크 테스트 — 골격 동작 확인
    df = load_golden_set()
    print(f'골든셋 로드: {len(df)}건')
    print(f'속성 컬럼: {[a for a in ASPECTS if a in df.columns]}')

    sample = df.iloc[0]['content_clean']
    s1 = stage1_trigger_match(sample)
    print(f'\nStage1 매칭 (idx=1): {s1}')
