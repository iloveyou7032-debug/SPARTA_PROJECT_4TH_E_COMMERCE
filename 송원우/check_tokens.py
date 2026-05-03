"""
check_tokens.py — 토큰화 검수 모듈 (v4.17 기반)

역할:
  1. inspect_tokens()   : 원문 | 형태소+품사 | 최종토큰 3단 비교 DataFrame 반환
  2. extract_oov()      : 미등록·오분석 의심 단어 추출 → USER_DICT 업데이트 후보 보고
  3. run_inspection()   : 샘플 추출부터 엑셀 저장까지 원클릭 실행
  4. find_variants()    : 뜻은 같지만 표현이 제각각인 토큰 클러스터 탐지
"""

import os
import re
import pandas as pd
from collections import Counter
from kiwipiepy import Kiwi

# ════════════════════════════════════════════════════════════
# 1. 상수 정의 (v4.12)
# ════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
# TEXT_CORRECTIONS — 형태소 분석 전 원문 강제 치환
# (구문 파편화 및 부정 문맥 감성 역전 방지)
# ─────────────────────────────────────────────
TEXT_CORRECTIONS = {
    # [마음에 들다] 변형 통일 — v4.17 보강: 띄어쓰기 없음 + 어미 단축형 추가
    '마음에 들': '마음에들다', '맘에 들': '마음에들다', '맘에들': '마음에들다', '맘에 듭': '마음에들다', '맘에듭': '마음에들다', '들어있어': '마음에들다', '들어있다고': '마음에들다',
    '마음에들': '마음에들다', '마음에 드': '마음에들다 ', '맘에 드': '마음에들다 ',
    # [고급지다] 형용사형 통일
    '고급진': '고급지다', '고급스럽': '고급지다', '고급스런': '고급지다',
    # [부정어 결합 - 소실 방지]
    '부드럽진 않': '안부드럽다', '조이는 느낌도 없': '안조이다', '조이는 느낌 없': '안조이다', '불편함이 전혀 없': '안불편하다', '불편함 전혀 없': '안불편하다', '늘어남이 없': '안늘어나다', '늘어남 없': '안늘어나다', '유연성 없': '안유연하다', '후회없어': '후회없다', '후회 없': '후회없다', '설명이 필요없': '설명필요없다', '설명 필요없': '설명필요없다',
    # [기타 오타 및 띄어쓰기 결합]
    '사이즈 업': '사이즈업', '핼스': '헬스', '적릭': '적립금', '쵝오': '최고', '오해': '오래', '갠찬': '괜찮', '갠찮': '괜찮', '내요': '네요', '내용': '네요', '톤톡': '톡톡',
}

