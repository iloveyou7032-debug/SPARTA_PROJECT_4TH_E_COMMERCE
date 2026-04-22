from __future__ import annotations

import json
import re
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
from playwright.sync_api import sync_playwright, Page, Response


# =========================================================
# 설정
# =========================================================
STORE_URL = "https://brand.naver.com/fila"

# 전체상품 카테고리 URL
# 1페이지: ?cp=1 형태이지만 ?st=POPULAR&dt=IMAGE&page=1&size=40 도 동작함
# 2페이지~: ?st=POPULAR&dt=IMAGE&page=N&size=40
PRODUCT_LIST_BASE_URL = (
    "https://brand.naver.com/fila/category/f78045970ada40cabd523e5cb57b5863"
    "?st=POPULAR&dt=IMAGE&page={page}&size=40"
)
PRODUCT_LIST_TOTAL_PAGES = 33  # 확인된 총 페이지 수 (33페이지 × 40개 = 약 1320개)

# 스크립트 위치 기준으로 상대 경로 자동 계산
# 파일이 '김선영/crawling/' 안에 있으므로 부모 두 단계 위가 프로젝트 루트
_HERE = Path(__file__).resolve().parent  # 김선영/crawling/
_PROJECT_ROOT = _HERE.parent  # 김선영/
OUTPUT_DIR = _PROJECT_ROOT / "data" / "fila_naver_store_reviews"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_URLS_CSV = OUTPUT_DIR / "product_urls.csv"
PARTIAL_CSV = OUTPUT_DIR / "reviews_partial.csv"
FINAL_CSV = OUTPUT_DIR / "reviews_final.csv"
RAW_JSONL = OUTPUT_DIR / "reviews_raw.jsonl"
SINCE_2020_CSV = OUTPUT_DIR / "reviews_since_2020.csv"

START_DATE = pd.Timestamp("2020-01-01", tz="UTC")

HEADLESS = False
CHECKPOINT_EVERY_PRODUCTS = 10
REQUEST_DELAY_SEC = 1.2
REVIEW_PAGE_SIZE = 100

REVIEW_API_PATH = "/n/v1/contents/reviews/query-pages"
REVIEW_API_URL_FALLBACK = "https://brand.naver.com/n/v1/contents/reviews/query-pages"


# =========================================================
# 로그
# =========================================================
def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{now_str()}] {msg}")


# =========================================================
# 공통 유틸
# =========================================================
def click_if_exists(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=timeout):
                loc.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def scroll_to_bottom(page: Page, rounds: int = 4, pause_ms: int = 1000) -> None:
    for _ in range(rounds):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(pause_ms)


