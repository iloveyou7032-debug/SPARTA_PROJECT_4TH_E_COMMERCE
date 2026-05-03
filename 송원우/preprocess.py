"""
preprocess.py — 전처리 마스터 모듈 (v1.0 / 2026-05-03)

check_tokens.py v4.17 사전·함수를 임포트하여 확장:
  - advanced_pre_process(): v4.17.1 패치 4개 추가 (한사이즈/셋업/반사이즈/하이라이즈)
  - preprocess_texts()    : 배치 토큰화 (list[str] → list[str])
  - preprocess_master()   : 전체 파이프라인 (CSV → parquet 2종)

Two-track 출력:
  - preprocessed_bertopic.parquet : content_len ≥ 10 (토픽 모델링용)
  - preprocessed_absa.parquet     : content_len ≥  6 (감성 분석용)
"""

import os
import re
import time
import pandas as pd

from check_tokens import (
    TEXT_CORRECTIONS,
    INTENSITY_ADVERBS,
    clean_text,
    process_result,
    get_kiwi,
)

# ─── v4.17.1 패치 정규식 (모듈 로드 시 1회 컴파일) ──────────────────────────
# check_tokens.py의 advanced_pre_process에는 없던 4개 Kiwi 분해 차단 패턴
# - 한사이즈(1341건), 셋업(1163건), 반사이즈(262건), 하이라이즈(237건) dict 미적용 해소
_PATCH_PATTERNS = [
    (re.compile(r'한\s*사이즈'),   '한사이즈'),
    (re.compile(r'셋\s*업'),       '셋업'),
    (re.compile(r'반\s*사이즈'),   '반사이즈'),
    (re.compile(r'하이\s*라이즈'), '하이라이즈'),
]

_NEG_SPLIT = re.compile(
    r'(하고|지만|아서|어서|니까|은데|는데|인데|고요|네요|대요|길래|았는데|었는데|이고)([가-힣])'
)


# ════════════════════════════════════════════════════════════
# 1. 전처리 함수 (v4.17.1 — check_tokens v4.17 + 패치)
# ════════════════════════════════════════════════════════════

def advanced_pre_process(text: str) -> str:
    """
    check_tokens.py v4.17 로직 + v4.17.1 패치 4개.
    kiwi.space() 배치 전달 직전에 호출한다.
    """
    # 오타·구문 교정 (TEXT_CORRECTIONS)
    for wrong, right in TEXT_CORRECTIONS.items():
        text = text.replace(wrong, right)

    # 마음에들다 변형 강화 (부사 삽입형 캡처)
    text = re.sub(r'(마음|맘)에\s*[가-힣]{0,2}\s*들\w*', '마음에들다 ', text)

    # v4.17.1 패치 — Kiwi 분해 차단
    for pat, repl in _PATCH_PATTERNS:
        text = pat.sub(repl, text)

    # 부정 결합 일반화
    text = re.sub(r'([가-힣]{2,4})(이|가|도|은|는)?\s+없([다어요습네음])', r'\1없\3', text)
    text = re.sub(r'([가-힣]{2,4})지[도는]?\s?않\w*', r' 안\1 ', text)
    text = re.sub(r'([가-힣]+)지[도는]?\s?못\w*', r' 못 \1', text)
    text = _NEG_SPLIT.sub(r'\1 \2', text)
    text = re.sub(r'없어[서선요]', '없다 ', text)
    text = re.sub(r'필요없\w*', '필요없다', text)
    return text


# ════════════════════════════════════════════════════════════
# 2. 배치 토큰화 (리스트 입력 → 토큰 문자열 리스트 출력)
# ════════════════════════════════════════════════════════════

def _post_space_patch(text: str) -> str:
    """
    kiwi.space() 이후 후처리 패치.
    kiwi.space()가 USER_DICT 단어를 재분리하는 경우를 복원한다.
    현재 대상: 하이라이즈 (kiwi.space() 한계로 '하이 라이즈'로 재분리)
    """
    return re.sub(r'하이\s+라이즈', '하이라이즈', text)


def _strip_intensity(token_str: str) -> str:
    """v4.18 — BERTopic용 강도 부사 제거 토큰 생성."""
    if not token_str:
        return token_str
    return ' '.join(w for w in token_str.split() if w not in INTENSITY_ADVERBS)


def preprocess_texts(texts: list[str]) -> list[str]:
    """
    텍스트 리스트를 clean_text → advanced_pre_process → kiwi.space
    → post_patch → kiwi.tokenize → process_result 파이프라인으로 처리한다.

    Parameters
    ----------
    texts : 원문 리스트 (clean_text 미적용 상태)

    Returns
    -------
    list[str] : 토큰 문자열 리스트 (공백 구분, 빈 문자열 포함 가능)
    """
    kiwi      = get_kiwi()
    cleaned   = [clean_text(t) for t in texts]
    pre       = [advanced_pre_process(t) for t in cleaned]
    spaced    = [_post_space_patch(s) for s in kiwi.space(pre)]
    tokenized = list(kiwi.tokenize(spaced))
    return [process_result(tok) for tok in tokenized]