# ─────────────────────────────────────────────
# USER_DICT — 사용자 사전 (핵심 키워드 및 강제 치환어 보호)
# ─────────────────────────────────────────────
USER_DICT = [
    # [강제 치환어 보호 (TEXT_CORRECTIONS 결과물)]
    '안부드럽다', '안조이다', '안불편하다', '안늘어나다', '안유연하다', '마음에들다', '고급지다', '설명필요없다', '사이즈업',
    # [핏/아이템/소재 속성]
    '스탠다드핏', '오버핏', '슬림핏', '테이퍼드핏', '와이드핏', '레귤러핏', '머슬핏', '크롭핏', '루즈핏', '가오리핏', '릴렉스핏',
    '조거팬츠', '롱슬리브', '숏슬리브', '브라탑', '크롭티', '바람막이', '윈드브레이커', '맨투맨', '아노락', '하프집업', '반집업', '집업', '바이커쇼츠', '와이드팬츠', '트랙팬츠', '자켓', '부츠', '코트',
    '기모', '심리스', '쿨링', '밴딩', '텐셀', '메쉬', '밑위', '밑단', 'Y존', '와이존', '넥라인', '암홀', '시보리', '안감', '지퍼', '포켓', '스트링', '기장', '기장감', '두께감', '터치감', '촉감', '원단', '재질', '소재',
    # [품질/평가 표현]
    '신축성', '복원력', '허리말림', '배말림', '압박감', '비침', '땀자국', '땀흡수', '통기성', '보풀', '물빠짐', '이염', '변형', '건조기', '세탁망', '내구성', '톡톡', '탄탄', '실패없다', '필요없다', '후회없다', '잘입다', '잘맞다', '딱맞다', '느낌', '착용감',
    # [체형/신체 부위/상태]
    '하비', '하체비만', '상비', '상체비만', '골반', '힙딥', '군살', '체형보정', '비율', '눈바디', '흡습속건', '흉곽압박', '승마살', '부담', '부각', '엉덩이', '허리', '다리', '종아리', '발목', '허벅지', '어깨', '팔뚝', '등살', '뱃살', '피부', '무릎', '복숭아', '살갗', '살갖', '발볼', '발등', '평발',
    # [사이즈/디자인/가격 속성]
    '사이즈', '길이', '색상', '색깔', '색감', '다른색', '가격',
    # [소비자 행동/트렌드/라이프스타일]
    '갓성비', '가심비', '색맛집', '핏맛집', '재구매', '정사이즈', '반업', '일업', '1업', '깔별', '깔별소장', '데일리템', '휘뚜루마뚜루', '문신템', '문신', '교복템', '교복', '인생바지', '인생레깅스', '강추', '최애바지', '최애템', '실내', '실외',
    '웜톤', '쿨톤', '톤다운', '무채색', '파스텔', '고프코어', '발레코어', '블록코어', '볼록코어', '올드머니룩', '와이투케이', 'Y2K', '스트릿룩', '스트릿패션', '캐주얼룩', '캐주얼', '스트릿', '스포티룩', '스포티',
    '출근룩', '데일리룩', '여행룩', '일상룩', '코디', '셋업', '바프', '바디프로필', '오운완', '원마일웨어', '투마일웨어', '꾸안꾸', '꾸꾸', '꾸꾸꾸',
    # [카테고리]
    '애슬레저', '에슬레저', '짐웨어', '웰니스', '리커버리', '요가복', '필라테스복', '러닝복', '런닝복', '러닝웨어', '러닝화', '골프웨어', '스윔웨어', '크로스핏', '웨이트', '데드리프트', '스쿼트', '하이킹', '등산', '캠핑', '움직임', '활동성', '슈레이스', '면소재', '운동', '운동복', '헬스',
    # [휠라]
    '휠라', '필라', '휠라코리아', '에샤페', '인터런', '페이토', '타르가', '오크먼트', '레이트레이서', '디스럽터', '디스럽터2', '코트디럭스', '스파게티', '휠라레이', '볼란테', '자마', '실버문', '메탈릭', '휠라키즈', '언더웨어', '헤리티지', '화이트라인', '테니스스커트', '테니스화', '리니어', '밀라노다운', '스포트', '발볼러', '칼발', '찍찍이', '벨크로', '어글리슈즈', '어글리', '청키슈즈', '청키', '빅로고',
    # [안다르]
    '안다르', '맨즈', '안다르맨즈', '에어스트', '에어리핏', '올데이핏', '에어쿨링', '뉴에어쿨링', '지니', '비프리', '에어무스', '릴렉스', '서스테이너블', '워터레깅스', '클라우드', '심포니', '에어캐치', '텐셀모달', '코듀라', '샤론', '프라나', '슬랙스', '폴로', '랩가디건', '커버업', '우븐팬츠', '워크레저', '비즈니스캐주얼', '9부', '8.2부', '7부', '임산부레깅스', '임산부', '임부복', 'Y존커버', '에어프라임', '아이스브리드', '노블스트라이프', '썸머라인', '피그먼트',
    # [젝시믹스]
    '젝시믹스', '젝시', '젝믹', '젝시맨', '젝시맨즈', '블랙라벨', '블라', '아이스페더', '젤라', '헤라', '텐션', '네오플렉시', '퍼포먼스', '젝시골프', '하이플렉시', '업텐션', '젤라인텐션', '핑거홀', '360N', '380N', '330N', '셀라', '셀라퍼펙션', '쿨파인', '브이업', '아이스페더컴포트', '트루플렉시', '인텐션', '하이서포트', '로우서포트', '미디움서포트', '젝시워터', '젝시코스메틱', '쉐르파',
    # [룰루레몬]
    '룰루레몬', '룰루', '얼라인', '스쿠바', '스위프틀리', '원더트레인', '패스트앤프리', '디파인', '메탈벤텍스', '에브리웨어', 'ABC팬츠', '아시아핏', '아시안핏', '글로벌핏', '스웨트라이프', '스윔라이프', '에듀케이터', '눌루', 'Nulu', '에버럭스', 'Everlux', '럭스트림', 'Luxtreme', '소프트스트림', 'Softstreme', '그로브팬츠', '얼라인탱크', '트래커쇼츠', '페이스브레이커', '루온', '실버레센트', '센스니트', '라이선투트레인', '써지', '라이크어클라우드', '에너지브라', '프리투비', '원더퍼프', '댄스스튜디오', '인비고레이트', '베이스페이스', '오티더블유', 'OTW', '차지필', '랩', '얼라인쇼츠', '릴렉스마사지듀얼볼', '듀얼볼',
    # [기타]
    '비즈니스웨어', '데일리웨어', '홈웨어', '이너웨어', '언더레이어', '이너탑', '이너팬츠', '레깅스팬츠', '레깅스', '레그워머', '팔토시', '암워머', '손목밴드', '요가매트', '빠른배송', '큰사람', '작은사람', '데일리바지', '네온그린', '한사이즈', '반사이즈', '간절기', '쿠션감', '반사이즈업', '반사이즈다운', '한사이즈업', '한사이즈다운', '합리적', '미끄럼방지', '콤비폴로', '어반액티브', '에어코튼', '스포츠양말', '가격대비', '윈드자켓', '밴드바지', '바스락', '생활복', '임부용', '기본티', '레이어드티', '레이어드용', '기본템',
    # [v4.13 도메인 어휘 승격 — NNG 후보 시트 상위]
    '디자인', '편안', '바지', '신발', '컬러', '라인', '불편', '최고', '쫀쫀', '타이트', '에어',
    '여름', '겨울', '가을',
    '5부', '4부', '3부',
    # [v4.14 도메인 어휘 승격 — NNG 후보 10000건 검수 결과 상위]
    # 아이템
    '팬츠', '티셔츠', '쇼츠', '양말', '팬티', '운동화', '가방', '모자', '스커트',
    # 신체 부위 / 핏 평가
    '가슴', '상의', '속옷', '여유',
    # 소재/구조
    '데님', '패드',
    # 품질 / ABSA 속성
    '세탁', '품절', '치수', '걱정',
    # 디자인 변형
    '투웨이', '플레어', '레이어', '스퀘어',
    # 브랜드 속성
    '로고', '실물', '매장',
    # 라이프스타일
    '여행', '활동', '활용', '일상',
    # [v4.15 P2 라운드 — NNG 후보 추가 승격]
    # 색상명
    '와이드', '블랙', '검정', '흰색', '화이트', '베이지', '그레이', '네이비', '브라운',
    # 평가 속성
    '고민', '처음', '마음',
    # 카테고리
    '요가', '골프', '밴드',
    # [v4.16 — 91K 검수 결과 추가 승격]
    # 아이템
    '청바지', '반바지',
    # 색상
    '실버',
    # 소재 / 디자인
    '스트레치', '소프트', '주머니',
    # 평가
    '가성비',
    # 라이프
    '출근',
    # [v4.17 시리즈/라인명 — 안다르]
    '시그니처', '에어데님', '에어엑스퍼트', '에어터치', '에어솔리드', '에어웜', '풀앤비치', '소프텐션',
    # [v4.17 시리즈/라인명 — 젝시믹스]
    '멜로우데이', '파워라이즈', '데일리페더', '썸머브리즈', '컴포트파인', '에코덱스', '덱스', 'xfk', 'xmk',
    # [v4.17 시리즈/라인명 — FILA]
    'coldwave', '리트모', '푸퍼', '니트트랙', '맥스', '하레핀', '벨로', '슬릭', '판테라', '플로트', '데시무스', '한소희',
    # [v4.17 시리즈/라인명 — 룰루레몬]
    '하이라이즈', '미드라이즈', '트레인', '패스트', '브레이커', '테크', '원더', '데이드리프트', '트라우저',
    # [v4.17 일반아이템 — 제외권장 포함 등록]
    '셔츠', '후드', '후디', '탱크탑', '카고', '부츠컷', '모크넥', '하프넥', '슬리브리스',
    '긴팔티', '반팔티', '카라티셔츠', '볼캡', '토트백', '백팩', '드로즈', '파자마', '저지', '재킷', '타이츠', '패딩',
    # [v4.17 일반소재]
    '플리스', '모달', '니트', '약기모', '스웻', '메모리', '나일론',
    # [v4.17 일반어]
    '착용', '라운드', '우먼즈', '키즈',
]