def normalize_datetime(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        if isinstance(value, (int, float)):
            return pd.to_datetime(
                value, unit="s", utc=True, errors="coerce"
            ).isoformat()
        return pd.to_datetime(value, utc=True, errors="coerce").isoformat()
    except Exception:
        return str(value)


def flatten_dict(d: Any, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    items: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                items.update(flatten_dict(v, new_key, sep=sep))
            elif isinstance(v, list):
                items[new_key] = json.dumps(v, ensure_ascii=False)
            else:
                items[new_key] = v
    else:
        items[parent_key] = d
    return items


def first_non_empty(*values: Any) -> Any:
    for v in values:
        if v is not None and v != "":
            return v
    return ""


def deep_get(d: dict, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def save_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_product_id_from_url(url: str) -> str:
    m = re.search(r"/products/(\d+)", url)
    return m.group(1) if m else ""


def _dedup(rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["product_id", "review_id"], keep="last")
    return df.to_dict("records")


# =========================================================
# 리뷰 없는 상품용 빈 행
# =========================================================
def make_empty_row(product_url: str, reason: str = "no_review") -> dict:
    product_id = extract_product_id_from_url(product_url)
    return {
        "product_url": product_url,
        "product_id": product_id,
        "review_id": None,
        "review_title": None,
        "review_body": "None",
        "rating": None,
        "helpful_count": None,
        "review_date": None,
        "reviewer_id": None,
        "reviewer_nickname": None,
        "reviewer_grade": None,
        "review_type": None,
        "review_service_type": None,
        "review_content_class": None,
        "product_option": None,
        "size_info": None,
        "keywords": None,
        "attach_count": None,
        "is_modified": None,
        "modified_date": None,
        "is_experience": None,
        "is_purchase_confirmed": None,
        "reply_count": None,
        "raw_json": None,
        "collect_status": reason,
    }


# =========================================================
# 체크포인트 저장
# =========================================================
def save_checkpoint(rows: list[dict], path: Path, label: str) -> None:
    if not rows:
        log(f"{label}: 저장할 데이터 없음")
        return

    df = pd.DataFrame(rows)
    has_review = df[df["review_id"].notna() & (df["review_id"] != "")]
    no_review = df[df["review_id"].isna() | (df["review_id"] == "")]

    if not has_review.empty:
        has_review = has_review.drop_duplicates(
            subset=["product_id", "review_id"], keep="last"
        )

    df_out = pd.concat([has_review, no_review], ignore_index=True)
    df_out.to_csv(path, index=False, encoding="utf-8-sig")

    total_products = df_out["product_id"].nunique()
    review_rows = len(has_review)
    no_review_cnt = no_review["product_id"].nunique()

    log(f"{label}: 저장 완료 → {path}")
    log(
        f"  고유 상품 수: {total_products}  "
        f"리뷰 행: {review_rows}  "
        f"리뷰 없는 상품: {no_review_cnt}"
    )

    preview_cols = [
        c
        for c in [
            "product_id",
            "review_id",
            "rating",
            "helpful_count",
            "review_date",
            "review_body",
        ]
        if c in df_out.columns
    ]
    if preview_cols and not has_review.empty:
        print("\n[최근 3건 미리보기]")
        print(has_review[preview_cols].tail(3).to_string(index=False))
        print()


# =========================================================
# 상품 URL 수집 (페이지 URL 직접 방문)
# =========================================================
def _collect_urls_from_current_page(page: Page, urls: set) -> int:
    """현재 페이지에서 상품 URL 수집 후 신규 추가 수 반환"""
    prev = len(urls)
    for anchor in page.locator("a[href*='/products/']").all():
        try:
            href = anchor.get_attribute("href", timeout=500) or ""
            if "/products/" in href:
                if href.startswith("/"):
                    href = "https://brand.naver.com" + href
                urls.add(href.split("?")[0].split("#")[0])
        except Exception:
            continue
    return len(urls) - prev


def collect_product_urls(page: Page) -> list[str]:
    log(f"상품 URL 수집 시작 (총 {PRODUCT_LIST_TOTAL_PAGES}페이지)")

    # 전체상품 1페이지 진입 (cp=1 방식)
    first_url = (
        "https://brand.naver.com/fila/category/" "f78045970ada40cabd523e5cb57b5863?cp=1"
    )
    page.goto(first_url, wait_until="domcontentloaded", timeout=20000)

    # 상품 목록 및 페이지 버튼 로딩 대기
    try:
        page.wait_for_selector("a[href*='/products/']", timeout=15000)
    except Exception:
        log("  !! 1페이지 상품 로딩 실패")
        return []

    page.wait_for_timeout(1500)
    scroll_to_bottom(page, rounds=3, pause_ms=1000)
    page.wait_for_timeout(1000)

    urls: set[str] = set()
    current_page = 1

    while current_page <= PRODUCT_LIST_TOTAL_PAGES:
        added = _collect_urls_from_current_page(page, urls)
        log(
            f"  [{current_page}/{PRODUCT_LIST_TOTAL_PAGES}] "
            f"신규 {added}개 (누적 {len(urls)}개)"
        )

        if current_page >= PRODUCT_LIST_TOTAL_PAGES:
            break

        next_page = current_page + 1

        # ── 다음 페이지 버튼 클릭 ──────────────────────────
        # 전략 1: data-shp-contents-id 속성으로 찾기 (가장 정확)
        clicked = False
        try:
            btn = page.locator(f"a[data-shp-contents-id='{next_page}']").first
            if btn.is_visible(timeout=3000):
                btn.click()
                clicked = True
                log(f"    → {next_page}페이지 버튼 클릭 (data-shp-contents-id)")
        except Exception:
            pass

        # 전략 2: '다음' 버튼 클릭 (10페이지 단위 넘어갈 때)
        if not clicked:
            try:
                # 다음 버튼: aria-label 또는 텍스트로 찾기
                next_btn = page.locator(
                    "a.hyY6CXtbcn:has-text('다음'), "
                    "a[role='menuitem']:has-text('다음'), "
                    "a[aria-label='다음 페이지']"
                ).first
                if next_btn.is_visible(timeout=3000):
                    next_btn.click()
                    clicked = True
                    log(f"    → '다음' 버튼 클릭 ({next_page}페이지로)")
            except Exception:
                pass

        # 전략 3: 텍스트가 next_page인 a 태그 클릭
        if not clicked:
            try:
                btn = page.locator(f"a[role='menuitem']:has-text('{next_page}')").first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    clicked = True
                    log(f"    → {next_page}페이지 버튼 클릭 (role=menuitem)")
            except Exception:
                pass

        if not clicked:
            log(f"  !! {next_page}페이지 버튼 클릭 실패 → 수집 종료")
            break

        # 페이지 전환 완료 대기
        try:
            page.wait_for_selector("a[href*='/products/']", timeout=15000)
        except Exception:
            log(f"  !! {next_page}페이지 로딩 타임아웃")
            break

        page.wait_for_timeout(1500)
        scroll_to_bottom(page, rounds=3, pause_ms=1000)
        page.wait_for_timeout(1000)

        current_page = next_page
        time.sleep(0.8)

    product_urls = sorted(urls)
    pd.DataFrame({"product_url": product_urls}).to_csv(
        PRODUCT_URLS_CSV, index=False, encoding="utf-8-sig"
    )
    log(f"상품 URL 수집 완료: {len(product_urls)}개 → {PRODUCT_URLS_CSV}")
    return product_urls


# =========================================================
# 리뷰 수집 (응답 인터셉트 방식)
# =========================================================
def collect_reviews_for_product(page: Page, product_url: str) -> tuple[list[dict], str]:
    fallback_product_id = extract_product_id_from_url(product_url)

    first_response_data: dict = {}
    captured_payload: dict = {}
    captured_url_store: dict = {}

    def handle_response(resp: Response) -> None:
        try:
            if REVIEW_API_PATH not in resp.url:
                return
            if resp.request.method != "POST":
                return
            if first_response_data:
                return
            try:
                post_data = resp.request.post_data or "{}"
                captured_payload.update(json.loads(post_data))
                captured_url_store["url"] = resp.url
            except Exception:
                pass
            body = resp.json()
            first_response_data.update(body)
            log(
                f"  1페이지 캡처 성공 "
                f"(totalPages={body.get('totalPages')}, "
                f"totalElements={body.get('totalElements')})"
            )
        except Exception as e:
            log(f"  응답 캡처 오류: {e}")

    page.on("response", handle_response)
    page.goto(product_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    clicked = click_if_exists(
        page,
        [
            "[role='tab']:has-text('리뷰')",
            "button:has-text('리뷰')",
            "a:has-text('리뷰')",
            "text=리뷰",
        ],
        timeout=5000,
    )

    if not clicked:
        page.remove_listener("response", handle_response)
        log("  리뷰 탭 클릭 실패")
        return [], "failed"

    deadline = time.time() + 8
    while not first_response_data and time.time() < deadline:
        page.wait_for_timeout(300)

    page.remove_listener("response", handle_response)

    if not first_response_data:
        log("  응답 캡처 실패 → 리뷰 없는 상품으로 처리")
        return [], "no_review"

    items = first_response_data.get("contents", [])
    total_pages = int(first_response_data.get("totalPages", 1))
    total_elements = int(first_response_data.get("totalElements", 0))

    if not items:
        log("  리뷰 없음")
        return [], "no_review"

    all_rows: list[dict] = []
    rows = [normalize_review_item(i, product_url, fallback_product_id) for i in items]
    all_rows.extend(rows)
    log(
        f"  page=1/{total_pages}  이번={len(rows)}건  "
        f"누적={len(all_rows)}건  (전체 약 {total_elements}건)"
    )

    if total_pages <= 1 or not captured_payload:
        return _dedup(all_rows), "ok"

    api_url = captured_url_store.get("url", REVIEW_API_URL_FALLBACK)

    for page_no in range(2, total_pages + 1):
        time.sleep(REQUEST_DELAY_SEC)

        payload = deepcopy(captured_payload)
        payload["page"] = page_no
        payload.pop("pageSize", None)
        payload.pop("size", None)
        payload["pageSize"] = REVIEW_PAGE_SIZE

        data = _fetch_via_evaluate(page, api_url, payload)
        if data is None:
            log(f"  page={page_no} fetch 실패 → 버튼 클릭 fallback")
            data = _click_page_fallback(page, page_no)
        if data is None:
            log(f"  page={page_no} 완전 실패 → 중단")
            break

        items = data.get("contents", [])
        if not items:
            break

        rows = [
            normalize_review_item(i, product_url, fallback_product_id) for i in items
        ]
        all_rows.extend(rows)
        log(
            f"  page={page_no}/{total_pages}  이번={len(rows)}건  누적={len(all_rows)}건"
        )

    return _dedup(all_rows), "ok"


def _fetch_via_evaluate(page: Page, api_url: str, payload: dict) -> dict | None:
    try:
        result = page.evaluate(
            """
            async ({ url, payload }) => {
                try {
                    const res = await fetch(url, {
                        method: "POST",
                        credentials: "include",
                        headers: {
                            "Content-Type": "application/json;charset=UTF-8",
                            "Accept": "application/json, text/plain, */*"
                        },
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) return { __status: res.status, __error: true };
                    return await res.json();
                } catch(e) {
                    return { __error: true, __msg: String(e) };
                }
            }
            """,
            {"url": api_url, "payload": payload},
        )
        if result and result.get("__error"):
            log(
                f"    fetch 오류 (status={result.get('__status', '?')}): {result.get('__msg', '')}"
            )
            return None
        return result
    except Exception as e:
        log(f"    evaluate 오류: {e}")
        return None


def _click_page_fallback(page: Page, target_page: int) -> dict | None:
    captured: dict = {}

    def handle(resp: Response) -> None:
        try:
            if REVIEW_API_PATH not in resp.url:
                return
            if resp.request.method != "POST":
                return
            if captured:
                return
            captured.update(resp.json())
        except Exception:
            pass

    page.on("response", handle)
    try:
        btn = page.locator(
            f"button:has-text('{target_page}'), a:has-text('{target_page}')"
        ).first
        if btn.is_visible(timeout=2000):
            btn.click(timeout=2000)
            deadline = time.time() + 5
            while not captured and time.time() < deadline:
                page.wait_for_timeout(300)
    except Exception as e:
        log(f"    fallback 클릭 오류: {e}")
    finally:
        page.remove_listener("response", handle)

    return dict(captured) if captured else None


# =========================================================
# 리뷰 아이템 정규화
# =========================================================
def normalize_review_item(
    item: dict, product_url: str, fallback_product_id: str
) -> dict:
    flat = flatten_dict(item)

    review_body = first_non_empty(
        item.get("reviewContent"),
        item.get("content"),
        item.get("body"),
        deep_get(item, "review", "reviewContent"),
        "",
    )
    rating = first_non_empty(
        item.get("reviewScore"),
        item.get("starScore"),
        item.get("score"),
        item.get("rating"),
        deep_get(item, "review", "reviewScore"),
        None,
    )
    product_id = first_non_empty(
        item.get("originProductNo"),
        item.get("productNo"),
        item.get("channelProductNo"),
        item.get("productId"),
        fallback_product_id,
    )
    review_id = first_non_empty(
        item.get("id"), item.get("reviewId"), item.get("reviewNo"), ""
    )
    helpful_count = first_non_empty(
        item.get("helpfulCount"),
        item.get("recommendCount"),
        item.get("likeCount"),
        item.get("helpCount"),
        0,
    )
    review_date = normalize_datetime(
        first_non_empty(
            item.get("createDate"),
            item.get("createdDate"),
            item.get("reviewCreatedDate"),
            item.get("registerDate"),
            item.get("writtenAt"),
            item.get("latestModifyDate"),
            "",
        )
    )
    review_title = first_non_empty(
        item.get("title"),
        item.get("reviewTitle"),
        item.get("headline"),
        item.get("summary"),
        "",
    )

    member_info = item.get("memberSummaryInfo") or item.get("member") or {}
    reviewer_id_masked = (
        member_info.get("memberId")
        or item.get("writerId")
        or item.get("memberId")
        or ""
    )
    reviewer_nickname = member_info.get("nickname") or item.get("nickname") or ""
    reviewer_grade = member_info.get("grade") or item.get("reviewerGrade") or ""

    review_type = item.get("reviewType") or ""
    review_service_type = item.get("reviewServiceType") or ""
    review_content_class = item.get("reviewContentClassType") or ""

    product_option = item.get("productOption") or item.get("option") or ""
    if isinstance(product_option, dict):
        product_option = json.dumps(product_option, ensure_ascii=False)

    size_info = item.get("sizeGuide") or item.get("size") or ""
    keywords = item.get("keywords") or item.get("tags") or []
    if isinstance(keywords, list):
        keywords = ",".join(str(k) for k in keywords)

    attach_count = item.get("totalAttachCount") or item.get("attachCount") or 0
    is_modified = item.get("modified") or item.get("isModified") or False
    modified_date = normalize_datetime(item.get("latestModifyDate") or "")
    is_experience = item.get("experienceGroup") or item.get("isExperience") or False
    is_purchase_confirmed = item.get("purchaseConfirm") or False
    reply_count = item.get("replyCount") or 0

    row = {
        "product_url": product_url,
        "product_id": product_id,
        "review_id": review_id,
        "review_title": review_title,
        "review_body": review_body,
        "rating": rating,
        "helpful_count": helpful_count,
        "review_date": review_date,
        "reviewer_id": reviewer_id_masked,
        "reviewer_nickname": reviewer_nickname,
        "reviewer_grade": reviewer_grade,
        "review_type": review_type,
        "review_service_type": review_service_type,
        "review_content_class": review_content_class,
        "product_option": product_option,
        "size_info": size_info,
        "keywords": keywords,
        "attach_count": attach_count,
        "is_modified": is_modified,
        "modified_date": modified_date,
        "is_experience": is_experience,
        "is_purchase_confirmed": is_purchase_confirmed,
        "reply_count": reply_count,
        "raw_json": json.dumps(item, ensure_ascii=False),
        "collect_status": "ok",
    }

    for k, v in flat.items():
        col = f"extra_{k}"
        if col not in row:
            row[col] = v

    return row


# =========================================================
# 2020년 이후 필터
# =========================================================
def filter_since_2020(df: pd.DataFrame) -> pd.DataFrame:
    if "review_date" not in df.columns:
        return df
    dt = pd.to_datetime(df["review_date"], utc=True, errors="coerce")
    return df[(dt >= START_DATE) | df["review_date"].isna()].copy()


# =========================================================
# 실행
# =========================================================
def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, channel="chrome")
        context = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        page = context.new_page()

        log("브라우저 열림 - 네이버 로그인 후 Enter를 눌러주세요")
        page.goto(STORE_URL, wait_until="domcontentloaded")
        input("\n>>> 로그인/인증이 완료되면 Enter를 눌러주세요: ")
        log("수집 시작")

        # 1) 기존 파일 전체 초기화 (처음부터 깨끗하게 시작)
        for old_file in [
            PRODUCT_URLS_CSV,
            PARTIAL_CSV,
            FINAL_CSV,
            RAW_JSONL,
            SINCE_2020_CSV,
        ]:
            if old_file.exists():
                old_file.unlink()
                log(f"기존 파일 삭제: {old_file.name}")

        # 2) 상품 URL 수집 (page=1 ~ page=33 직접 방문)
        product_urls = collect_product_urls(page)
        log(f"총 {len(product_urls)}개 상품 대상")
        # product_urls = product_urls[:5]  # 테스트 시 주석 해제

        # 3) 리뷰 수집 초기화
        done_product_ids: set[str] = set()
        done_review_keys: set[str] = set()
        all_rows: list[dict] = []

        # 4) 상품별 수집
        for idx, product_url in enumerate(product_urls, start=1):
            pid = extract_product_id_from_url(product_url)
            log(f"\n{'='*60}")
            log(f"[{idx}/{len(product_urls)}] 상품 ID={pid}")

            if pid in done_product_ids:
                log("  이미 처리됨 → 스킵")
                continue

            try:
                rows, status = collect_reviews_for_product(page, product_url)

                if status in ("no_review", "failed"):
                    reason = "no_review" if status == "no_review" else "collect_failed"
                    all_rows.append(make_empty_row(product_url, reason=reason))
                    done_product_ids.add(pid)
                    log(f"  → placeholder 행 추가 (reason={reason})")
                else:
                    new_rows = []
                    for r in rows:
                        key = f"{r.get('product_id')}_{r.get('review_id')}"
                        if key not in done_review_keys:
                            new_rows.append(r)
                            done_review_keys.add(key)

                    all_rows.extend(new_rows)
                    done_product_ids.add(pid)

                    if new_rows:
                        save_jsonl(
                            RAW_JSONL,
                            [
                                {
                                    "product_url": r.get("product_url"),
                                    "product_id": r.get("product_id"),
                                    "review_id": r.get("review_id"),
                                    "raw_json": r.get("raw_json"),
                                }
                                for r in new_rows
                            ],
                        )
                    log(
                        f"  신규 {len(new_rows)}건 추가 (전체 누적 행: {len(all_rows)})"
                    )

            except Exception as e:
                log(f"  !! 예외: {e}")
                all_rows.append(make_empty_row(product_url, reason="collect_failed"))
                done_product_ids.add(pid)

            if idx % CHECKPOINT_EVERY_PRODUCTS == 0:
                save_checkpoint(
                    all_rows, PARTIAL_CSV, label=f"중간저장 ({idx}/{len(product_urls)})"
                )

        # 4) 최종 저장
        log(f"\n{'='*60}")
        if not all_rows:
            log("수집된 데이터 없음")
            browser.close()
            return

        save_checkpoint(all_rows, FINAL_CSV, label="최종저장")

        df_final = pd.DataFrame(all_rows)
        total_products = df_final["product_id"].nunique()
        has_review_cnt = df_final[
            df_final["review_body"].notna() & (df_final["review_body"] != "None")
        ]["product_id"].nunique()
        no_review_cnt = total_products - has_review_cnt

        log(f"  고유 상품 ID 수: {total_products}")
        log(f"  리뷰 있는 상품: {has_review_cnt}")
        log(f"  리뷰 없는 상품: {no_review_cnt}")

        df_2020 = filter_since_2020(df_final)
        df_2020.to_csv(SINCE_2020_CSV, index=False, encoding="utf-8-sig")
        log(f"2020년 이후 필터: {len(df_2020)}행 → {SINCE_2020_CSV}")

        browser.close()
        log("완료!")


if __name__ == "__main__":
    run()
