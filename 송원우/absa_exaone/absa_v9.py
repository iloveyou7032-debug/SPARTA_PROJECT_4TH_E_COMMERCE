"""
absa_v9.py — ABSA 캐스케이드 파이프라인 v9
============================================================================

v8 대비 변경 사항:
    [v8 진단]
        핏/사이즈 F1=0.5831, X recall=0.262 (gold=X → pred=P 255건).
        v8 브랜드 P-bias 완화가 핏/사이즈 X→P 오분류를 233→255건으로 악화.
        LLM이 "편하다/찰떡/좋다" 단독 표현을 핏 P로 오분류.
        기존 프롬프트 규칙("편해요 좋아요 단독은 X")으로는 부족.

    [v9 변경] 핏/사이즈 단독 조정
    [1] 프롬프트 핏/사이즈 X 규칙 구체화
        v8: "'편해요' '좋아요' 단독은 X."
        v9: "'편해요' '좋아요' '찰떡' '딱이에요' '가볍다' 단독은 X.
             사이즈 수치(cm/kg) 또는 핏·사이즈·기장·허리·어깨 직접 언급 없으면 X."

작성: 송원우 (골격) / 안진식 (v9)
환경: Jupyter / Ollama 로컬 EXAONE 3.5 7.8B
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────────────

ASPECTS = ['핏/사이즈', '소재/내구성', '기능성', '디자인', '브랜드/헤리티지', '가격/가치']
LABELS  = ['P', 'N', 'X']

TRIGGERS_P: dict[str, list[str]] = {
    '핏/사이즈': [
        '정사이즈', '딱 맞', '잘 맞', '핏 좋', '핏 잘 잡', '핏감 좋',
        '라인 예쁘', '라인 살아', 'Y존 커버', '와이존 커버',
        '허리 잘 잡', '라이즈 좋', '잘 잡아', '안 흘러내', '안 처짐',
        '잘맞다', '딱맞다',
    ],
    '소재/내구성': [
        '부드럽', '보들', '매끄럽', '촉감 좋', '원단 좋',
        '두께 적당', '두께감 좋', '탄탄', '탄력 좋',
        '보풀 없', '변색 없', '안 늘어', '오래 입',
        '부드럽다', '매끄럽다', '탄탄하다',
    ],
    '기능성': [
        '신축성', '잘 늘어', '흡습', '땀 빨리 마', '땀 안 차',
        '통기', '바람 잘 통', '활동성', '운동할 때 편', '움직이기 편',
        '보온', '따뜻', '안 춥', '냉감', '안 비치',
        '따뜻하다', '시원하다', '안비치다',
    ],
    '디자인': [
        '예쁘', '이쁘', '디자인 좋', '디자인 마음',
        '색깔 예쁘', '색감 예쁘', '컬러 예쁘', '색이 좋', '색 예쁘',
        '패턴 예쁘', '실루엣 예쁘',
        '데일리', '코디 잘', '어울', '여성스럽', '세련', '고급스럽',
        '양면 착용', '다른 색', '다른 컬러',
        '예쁘다', '고급지다', '어울리다',
    ],
    '브랜드/헤리티지': [
        '또 살', '또 사', '다음에도 살', '다음에도 사', '다음에 살', '다음에 사',
        '앞으로도 살', '앞으로도 사', '계속 살', '계속 사',
        '재구매', '재주문', '한 번 더',
        '추천', '강추',
        '믿고 산', '믿고 사', '믿을 수 있', '브랜드 믿',
        '팬', '단골', '여기만', '충성',
        '답다', '스럽다', '감성', '느낌',
        '안다르답', '젝시믹스답', '휠라', '룰루레몬', '올드머니',
    ],
    '가격/가치': [
        '가성비', '이 가격', '저렴', '합리적', '가격 착', '가격 만족',
        '할인 좋', '세일', '가격대비',
    ],
}

TRIGGERS_N: dict[str, list[str]] = {
    '핏/사이즈': [
        '사이즈 작', '사이즈 큼', '작아요', '커요', '한치수',
        '조임', '끼임', '답답', 'Y존 부각', '와이존 부각',
        '허리 말림', '흘러내', '처짐', '늘어짐', '라인 이상',
        '답답하다', '허리말림',
    ],
    '소재/내구성': [
        '보풀', '늘어남', '변색', '후줄근',
        '까실', '따끔', '비침', '비쳐', '비치는',
        '후진 원단', '원단 별로', '얇', '거칠', '까칠',
        '세탁 후 변', '빨면',
        '거칠다', '까칠하다',
    ],
    '기능성': [
        '신축성 부족', '안 늘어남', '빳빳', '뻣뻣',
        '땀 안 마', '땀 차',
        '운동할 때 불편', '활동 제한', '움직이기 불편',
        '춥다', '안 따뜻', '너무 덥',
        '기능 떨어', '기능 별로', '운동복 같지 않',
        '안유연하다', '안늘어나다',
    ],
    '디자인': [
        '안 예쁘', '디자인 별로', '색감 별로', '색 별로',
        '패턴 별로', '실루엣 이상', '사진과 다름', '사진이랑 다',
        '촌스럽', '안 어울', '너무 화려', '너무 밋밋',
        '촌스럽다',
    ],
    '브랜드/헤리티지': [
        '다신 안', '다시는 안', '실망', '기대 이하', '비추',
        '답지 못', '브랜드 가치 없', '환불', '반품',
    ],
    '가격/가치': [
        '비싸', '너무 비쌈', '가격 대비 별로', '가격이 부담',
        '이 가격에 이걸', '가격 거품',
        '비싸다',
    ],
}

# 브랜드/헤리티지 후보정용
# [v7] 핏/사이즈 후보정 비활성화 (v6 검증 방향 유지)
_CORRECTION_SKIP = {'핏/사이즈'}

NEG_TONE_WORDS = re.compile(
    r'별로|후줄근|실망|기대\s?이하|최악|환불|반품|비추|짜증|후진|망함|쓰레기|짜증나'
)
WEAK_BRAND_P = re.compile(
    r'또\s?사|다음에도\s?사|추가\s?구매|재구매|다음에\s?사'
)

ASPECT_RULES: dict[str, str] = {
    '핏/사이즈': (
        '의류 핏·사이즈 판단. 사이즈표 대비 실측 차이 언급 시 N. '
        '단순 "좋아요"는 X (구체적 핏/사이즈 언급 필요). 신발·양말 착용감은 기능성으로 분리.'
    ),
    '소재/내구성': (
        '소재 촉감·질감·두께·세탁 후 변형·보풀·탈색은 소재/내구성. '
        '끈/밴드 강도 문제도 포함. 단순 "좋다"는 X (소재 관련 구체 언급 필요).'
    ),
    '기능성': (
        '의류 착용감은 핏/사이즈로 분류, 신발/양말 착용감(쿠셔닝/폭신함)은 기능성. '
        '끈/밴드 소재 강성 문제는 소재/내구성으로 분리.'
    ),
    '디자인': (
        '색상·패턴·실루엣·외관 평가. 포장·박스 디자인은 X. '
        '사진과 색상 차이는 N. "예쁘다" 단독으로 충분히 P.'
    ),
    '브랜드/헤리티지': (
        '재구매·추천·강추·팬·단골·브랜드명(안다르/젝시믹스/룰루레몬/휠라) 직접 언급 + 긍정 어조 → P. '
        '실망·비추·환불·반품·다시는 안 산다 → N. '
        '제품 만족(디자인/핏/소재) 단독 언급 ≠ 브랜드 긍정 → X.'
    ),
    '가격/가치': (
        '가격 대비 만족은 P, 가격 대비 불만은 N. '
        '단순 가격 언급("6만원")은 X. 배송비 불만은 X.'
    ),
}


# ─────────────────────────────────────────────────────────────────────
# KiWi 토크나이저 (v4에서 이식)
# ─────────────────────────────────────────────────────────────────────

TEXT_CORRECTIONS = {
    '마음에 들': '마음에들다', '맘에 들': '마음에들다', '맘에들': '마음에들다',
    '맘에 듭': '마음에들다', '맘에듭': '마음에들다',
    '마음에들': '마음에들다', '마음에 드': '마음에들다 ', '맘에 드': '마음에들다 ',
    '고급진': '고급지다', '고급스럽': '고급지다', '고급스런': '고급지다',
    '부드럽진 않': '안부드럽다', '조이는 느낌도 없': '안조이다',
    '조이는 느낌 없': '안조이다', '불편함이 전혀 없': '안불편하다',
    '불편함 전혀 없': '안불편하다', '늘어남이 없': '안늘어나다',
    '늘어남 없': '안늘어나다', '유연성 없': '안유연하다',
    '후회없어': '후회없다', '후회 없': '후회없다',
    '사이즈 업': '사이즈업', '핼스': '헬스',
    '쵝오': '최고', '갠찬': '괜찮', '갠찮': '괜찮',
}

NORMALIZATION_DICT = {
    '젝시': '젝시믹스', '젝믹': '젝시믹스', '룰루': '룰루레몬', '필라': '휠라',
    '이뻐요': '예쁘다', '이쁘다': '예쁘다', '귀여워': '귀엽다',
    '따뜻해요': '따뜻하다', '따뜻': '따뜻하다', '따듯': '따뜻하다',
    '시원': '시원하다', '찰떡': '어울리다', '살아나다': '어울리다',
    '강추해요': '강추', '강추함': '강추', '추천해요': '추천',
    '답답': '답답하다', '안비침': '안비치다', '안비쳐': '안비치다',
    '잘입다': '잘맞다', '딱맞다': '잘맞다',
    '적당': '적당하다', '무난': '무난하다', '저렴': '저렴하다', '고급': '고급지다',
}

_STOPWORDS = {
    '네이버', '페이', '후기', '작성', '포인트', '구매', '제품', '상품', '주문', '배송',
    '이번', '선택', '사용', '생각', '평소', '하다', '되다', '그냥', '같다',
    '사다', '입다', '순간', '구입', '넘다', '알다', '보이다', '보다',
    '기준', '찾다', '덥다', '힘들다', '받다', '적다', '닿다', '나오다',
    '배송비', '살다', '할인', '기분', '요즘',
}

_USER_DICT_SET = {
    '안부드럽다', '안조이다', '안불편하다', '안늘어나다', '안유연하다',
    '마음에들다', '고급지다', '사이즈업',
    '신축성', '재구매', '정사이즈', '강추', '가성비', '가격대비',
    '잘맞다', '딱맞다', '안비치다', '따뜻하다', '시원하다', '저렴하다',
    '안다르', '젝시믹스', '룰루레몬', '휠라',
    'Y존', '와이존', '원단', '소재', '핏', '레깅스', '신축성',
}

_CORE_SINGLE = {'핏', '딱', '꽉', '쏙'}
_TARGET_TAGS  = {'NNG', 'NNP', 'XR', 'VA', 'VA-I', 'VA-R', 'VV', 'VV-I', 'VV-R'}
_NOUN_TAGS    = {'NNG', 'NNP', 'XR'}
_PRED_TAGS    = {'VA', 'VA-I', 'VA-R', 'VV', 'VV-I', 'VV-R'}
_PATCH_PATTERNS = [
    (re.compile(r'한\s*사이즈'),   '한사이즈'),
    (re.compile(r'셋\s*업'),       '셋업'),
    (re.compile(r'반\s*사이즈'),   '반사이즈'),
    (re.compile(r'하이\s*라이즈'), '하이라이즈'),
]

_kiwi = None

def _get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi(num_workers=os.cpu_count())
        for word in _USER_DICT_SET:
            _kiwi.add_user_word(word, 'NNP', score=0.0)
    return _kiwi


def _clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'http\S+|www\.\S+', ' ', text)
    text = re.sub(r'[^\w\s가-힣㄰-㆏]', ' ', text)
    text = re.sub(r'[\n\r\t]', ' ', text)
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def _advanced_pre_process(text: str) -> str:
    for wrong, right in TEXT_CORRECTIONS.items():
        text = text.replace(wrong, right)
    text = re.sub(r'(마음|맘)에\s*[가-힣]{0,2}\s*들\w*', '마음에들다 ', text)
    for pat, repl in _PATCH_PATTERNS:
        text = pat.sub(repl, text)
    text = re.sub(r'([가-힣]{2,4})(이|가|도|은|는)?\s+없([다어요습네음])', r'\1없\3', text)
    text = re.sub(r'([가-힣]{2,4})지[도는]?\s?않\w*', r' 안\1 ', text)
    text = re.sub(r'([가-힣]+)지[도는]?\s?못\w*', r' 못 \1', text)
    text = re.sub(r'없어[서선요]', '없다 ', text)
    text = re.sub(r'필요없\w*', '필요없다', text)
    return text


def _process_result(tokens) -> str:
    extracted, prefix = [], ''
    for t in tokens:
        tag = str(t.tag)
        if tag == 'MAG':
            if t.form in {'잘', '안', '못', '딱'}:
                prefix = t.form
            else:
                prefix = ''
            continue
        is_noun = tag in _NOUN_TAGS and (len(t.form) > 1 or t.form in _CORE_SINGLE)
        is_pred = tag in _PRED_TAGS
        if is_noun or is_pred:
            word = NORMALIZATION_DICT.get(t.form)
            if word is None:
                temp = t.form + '다' if is_pred else t.form
                word = NORMALIZATION_DICT.get(temp, temp)
            if prefix:
                compound = prefix + word
                if compound in NORMALIZATION_DICT:
                    word = NORMALIZATION_DICT[compound]
                elif compound in _USER_DICT_SET:
                    word = compound
                elif (compound + '다') in _USER_DICT_SET and is_pred:
                    word = compound + '다'
                elif prefix == '딱' and is_noun:
                    pass
            prefix = ''
            if word not in _STOPWORDS and (len(word) > 1 or word in _CORE_SINGLE):
                extracted.append(word)
        else:
            prefix = ''
    return ' '.join(extracted)


def preprocess_texts(texts: list[str]) -> list[str]:
    """텍스트 리스트 → KiWi 형태소 토큰 문자열 리스트."""
    kiwi    = _get_kiwi()
    cleaned = [_clean_text(t) for t in texts]
    pre     = [_advanced_pre_process(t) for t in cleaned]
    spaced  = kiwi.space(pre)
    spaced  = [re.sub(r'하이\s+라이즈', '하이라이즈', s) for s in spaced]
    tokenized = list(kiwi.tokenize(spaced))
    return [_process_result(tok) for tok in tokenized]


# ─────────────────────────────────────────────────────────────────────
# 1. 데이터 로드 / Few-shot 빌드
# ─────────────────────────────────────────────────────────────────────

def load_golden_set(path: str | Path = 'absa_golden_set_1000_v23.xlsx') -> pd.DataFrame:
    df = pd.read_excel(path)
    required = {'sample_idx', 'content_clean'} | set(ASPECTS)
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'골든셋에 컬럼 누락: {missing}')
    if 'tokens' not in df.columns:
        print('[v5] tokens 컬럼 없음 → KiWi 토크나이저로 자동 생성 중...')
        df['tokens'] = preprocess_texts(df['content_clean'].tolist())
        print(f'  완료: {len(df)}건')
    return df


def build_few_shot_examples(
    golden_df: pd.DataFrame,
    n_per_class: int = 3,
    seed: int = 42,
) -> dict[str, list[tuple[str, str]]]:
    priority_idx = {10, 74, 502}
    result: dict[str, list[tuple[str, str]]] = {}
    for aspect in ASPECTS:
        examples: list[tuple[str, str]] = []
        for label in LABELS:
            subset = golden_df[golden_df[aspect] == label].copy()
            if subset.empty:
                continue
            selected_rows: list[pd.Series] = []
            prio = subset[subset['sample_idx'].isin(priority_idx)]
            for _, row in prio.iterrows():
                if len(selected_rows) < n_per_class:
                    selected_rows.append(row)
            rest = subset[~subset['sample_idx'].isin(priority_idx)].copy()
            remaining_n = n_per_class - len(selected_rows)
            if remaining_n > 0 and len(rest) > 0:
                rest = rest.sample(frac=1, random_state=seed)
                rest['_len'] = rest['content_clean'].str.len()
                rest_sorted = rest.sort_values('_len').reset_index(drop=True)
                n_rest = len(rest_sorted)
                idxs = [int(i * (n_rest - 1) / max(remaining_n - 1, 1)) for i in range(remaining_n)]
                idxs = sorted(set(idxs))[:remaining_n]
                for i in idxs:
                    selected_rows.append(rest_sorted.iloc[i])
            for row in selected_rows[:n_per_class]:
                examples.append((str(row['content_clean']), label))
        result[aspect] = examples
    return result


# ─────────────────────────────────────────────────────────────────────
# 2. 배치 추론
# ─────────────────────────────────────────────────────────────────────

def build_batch_examples(
    golden_df: pd.DataFrame,
    n_examples: int = 6,
    seed: int = 42,
) -> list[tuple[str, dict[str, str]]]:
    """속성당 P/N 예시 최소 1건 강제 포함 (n_examples=6 기본)."""
    df = golden_df.copy()
    selected_rows = []
    seen_idx = set()

    for asp in ASPECTS:
        pool = df[df[asp].isin(['P', 'N']) & ~df.index.isin(seen_idx)]
        if len(pool) > 0:
            row = pool.sample(1, random_state=seed).iloc[0]
            selected_rows.append(row)
            seen_idx.add(row.name)

    remaining_n = n_examples - len(selected_rows)
    if remaining_n > 0:
        df['_non_x'] = sum((df[asp].isin(['P', 'N'])).astype(int) for asp in ASPECTS)
        candidates = df[~df.index.isin(seen_idx)].sort_values('_non_x', ascending=False)
        for _, row in candidates.head(remaining_n).iterrows():
            selected_rows.append(row)

    examples = []
    for row in selected_rows[:n_examples]:
        labels = {asp: str(row[asp]) for asp in ASPECTS}
        examples.append((str(row['content_clean']), labels))
    return examples


def build_batch_prompt(
    content: str,
    examples: list[tuple[str, dict[str, str]]],
) -> str:
    lines = [
        '한국어 애슬레저 리뷰를 6가지 속성별로 각각 P/N/X로 분류하세요.',
        'P=긍정 언급, N=부정 언급, X=해당 속성이 전혀 언급되지 않음.',
        '',
        '판단 기준:',
        '- 핏/사이즈 X: 핏·사이즈·기장·허리·어깨·라인 직접 언급이 없으면 반드시 X. "편해요" "좋아요" "찰떡" "딱이에요" "가볍다" 단독은 X. 사이즈 수치(cm/kg) 또는 핏 관련 단어 없으면 X.',
        '- 브랜드/헤리티지 P: 재구매 의사·브랜드 충성도·전반 만족이 느껴지면 P. 브랜드명 없어도 "또 살거예요" "계속 쓸 것 같다" "강추" 등은 P. 단, 단순 상품 칭찬(예쁘다·편하다 단독)은 X.',
        '- 브랜드/헤리티지 N: 실망·비추·환불·반품·다시는 안 산다 등 브랜드 불신.',
        '- 가격/가치 P: 가성비·저렴·합리적 등 가격 만족 명시. 단순 가격 언급은 X.',
        '- X는 해당 속성이 완전히 없는 경우만. 간접 언급도 P 또는 N으로 판단.',
        '',
        '반드시 아래 형식으로만 출력. 다른 설명 절대 금지.',
        '',
    ]
    for ex_content, ex_labels in examples:
        lines.append(f'리뷰: "{ex_content}"')
        for asp in ASPECTS:
            lines.append(f'{asp}: {ex_labels.get(asp, "X")}')
        lines.append('')

    lines.append(f'리뷰: "{content}"')
    lines.append(f'{ASPECTS[0]}:')
    return '\n'.join(lines)


def parse_batch_response(text: str) -> dict[str, str]:
    full_text = f'{ASPECTS[0]}: {text}'
    result = {asp: 'X' for asp in ASPECTS}
    for line in full_text.split('\n'):
        line = line.strip()
        for asp in ASPECTS:
            if line.startswith(asp):
                after = line[len(asp):].lstrip(':').strip()
                for ch in after:
                    if ch in ('P', 'N', 'X'):
                        result[asp] = ch
                        break
    return result


def call_exaone_batch(
    prompt: str,
    model: str = 'exaone3.5:7.8b',
    temperature: float = 0.1,
    max_tokens: int = 120,
    retries: int = 3,
) -> dict[str, str]:
    import ollama
    fallback = {asp: 'X' for asp in ASPECTS}
    for attempt in range(retries):
        try:
            resp = ollama.generate(
                model=model,
                prompt=prompt,
                options={'temperature': temperature, 'num_predict': max_tokens},
            )
            return parse_batch_response(resp['response'])
        except Exception as e:
            if attempt < retries - 1:
                print(f'[call_exaone_batch] 오류 ({attempt + 1}/{retries}): {e} — 재시도 중...')
                time.sleep(2)
            else:
                print(f'[call_exaone_batch] 최종 실패 (all X): {e}')
    return fallback


# ─────────────────────────────────────────────────────────────────────
# 3. [v5 핵심] apply_trigger_correction — 전 속성으로 확대
# ─────────────────────────────────────────────────────────────────────

def apply_trigger_correction(
    content: str,
    tokens: str,
    llm_preds: dict[str, str],
) -> dict[str, str]:
    """
    [v5] LLM 예측이 X일 때, tokens(형태소) 기반 트리거 매칭으로 P/N 후보정.
    전 속성에 적용 (v3는 브랜드/헤리티지만).

    tokens 기반 매칭으로 불규칙 활용 커버:
      "예뻐요" → tokens "예쁘다" → 트리거 '예쁘' 매칭 ✅
      "부드러워요" → tokens "부드럽다" → 트리거 '부드럽' 매칭 ✅

    LLM 결정을 override하지 않고, LLM=X인 경우에만 후보정.
    → false positive 방지 (v4 실패 원인 해소)
    """
    result = llm_preds.copy()

    for asp in ASPECTS:
        # [v7] 핏/사이즈 후보정 비활성화
        if asp in _CORRECTION_SKIP:
            continue

        if result[asp] != 'X':
            continue  # LLM이 이미 P/N 확정 → 유지

        p_hit = any(kw in tokens for kw in TRIGGERS_P.get(asp, []))
        n_hit = any(kw in tokens for kw in TRIGGERS_N.get(asp, []))

        if asp == '브랜드/헤리티지':
            # 브랜드는 추가 검증 로직 유지 (v3 로직)
            neg_tone = bool(NEG_TONE_WORDS.search(content))
            weak_p   = bool(WEAK_BRAND_P.search(content))
            if n_hit and not p_hit:
                result[asp] = 'N'
            elif p_hit and not n_hit:
                if not (weak_p and neg_tone):
                    result[asp] = 'P'
        else:
            # 그 외 속성: P/N 단독 매칭 시 후보정, AMBIGUOUS는 X 유지
            if n_hit and not p_hit:
                result[asp] = 'N'
            elif p_hit and not n_hit:
                result[asp] = 'P'

    return result


# ─────────────────────────────────────────────────────────────────────
# 4. End-to-end 추론
# ─────────────────────────────────────────────────────────────────────

def predict_one(
    content: str,
    tokens: str,
    batch_examples: list[tuple[str, dict[str, str]]],
) -> dict[str, str]:
    """
    [v5] LLM 전량 판단 → tokens 기반 전속성 후보정.

    Stage 1 확정 → LLM 스킵 로직 제거 (v4 실패 원인).
    LLM이 모든 속성 최종 판단 후, X 예측에 한해 tokens 트리거로 후보정.
    """
    prompt     = build_batch_prompt(content, batch_examples)
    llm_result = call_exaone_batch(prompt)
    return apply_trigger_correction(content, tokens, llm_result)


def predict_dataframe(
    df: pd.DataFrame,
    few_shots: dict[str, list[tuple[str, str]]],
    content_col: str = 'content_clean',
    tokens_col: str = 'tokens',
    show_progress: bool = True,
    checkpoint_path: str | Path | None = None,
    checkpoint_every: int = 50,
    golden_path: str | Path = 'absa_golden_set_1000_v23.xlsx',
    workers: int = 2,
) -> pd.DataFrame:
    """
    [v5] DataFrame 일괄 추론.
    - tokens 컬럼 없으면 자동 생성
    - LLM 전량 판단 + 전속성 tokens 후보정
    - ThreadPoolExecutor(workers=2) 병렬 추론
    - 체크포인트 유지 (50건마다 CSV + 재시작 이어받기)
    """
    if tokens_col not in df.columns:
        print(f'[v5] {tokens_col} 컬럼 없음 → KiWi 자동 생성 중...')
        df = df.copy()
        df[tokens_col] = preprocess_texts(df[content_col].tolist())
        print(f'  완료: {len(df)}건')

    checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

    golden         = load_golden_set(golden_path)
    batch_examples = build_batch_examples(golden, n_examples=6)

    start_idx  = 0
    preds_list: list[dict[str, str]] = []
    if checkpoint_path and checkpoint_path.exists():
        done_df    = pd.read_csv(checkpoint_path)
        start_idx  = len(done_df)
        preds_list = done_df[ASPECTS].to_dict('records')
        print(f'[체크포인트 복구] {start_idx:,}건 이어받기 — 남은 {len(df) - start_idx:,}건 계속')

    remaining   = df.iloc[start_idx:].reset_index(drop=True)
    contents    = remaining[content_col].tolist()
    tokens_list = remaining[tokens_col].tolist()

    iterable = tqdm(range(len(remaining)), desc='추론(v9-핏규칙강화)') \
               if show_progress else range(len(remaining))

    def _infer(i: int) -> tuple[int, dict[str, str]]:
        return i, predict_one(str(contents[i]), str(tokens_list[i]), batch_examples)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures    = {ex.submit(_infer, i): i for i in range(len(remaining))}
        results_map: dict[int, dict[str, str]] = {}

        for fut in as_completed(futures):
            i, pred = fut.result()
            results_map[i] = pred
            if show_progress:
                iterable.update(1)

            if checkpoint_path and len(results_map) % checkpoint_every == 0:
                ordered = [results_map[j] for j in range(len(results_map)) if j in results_map]
                if len(ordered) == len(results_map):
                    temp = df.iloc[:start_idx + len(ordered)].copy()
                    for asp in ASPECTS:
                        temp[asp] = ([p[asp] for p in preds_list] +
                                     [p[asp] for p in ordered])
                    temp.to_csv(checkpoint_path, index=False)

    if show_progress:
        iterable.close()

    ordered_preds = [results_map[i] for i in range(len(remaining))]
    preds_list.extend(ordered_preds)

    result = df.copy()
    for aspect in ASPECTS:
        result[aspect] = [p[aspect] for p in preds_list]

    if checkpoint_path:
        result.to_csv(checkpoint_path, index=False)

    return result


# ─────────────────────────────────────────────────────────────────────
# 5. 검증
# ─────────────────────────────────────────────────────────────────────

def evaluate(
    pred_df: pd.DataFrame,
    gold_df: pd.DataFrame,
    join_key: str = 'sample_idx',
) -> dict:
    from sklearn.metrics import f1_score, classification_report

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
    print('═' * 60)
    print(f"  Macro-F1: {eval_result['macro_f1']:.4f}")
    print('═' * 60)
    for aspect in ASPECTS:
        f1   = eval_result['per_aspect_f1'][aspect]
        flag = '✅' if f1 >= 0.60 else '⚠️ ' if f1 >= 0.45 else '❌'
        print(f'  {flag} {aspect:<14} F1={f1:.4f}')
    print()
    for aspect in ASPECTS:
        print(f'\n[{aspect}] Confusion Matrix:')
        print(eval_result['confusion'][aspect])
        print(f'\n[{aspect}] Classification Report:')
        print(eval_result['per_aspect_report'][aspect])


def diagnose_low_f1_aspect(eval_result: dict, threshold: float = 0.60) -> list[str]:
    return [a for a, f1 in eval_result['per_aspect_f1'].items() if f1 < threshold]


def extract_misclassified(
    pred_df: pd.DataFrame,
    gold_df: pd.DataFrame,
    aspect: str,
    join_key: str = 'sample_idx',
) -> pd.DataFrame:
    m    = pred_df.merge(gold_df, on=join_key, suffixes=('_pred', '_gold'))
    miss = m[m[f'{aspect}_pred'] != m[f'{aspect}_gold']]
    return miss[[join_key, 'content_clean', f'{aspect}_pred', f'{aspect}_gold']]