# ─────────────────────────────────────────────
# NORMALIZATION_DICT — 오타/동의어 통합 정규화
# ─────────────────────────────────────────────
NORMALIZATION_DICT = {
    '젝시': '젝시믹스', '젝믹': '젝시믹스', '젝시맨': '젝시믹스', '젝시맨즈': '젝시믹스', '젝스믹스': '젝시믹스',
    '안드르': '안다르',
    '래깅스': '레깅스', '조깅스': '레깅스',
    '시이즈': '사이즈', '사아즈': '사이즈', '서이즈': '사이즈',
    '룰루': '룰루레몬', '필라': '휠라', '휠라코리아': '휠라', '안다르맨즈': '안다르', '블라': '블랙라벨',
    '이뻐요': '예쁘다', '이쁘다': '예쁘다', '귀엽': '귀엽다', '귀여': '귀엽다', '커엽': '귀엽다', '귀여워': '귀엽다',
    '따뜻해요': '따뜻하다', '따뜻': '따뜻하다', '따듯': '따뜻하다', '캐쥬얼': '캐주얼', '추운': '춥다',
    '런닝': '러닝', '시원': '시원하다', '잘어울리다': '어울리다', '찰떡': '어울리다', '언더': '언더웨어',
    '조아요': '좋다', '조아여': '좋다', '져아': '좋다', '조아': '좋다', '조으': '좋다', '만적': '만족',
    '런닝복': '러닝복', '에슬레저': '애슬레저', '실패없': '실패없다',
    '살아나다': '어울리다', '살아난다': '어울리다',
    '강추해요': '강추', '강추함': '강추', '추천해요': '추천',
    '답답': '답답하다', '안답답': '안답답하다', '안비침': '안비치다', '안비쳐': '안비치다',
    # [핏 평가 통일 — 잘입다/딱맞다 → 잘맞다]
    # ※ '맞다': '잘맞다' 제거 — prefix '잘'+'맞다' 결합 시 '잘잘맞다' 중복 발생
    '잘입다': '잘맞다', '딱맞다': '잘맞다',
    # [오타 통일]
    '싸이즈': '사이즈', '브렌드': '브랜드', '평상복': '일상복',
    # [어간 통일 — 명사형 → '~하다/~지다' 형용사형]
    '적당': '적당하다', '무난': '무난하다', '넉넉': '넉넉하다',
    '저렴': '저렴하다', '고급': '고급지다',
    # [v4.17 영문 시리즈명 → 한글 정규화]
    'align': '얼라인', 'abc': 'ABC팬츠',
}