# ════════════════════════════════════════════════════════════
# 3. 마스터 파이프라인 (CSV → parquet 2종)
# ════════════════════════════════════════════════════════════

def preprocess_master(
    input_path:  str = './final_data/master_preprocessed_260430.csv',
    output_dir:  str = './final_data',
    chunk_size:  int = 50_000,
    content_col: str = 'content',
    brand_col:   str = 'brand',
) -> dict:
    """
    전체 마스터 테이블 전처리 파이프라인.

    Parameters
    ----------
    input_path  : 입력 CSV 경로 (노트북 실행 위치 기준 상대경로)
    output_dir  : parquet 저장 디렉토리
    chunk_size  : 청크 단위 행 수 (기본 50,000 — M4 Pro RAM 기준 안전 수준)
    content_col : 리뷰 텍스트 컬럼명
    brand_col   : 브랜드 컬럼명

    Returns
    -------
    dict: {'total': int, 'bertopic': int, 'absa': int, 'elapsed_min': float}

    Notes
    -----
    - Two-track 분기:
        BERTopic → content_len ≥ 10 (토픽 모델링 노이즈 방지)
        ABSA     → content_len ≥  6 (이미 5자 이하 제거된 마스터 테이블이므로 사실상 전체)
    - 출력 컬럼 추가:
        content_clean : clean_text 결과
        content_len   : 공백 제외 길이
        tokens        : ABSA/통계용 토큰 (강도 부사 포함)
        tokens_topic  : BERTopic용 토큰 (강도 부사 제외) — v4.18
    - pyarrow 필요: `uv add pyarrow` 미설치 시 오류 발생
    """
    kiwi = get_kiwi()
    t0   = time.time()
    os.makedirs(output_dir, exist_ok=True)

    bert_chunks: list[pd.DataFrame] = []
    absa_chunks: list[pd.DataFrame] = []
    total_in = 0

    print(f"[preprocess_master] 시작 — 입력: {input_path}")
    print(f"  청크 크기: {chunk_size:,}건 | 출력: {output_dir}")

    reader = pd.read_csv(
        input_path,
        chunksize=chunk_size,
        dtype={content_col: 'str', brand_col: 'str'},
        low_memory=False,
    )

    for i, chunk in enumerate(reader, 1):
        chunk = chunk.reset_index(drop=True)
        chunk[content_col] = chunk[content_col].fillna('').astype(str)

        texts   = chunk[content_col].tolist()
        cleaned = [clean_text(t) for t in texts]
        lens    = [len(c.replace(' ', '')) for c in cleaned]

        # 배치 토큰화 (kiwi.space 후처리 패치 포함)
        pre       = [advanced_pre_process(t) for t in cleaned]
        spaced    = [_post_space_patch(s) for s in kiwi.space(pre)]
        tokenized = list(kiwi.tokenize(spaced))
        tokens    = [process_result(tok) for tok in tokenized]

        chunk['content_clean'] = cleaned
        chunk['content_len']   = lens
        chunk['tokens']        = tokens                                  # ABSA·통계용 (강도 부사 포함)
        chunk['tokens_topic']  = [_strip_intensity(t) for t in tokens]   # BERTopic용 (강도 부사 제외)

        # 빈 토큰 제외 마스크
        has_token       = chunk['tokens'].str.strip().ne('')
        has_topic_token = chunk['tokens_topic'].str.strip().ne('')

        # Two-track 분기
        bert_chunks.append(chunk[(chunk['content_len'] >= 10) & has_topic_token].copy())
        absa_chunks.append(chunk[(chunk['content_len'] >= 6)  & has_token].copy())

        total_in += len(chunk)
        elapsed   = (time.time() - t0) / 60
        print(f"  청크 {i:>3}: {total_in:>9,}건 누적 | 경과 {elapsed:.1f}분")

    bert_df = pd.concat(bert_chunks, ignore_index=True)
    absa_df = pd.concat(absa_chunks, ignore_index=True)

    # 청크 간 int/str 혼재 → pyarrow ArrowInvalid 방지
    for df in (bert_df, absa_df):
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].where(df[col].isna(), df[col].astype(str))

    bert_path = os.path.join(output_dir, 'preprocessed_bertopic.parquet')
    absa_path = os.path.join(output_dir, 'preprocessed_absa.parquet')

    bert_df.to_parquet(bert_path, index=False)
    absa_df.to_parquet(absa_path, index=False)

    elapsed_min = (time.time() - t0) / 60

    print(f"\n{'='*52}")
    print(f"  입력 총계     : {total_in:>10,}건")
    print(f"  BERTopic 출력 : {len(bert_df):>10,}건  (content_len ≥ 10)")
    print(f"  ABSA 출력     : {len(absa_df):>10,}건  (content_len ≥  6)")
    print(f"  총 소요시간   : {elapsed_min:.1f}분")
    print(f"{'='*52}")
    print(f"  저장 완료: {bert_path}")
    print(f"  저장 완료: {absa_path}")

    return {
        'total':       total_in,
        'bertopic':    len(bert_df),
        'absa':        len(absa_df),
        'elapsed_min': elapsed_min,
    }