# ─────────────────────────────────────────────
# RAW_STOPWORDS — 불용어 사전
# ※ '없다', '실내', '실외' 영구 삭제 (감성/도메인 보존), 신규 노이즈 추가
# ─────────────────────────────────────────────
RAW_STOPWORDS = {
    '네이버', '페이', '후기', '작성', '등록', '포인트', '아울렛', '로그인', '사이트', '구매', '제품', '상품', '주문', '배송',
    '이번', '선택', '사용', '생각', '평소', '하다', '되다', '들르다', '들렀다', '특유', '햇빛', '조명',
    '따르다', '시선', '만들다', '측면', '덕분', '신다', '더하다', '필수', '쟁이다',
    # v4.18 — 강도 부사 6개 제거: '진짜', '너무', '정도', '많이', '조금' (INTENSITY_ADVERBS로 이동)
    '그냥', '아웃렛', '와이프', '않다', '안다', '내다', '같다', '울다', '그렇다', '이렇다', '어떻다', '저렇다',
    '사다', '입다', '순간', '구입', '종류', '달라다', '넘다', '부분', '알다', '보이다', '중요', '보다',
    '기준', '올리다', '내리다', '찾다', '장난', '죽다', '생명', '덥다', '힘들다',
    '삐지다', '받다', '적다', '착용', '닿다', '타사', '나오다', '넣다', '방식', '세일', '쎄일',
    '안파다', '배송비', '살다', '할인', '기분', '디다', '감안', '안나오다', '안입다', '요즘',
    # v4.18 — '약간' 제거 (INTENSITY_ADVERBS로 이동)
    '요즈음', '역쉬', '역시', '기다', '몰다', '모르다', '돌리다', '바람', '특가', '행사',
    '가리다', '리뷰', '안타다', '타다', '나가다', '쓰다', '딸아이', '아이', '아들', '남편', '아내', '부인', '재다',
    '동생', '언니', '누나', '오빠', '형', '문의', '교환', '감수', '입지', '나다', '치다', '박다',
    '짙다', '베란다', '일주일', '두다', '하이', '일반', '비하다', '비슷', '사람', '물어보다', '시즌', '날씨',
    '껴입다', '딱오다', '도움', '기부니', '차이', '돌다', '품목', '시키다', '전체', '느끼다',
}

FINAL_STOPWORDS = RAW_STOPWORDS - set(USER_DICT)

# ─────────────────────────────────────────────
# INTENSITY_ADVERBS — 감성 강도 부사 (v4.18 신규)
# MAG 태그로 분석되며, ABSA 검증·NetworkX·포지셔닝 강도가중치 산출에 활용
# BERTopic 입력에서는 별도 컬럼(tokens_topic)으로 분리하여 토픽 키워드 노이즈 차단
# ─────────────────────────────────────────────
INTENSITY_ADVERBS = {
    # 강한 강조
    '매우', '엄청', '너무', '진짜', '정말', '무척', '아주', '되게', '훨씬',
    # 약한 강조
    '조금', '약간', '꽤', '많이', '정도',
    # 부정적 강조
    '별로', '전혀',
}

# 분석 대상 품사
CORE_SINGLE = {'핏', '딱', '꽉', '쏙'}
TARGET_TAGS = {'NNG', 'NNP', 'XR', 'VA', 'VA-I', 'VA-R', 'VV', 'VV-I', 'VV-R'}
NOUN_TAGS   = {'NNG', 'NNP', 'XR'}
PRED_TAGS   = {'VA', 'VA-I', 'VA-R', 'VV', 'VV-I', 'VV-R'}

# OOV 후보로 볼 수상한 태그 (Kiwi가 모르는 단어를 처리하는 방식)
SUSPICIOUS_TAGS = {'SW', 'SB', 'SL', 'UN', 'UNKNOWN'}

USER_DICT_SET = set(USER_DICT)

# 단어 경계 기반 USER_DICT 일괄 매칭 패턴 — 모듈 로드 시 1회 컴파일 (554개 동시 검색)
_DICT_SORTED  = sorted(USER_DICT_SET, key=len, reverse=True)  # 긴 단어 먼저 (prefix 오탐 방지)
_DICT_PATTERN = re.compile(
    r'(?<![가-힣A-Za-z0-9])(' + '|'.join(re.escape(w) for w in _DICT_SORTED) + r')(?![가-힣A-Za-z0-9])'
)

# v4.14 — Kiwi 분해 발생 단어. add_user_word(score=5.0)로 가중치 강화
HIGH_SCORE_WORDS = {
    '셋업', '신축성', '한사이즈', '반사이즈', 'Y존', '8.2부', '가격대비',
    '한사이즈업', '반사이즈업', '한사이즈다운', '반사이즈다운',
    '하이라이즈',  # v4.17.1 — 분해 지속으로 추가
}

# 정규화 사전 전체 커버리지 (key + value)
NORM_ALL = set(NORMALIZATION_DICT.keys()) | set(NORMALIZATION_DICT.values())

# 4개 사전 통합 커버리지 (v4.18: INTENSITY_ADVERBS 추가)
ALL_COVERED = USER_DICT_SET | NORM_ALL | FINAL_STOPWORDS | INTENSITY_ADVERBS

# ════════════════════════════════════════════════════════════
# 2. Kiwi 싱글톤 (reload 시 재초기화)
# ════════════════════════════════════════════════════════════

_kiwi: Kiwi | None = None

def get_kiwi() -> Kiwi:
    global _kiwi
    if _kiwi is None:
        print("Kiwi 초기화 중...")
        _kiwi = Kiwi(num_workers=os.cpu_count())
        for word in USER_DICT_SET:
            score = 5.0 if word in HIGH_SCORE_WORDS else 0.0
            _kiwi.add_user_word(word, 'NNP', score=score)
        print(f"  사용자 사전 {len(USER_DICT_SET)}개 등록 완료. (가중치 강화 {len(HIGH_SCORE_WORDS & USER_DICT_SET)}개)")
    return _kiwi

# ════════════════════════════════════════════════════════════
# 3. 전처리 함수 (v4.10과 동일)
# ════════════════════════════════════════════════════════════

def clean_text(text: str) -> str:
    import re
    if not isinstance(text, str):
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'http\S+|www\.\S+', ' ', text)
    text = re.sub(r'\S+@\S+', ' ', text)
    text = re.sub(r'[^\w\s가-힣㄰-㆏]', ' ', text)
    text = re.sub(r'[\n\r\t]', ' ', text)
    text = re.sub(r'(.)\1{2,}', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()

def advanced_pre_process(text: str) -> str:
    for wrong, right in TEXT_CORRECTIONS.items():
        text = text.replace(wrong, right)
    # [v4.17] 마음에 들다 변형 강화 — "마음에 쏙 들/마음에 들고/맘에 쏙" 등 부사 삽입형 캡처
    text = re.sub(r'(마음|맘)에\s*[가-힣]{0,2}\s*들\w*', '마음에들다 ', text)
    # [부정 결합 일반화] (P0): [명사+없다] / [형용사+않다] 무한 패턴을 정규식으로 통합
    # ex) "의미가 없다" → "의미없다", "변화 없네" → "변화없네"
    text = re.sub(r'([가-힣]{2,4})(이|가|도|은|는)?\s+없([다어요습네음])', r'\1없\3', text)
    # ex) "편하지 않아요" → "안편하요" (어미 손상되나 부정 의미는 보존)
    text = re.sub(r'([가-힣]{2,4})지[도는]?\s?않\w*', r' 안\1 ', text)
    text = re.sub(r'([가-힣]+)지[도는]?\s?못\w*', r' 못 \1', text)
    pattern = r'(하고|지만|아서|어서|니까|은데|는데|인데|고요|네요|대요|길래|았는데|었는데|이고)([가-힣])'
    text = re.sub(pattern, r'\1 \2', text)
    text = re.sub(r'없어[서선요]', '없다 ', text)
    text = re.sub(r'필요없\w*', '필요없다', text)
    return text

def process_result(tokens) -> str:
    extracted, prefix = [], ''
    for t in tokens:
        tag = str(t.tag)
        if tag == 'MAG':
            if t.form in {'잘', '안', '못', '딱'}:
                # 부정·결합 prefix → 다음 토큰과 결합 (기존 로직)
                prefix = t.form
                continue
            if t.form in INTENSITY_ADVERBS:
                # v4.18 — 강도 부사 단독 토큰 보존 (결합 금지)
                # 직전 prefix가 있으면 버리고(예: '잘 너무' 같은 비정상 패턴) 강도 부사만 남김
                prefix = ''
                extracted.append(t.form)
                continue
            # 그 외 MAG는 기존처럼 무시 (prefix 리셋)
            prefix = ''
            continue
        is_noun = tag in NOUN_TAGS and (len(t.form) > 1 or t.form in CORE_SINGLE)
        is_pred = tag in PRED_TAGS
        if is_noun or is_pred:
            word = NORMALIZATION_DICT.get(t.form)
            if word is None:
                temp = t.form + '다' if is_pred else t.form
                word = NORMALIZATION_DICT.get(temp, temp)
            # [v4.17] prefix 결합은 사전 등재된 경우만 인정 (임의 결합 noise 차단)
            # - '안조이/안부해보이/딱길이' 같은 사전 미등재 결합 → prefix 무시
            # - '딱'은 명사(NNG/NNP)와 결합 금지 (딱+길이/딱+엉덩이 차단)
            if prefix:
                compound = prefix + word
                if compound in NORMALIZATION_DICT:
                    word = NORMALIZATION_DICT[compound]
                elif compound in USER_DICT_SET:
                    word = compound
                elif (compound + '다') in USER_DICT_SET and is_pred:
                    word = compound + '다'
                elif prefix == '딱' and is_noun:
                    pass  # '딱+명사' 결합 금지 — word 단독
                # 그 외: 사전 미등재 결합 → prefix 버리고 word 단독
            prefix = ''
            if word not in FINAL_STOPWORDS and (len(word) > 1 or word in CORE_SINGLE):
                extracted.append(word)
        else:
            prefix = ''
    return ' '.join(extracted)

# ════════════════════════════════════════════════════════════
# 4. [핵심] inspect_tokens — 3단 비교 DataFrame
# ════════════════════════════════════════════════════════════

def inspect_tokens(texts: list[str], show_all_tags: bool = False) -> pd.DataFrame:
    """
    원문 | 형태소+품사 (전체) | 최종 토큰 3단 비교 DataFrame 반환.

    Parameters
    ----------
    texts          : 검수할 원문 리스트
    show_all_tags  : True → 모든 형태소 표시 / False → TARGET_TAGS만 표시

    Returns
    -------
    DataFrame  columns: [원문, 형태소_상세, 최종_토큰, user_dict_miss, 의심_단어]
    """
    kiwi = get_kiwi()
    cleaned   = [clean_text(t) for t in texts]
    processed = kiwi.space([advanced_pre_process(t) for t in cleaned])  # 배치 처리
    tokenized = list(kiwi.tokenize(processed))

    rows = []
    for orig, tok_list in zip(texts, tokenized):
        # 형태소 상세 (form/tag)
        if show_all_tags:
            detail = ' | '.join(f'{t.form}({t.tag})' for t in tok_list)
        else:
            detail = ' | '.join(
                f'{t.form}({t.tag})'
                for t in tok_list
                if str(t.tag) in TARGET_TAGS or str(t.tag) in SUSPICIOUS_TAGS
            )

        final_tokens = process_result(tok_list)
        token_set    = set(final_tokens.split())

        # USER_DICT 미적용 감지 — 사전 컴파일 패턴 1회 스캔 (554개 × 231K regex → 231K 1회)
        orig_hits = set(_DICT_PATTERN.findall(orig))
        missed = [
            w for w in orig_hits
            if w not in token_set and NORMALIZATION_DICT.get(w) not in token_set
        ]

        # 의심 단어: SUSPICIOUS_TAGS로 분석된 형태소
        suspicious = [
            f'{t.form}({t.tag})'
            for t in tok_list
            if str(t.tag) in SUSPICIOUS_TAGS and len(t.form) > 1
        ]

        # 3개 사전 미해당 + 실제로 이상한 토큰만
        uncovered = [
            tok for tok in token_set
            if tok not in ALL_COVERED
            and (
                bool(re.search(r'[0-9\W]', tok))
                or (len(tok) == 1 and tok not in CORE_SINGLE)
                or (not tok.endswith('다') and bool(re.search(r'[아어이]$', tok)))
            )
        ]

        rows.append({
            '원문':           orig,
            '형태소_상세':    detail,
            '최종_토큰':      final_tokens,
            'dict_미적용':    ', '.join(missed)     if missed     else '',
            '의심_단어':      ', '.join(suspicious) if suspicious else '',
            '사전미해당_토큰': ', '.join(sorted(uncovered)) if uncovered else '',
        })

    return pd.DataFrame(rows)

# ════════════════════════════════════════════════════════════
# 5. [핵심] extract_oov — USER_DICT 업데이트 후보 추출
# ════════════════════════════════════════════════════════════

def extract_oov(texts: list[str], top_n: int = 50) -> dict:
    """
    미등록·오분석 의심 단어를 추출해 USER_DICT 업데이트 후보를 보고한다.

    Returns
    -------
    dict with keys:
      'nng_candidates'   : USER_DICT에 없는 고빈도 NNG (일반명사) → 고유명사 등록 후보
      'dict_miss_report' : 원문에 USER_DICT 단어가 있는데 토큰에 안 잡힌 사례
      'suspicious_forms' : SUSPICIOUS_TAG 처리된 형태소 (Kiwi 미인식 단어)
    """
    kiwi = get_kiwi()
    cleaned   = [clean_text(t) for t in texts]
    processed = kiwi.space([advanced_pre_process(t) for t in cleaned])  # 배치 처리
    tokenized = list(kiwi.tokenize(processed))

    nng_counter      = Counter()
    dict_miss_all    = []
    suspicious_all   = Counter()
    uncovered_all    = Counter()

    for orig, tok_list in zip(texts, tokenized):
        final_tokens = process_result(tok_list)
        token_set    = set(final_tokens.split())

        for t in tok_list:
            tag = str(t.tag)
            # ① USER_DICT 미등록 NNG (2글자 이상, 불용어·정규화 사전 미포함)
            if tag == 'NNG' and len(t.form) >= 2 and t.form not in ALL_COVERED:
                nng_counter[t.form] += 1

            # ③ Kiwi 미인식 형태소
            if tag in SUSPICIOUS_TAGS and len(t.form) > 1:
                suspicious_all[f'{t.form}({tag})'] += 1

        # ② USER_DICT 단어가 원문에 있는데 최종 토큰에 없는 경우 — 컴파일 패턴 1회 스캔
        orig_hits = set(_DICT_PATTERN.findall(orig))
        missed = [
            w for w in orig_hits
            if w not in token_set and NORMALIZATION_DICT.get(w) not in token_set
        ]
        if missed:
            dict_miss_all.append({'원문': orig[:60], '미적용_단어': ', '.join(missed)})

        # ④ 이상 토큰 후보: 3개 사전 미해당 + 아래 조건 중 하나라도 해당
        #    - 숫자·특수문자 혼입 (정제 누락 의심)
        #    - 1글자 (CORE_SINGLE 제외)
        #    - 동사/형용사 어근이 '다'로 끝나지 않고 잔류 (process_result 누락 의심)
        for tok in token_set:
            if tok in ALL_COVERED:
                continue
            is_garbage   = bool(re.search(r'[0-9\W]', tok))
            is_single    = len(tok) == 1 and tok not in CORE_SINGLE
            is_bare_pred = not tok.endswith('다') and re.search(r'[아어이]$', tok)
            if is_garbage or is_single or is_bare_pred:
                uncovered_all[tok] += 1

    result = {
        'nng_candidates':   pd.DataFrame(
            nng_counter.most_common(top_n), columns=['단어', '빈도']
        ),
        'dict_miss_report': pd.DataFrame(dict_miss_all) if dict_miss_all
                            else pd.DataFrame(columns=['원문', '미적용_단어']),
        'suspicious_forms': pd.DataFrame(
            suspicious_all.most_common(top_n), columns=['형태소(태그)', '빈도']
        ),
        'uncovered_tokens': pd.DataFrame(
            uncovered_all.most_common(top_n), columns=['토큰', '빈도']
        ),
    }
    return result

# ════════════════════════════════════════════════════════════
# 6. run_inspection — 원클릭 실행 (샘플 추출 → 검수 → 저장)
# ════════════════════════════════════════════════════════════

def run_inspection(
    df: pd.DataFrame,
    sample_sizes: dict | None = None,
    content_col: str = 'content',
    brand_col: str   = 'brand',
    top_n: int       = 50,
    min_freq: int    = 2,
    edit_dist: int   = 1,
    save_path: str   = './step1_token_inspection_latest.xlsx',
) -> tuple[pd.DataFrame, dict]:
    """
    샘플 추출 → inspect_tokens → extract_oov → find_variants → 엑셀 저장.

    Parameters
    ----------
    df           : 마스터 DataFrame (clean_text 미적용 원본 권장)
    sample_sizes : {'안다르': 30, '젝시믹스': 30, 'FILA': 20, '룰루레몬': 20}
                   None이면 전체 데이터 사용
    content_col  : 텍스트 컬럼명
    brand_col    : 브랜드 컬럼명
    top_n        : OOV 후보 상위 N개
    min_freq     : find_variants 최소 빈도
    edit_dist    : find_variants 편집거리 허용값
    save_path    : 저장 경로 (None이면 저장 안 함)

    Returns
    -------
    (inspect_df, oov_report, variants_df)
    """
    # ── 샘플 추출 ────────────────────────────────────────────
    if sample_sizes:
        sample_df = pd.concat([
            df[df[brand_col] == brand].sample(
                n=min(n, len(df[df[brand_col] == brand])), random_state=42
            )
            for brand, n in sample_sizes.items()
            if brand in df[brand_col].values
        ], ignore_index=True).sample(frac=1, random_state=42).reset_index(drop=True)
    else:
        sample_df = df.copy()

    texts = sample_df[content_col].fillna('').astype(str).tolist()
    print(f"[검수 시작] 총 {len(texts)}건")

    # ── 3단 비교 ─────────────────────────────────────────────
    inspect_df = inspect_tokens(texts)
    inspect_df.insert(0, brand_col, sample_df[brand_col].values)

    # ── OOV 후보 ─────────────────────────────────────────────
    oov_report = extract_oov(texts, top_n=top_n)

    # ── 변형 표현 탐지 ───────────────────────────────────────
    print("[find_variants] 변형 표현 탐지 중...")
    variants_df = find_variants(texts, min_freq=min_freq, edit_dist=edit_dist)

    # ── 엑셀 저장 (시트 6개) ─────────────────────────────────
    if save_path:
        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            inspect_df.to_excel(writer, sheet_name='토큰검수',      index=False)
            oov_report['nng_candidates'].to_excel(writer,  sheet_name='NNG후보',       index=False)
            oov_report['dict_miss_report'].to_excel(writer, sheet_name='사전미적용',    index=False)
            oov_report['suspicious_forms'].to_excel(writer, sheet_name='미인식형태소',  index=False)
            oov_report['uncovered_tokens'].to_excel(writer, sheet_name='사전미해당토큰', index=False)
            variants_df.to_excel(writer, sheet_name='변형표현',     index=False)
        print(f"[저장 완료] {save_path}")

    # ── 콘솔 요약 ────────────────────────────────────────────
    miss_cnt  = (inspect_df['dict_미적용'] != '').sum()
    susp_cnt  = (inspect_df['의심_단어'] != '').sum()
    uncov_cnt = (inspect_df['사전미해당_토큰'] != '').sum()
    print(f"\n{'='*55}")
    print(f"  총 검수 건수        : {len(inspect_df)}")
    print(f"  dict 미적용 건수    : {miss_cnt}건")
    print(f"  의심 단어 건수      : {susp_cnt}건")
    print(f"  사전 미해당 토큰    : {uncov_cnt}건")
    print(f"  변형 클러스터       : {len(variants_df)}개")
    print(f"  NNG 후보 상위 5     : {oov_report['nng_candidates'].head(5)['단어'].tolist()}")
    print(f"{'='*55}\n")

    return inspect_df, oov_report, variants_df


# ════════════════════════════════════════════════════════════
# 7. find_variants — 동의어·오타·줄임말 변형 클러스터 탐지
# ════════════════════════════════════════════════════════════

# 한국어에서 자주 혼용되는 모음/자음 패턴 (정규화 후 같아지면 같은 단어로 간주)
_PHONETIC_NORM = [
    (r'이쁘', '예쁘'),    # 이쁘다 ↔ 예쁘다
    (r'따듯', '따뜻'),    # 따듯 ↔ 따뜻
    (r'캐쥬', '캐주'),    # 캐쥬얼 ↔ 캐주얼
    (r'런닝', '러닝'),    # 런닝 ↔ 러닝
    (r'갠찮', '괜찮'),    # 갠찮 ↔ 괜찮
    (r'갠찬', '괜찮'),
    (r'조으', '좋'),      # 조으다 ↔ 좋다
    (r'조아', '좋아'),    # 조아요 ↔ 좋아요
    (r'넘\b', '너무'),    # 넘 ↔ 너무
    (r'에슬', '애슬'),    # 에슬레저 ↔ 애슬레저
    (r'만족스럽', '만족'), # 만족스럽다 ↔ 만족
    (r'ㅎ+', ''),         # 잔류 자모음
    (r'ㅋ+', ''),
]


def _phonetic_key(token: str) -> str:
    key = token
    for pattern, repl in _PHONETIC_NORM:
        key = re.sub(pattern, repl, key)
    # 어미 변형 통일: '~해요/했어요/하다' → 어간만
    key = re.sub(r'(해요|했어요|하다|합니다|해서|하고)$', '하다', key)
    key = re.sub(r'(이에요|이에요|예요|입니다)$', '이다', key)
    return key


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def find_variants(
    texts: list[str],
    min_freq: int = 2,
    edit_dist: int = 1,
    top_n: int = 40,
) -> pd.DataFrame:
    """
    샘플 텍스트에서 '뜻은 같지만 표현이 제각각인' 토큰 클러스터를 탐지한다.

    탐지 방법 (3-track):
      A. 발음/모음 정규화 후 동일해지는 그룹 (이쁘다 ↔ 예쁘다)
      B. 편집 거리(Levenshtein) ≤ edit_dist인 쌍 (괜찮다 ↔ 갠찮다)
      C. 접두 포함 관계 — 짧은 쪽이 긴 쪽의 앞 2/3 이상 (젝시 ↔ 젝시믹스)

    Parameters
    ----------
    texts    : 원문 리스트 (clean_text 적용 전 원본)
    min_freq : 클러스터 내 총 빈도 합산 최솟값 (노이즈 제거)
    edit_dist: Levenshtein 허용 거리 (기본 1)
    top_n    : 반환할 상위 클러스터 수

    Returns
    -------
    DataFrame  columns: [대표형, 변형_목록, 각_빈도, 총빈도, 권장_처리]
    """
    kiwi = get_kiwi()
    cleaned   = [clean_text(t) for t in texts]
    processed = kiwi.space([advanced_pre_process(t) for t in cleaned])  # 배치 처리
    tokenized = list(kiwi.tokenize(processed))

    # 전체 최종 토큰 빈도 수집
    freq: Counter = Counter()
    for tok_list in tokenized:
        for tok in process_result(tok_list).split():
            freq[tok] += 1

    # min_freq 미만 제거
    tokens = [t for t, c in freq.items() if c >= min_freq]

    # ── Track A: 발음 정규화 키로 그룹핑 ─────────────────────
    phon_groups: dict[str, list[str]] = {}
    for tok in tokens:
        key = _phonetic_key(tok)
        phon_groups.setdefault(key, []).append(tok)
    phon_clusters = {k: v for k, v in phon_groups.items() if len(v) >= 2}

    # ── Track B: 편집 거리 클러스터링 ────────────────────────
    # 한국어 음절 단위 edit_dist=1은 무관 어휘를 대량 묶음 (좋다/크다/얇다 등)
    # → 3글자 이상 + '다'로 끝나지 않는 명사형만 허용 (형용사 어간 충돌 차단)
    edit_candidates = [
        t for t in tokens
        if len(t) >= 3 and not t.endswith('다')
    ]
    visited: set[str] = set()
    edit_clusters: list[list[str]] = []
    for i, a in enumerate(edit_candidates):
        if a in visited:
            continue
        group = [a]
        for b in edit_candidates[i + 1:]:
            if b in visited:
                continue
            if abs(len(a) - len(b)) > edit_dist:
                continue
            if _levenshtein(a, b) <= edit_dist:
                group.append(b)
                visited.add(b)
        if len(group) >= 2:
            visited.add(a)
            edit_clusters.append(group)

    # ── Track C: 접두 포함(줄임말) ───────────────────────────
    prefix_clusters: list[list[str]] = []
    long_tokens = [t for t in tokens if len(t) >= 4]
    short_tokens = [t for t in tokens if 2 <= len(t) < 4]
    for short in short_tokens:
        matched = [t for t in long_tokens if t.startswith(short) and len(t) >= len(short) * 1.5]
        if matched:
            prefix_clusters.append([short] + matched)

    # ── 결과 통합 ─────────────────────────────────────────────
    seen_sets: list[frozenset] = []
    rows = []

    def _add_cluster(group: list[str], method: str):
        fs = frozenset(group)
        # 이미 포함된 클러스터면 스킵
        if any(fs <= s or s <= fs for s in seen_sets):
            return
        seen_sets.append(fs)
        total = sum(freq[t] for t in group)
        if total < min_freq:
            return
        # 가장 빈도 높은 것을 대표형으로
        rep = max(group, key=lambda t: freq[t])
        variants = sorted(group, key=lambda t: -freq[t])
        freq_str = ', '.join(f'{t}({freq[t]})' for t in variants)

        # 권장 처리 자동 추론
        if method == 'prefix':
            action = f'NORMALIZATION_DICT: {rep!r} → 긴 형태로 통일 검토'
        elif any(_phonetic_key(a) == _phonetic_key(b) for a in group for b in group if a != b):
            action = f'NORMALIZATION_DICT: 변형들 → {rep!r} 로 통일'
        else:
            action = f'NORMALIZATION_DICT 또는 USER_DICT 추가 검토'

        rows.append({
            '대표형':    rep,
            '변형_목록': freq_str,
            '총빈도':    total,
            '탐지방법':  method,
            '권장_처리': action,
        })

    for key, group in phon_clusters.items():
        _add_cluster(group, 'phonetic')
    for group in edit_clusters:
        _add_cluster(group, 'edit_dist')
    for group in prefix_clusters:
        _add_cluster(group, 'prefix')

    if not rows:
        print("변형 클러스터가 발견되지 않았습니다. min_freq 또는 edit_dist를 조정해보세요.")
        return pd.DataFrame(columns=['대표형', '변형_목록', '총빈도', '탐지방법', '권장_처리'])

    result_df = (
        pd.DataFrame(rows)
        .sort_values('총빈도', ascending=False)
        .reset_index(drop=True)
        .head(top_n)
    )
    print(f"[find_variants] {len(result_df)}개 클러스터 탐지 완료")
    return result_df

    return inspect_df, oov_report
