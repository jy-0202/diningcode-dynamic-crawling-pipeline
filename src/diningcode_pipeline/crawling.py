"""
DiningCode 동적 크롤링 수집 모듈

서울 > 강남역의 공개 맛집 정보를 Selenium으로 제한적으로 수집하고
수집 직후 결과를 Raw CSV로 저장한다.

주요 흐름
1. Chrome WebDriver 생성
2. DiningCode 접속
3. 서울 > 강남역 선택
4. 최대 2회 스크롤
5. 카테고리별 상위 5개 음식점 후보 수집
6. source_url 기준 중복 제거
7. 상세정보 및 상위 3개 메뉴 수집
8. Raw CSV 저장
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import (
    BASE_URL,
    MAX_RESTAURANTS_PER_CATEGORY,
    MAX_SCROLLS,
    MAX_TOTAL_RESTAURANTS,
    RAW_DATA_DIR,
    RAW_HTML_DIR,
    TARGET_CITY,
    TARGET_REGION,
    TOP_MENU_COUNT,
    WAIT_TIMEOUT,
)

# ===========================================================
# 1. 기본 함수
# ===========================================================

def ensure_directory(directory: Path) -> Path:
    """지정한 폴더가 없으면 생성하고 경로를 반환한다."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_html_batch_directory() -> Path:
    """수집 시각을 이름으로 사용하는 Raw HTML 배치 폴더를 생성한다."""
    batch_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    batch_dir = RAW_HTML_DIR / batch_id

    return ensure_directory(batch_dir)


def save_raw_html(
    html: str,
    batch_dir: Path,
    file_name: str,
) -> Path:
    """Selenium으로 렌더링된 HTML을 Raw 파일로 저장한다."""
    file_path = batch_dir / file_name

    file_path.write_text(
        html,
        encoding='utf-8',
    )

    return file_path


def get_restaurant_rid(source_url: str) -> str:
    """DiningCode 상세 URL에서 rid 값을 추출한다."""
    parsed_url = urlparse(source_url)
    query_params = parse_qs(parsed_url.query)

    rid_values = query_params.get('rid')

    if not rid_values or not rid_values[0]:
        raise ValueError(
            f'상세 URL에서 rid를 찾지 못했습니다. {source_url}'
        )

    return rid_values[0]


def create_driver() -> tuple[webdriver.Chrome, WebDriverWait]:
    """Chrome WebDriver와 WebDriverWait 객체를 생성한다."""
    options = Options()
    options.add_argument('--start-maximized')

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    return driver, wait


# ===========================================================
# 2. 사이트 접속 및 지역 선택
# ===========================================================

def open_site(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """DiningCode 메인 페이지에 접속한다."""
    driver.get(BASE_URL)

    wait.until(
        EC.presence_of_element_located(
            (By.TAG_NAME, 'body')
        )
    )

    print('페이지 제목:', driver.title)
    print('현재 URL:', driver.current_url)


def select_region(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    city: str = TARGET_CITY,
    region: str = TARGET_REGION,
) -> None:
    """지역 선택 UI에서 서울 > 강남역을 선택한다."""
    region_button = driver.find_element(
        By.CSS_SELECTOR,
        'div.Top__Nav__KeyVisual .KeyVisual__Inner button',
    )
    region_button.click()

    wait.until(
        EC.presence_of_element_located(
            (By.CLASS_NAME, 'Location__Popup__Layer')
        )
    )

    city_button = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                (
                    '//button[contains(@class, "District__Item__Button") '
                    f'and normalize-space()="{city}"]'
                ),
            )
        )
    )
    city_button.click()

    region_button = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                (
                    '//button[contains(@class, "District__Item__Button")]'
                    f'[contains(., "{region}")]'
                ),
            )
        )
    )
    region_button.click()

    submit_button = wait.until(
        EC.element_to_be_clickable(
            (By.CLASS_NAME, 'Location__Popup__Submit')
        )
    )
    submit_button.click()

    wait.until(EC.url_contains('/foodrank/'))

    print(f'선택 지역: {city} > {region}')
    print(f'현재 URL: {driver.current_url}')


# ===========================================================
# 3. 결과 스크롤
# ===========================================================

def scroll_results(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    max_scrolls: int = MAX_SCROLLS,
) -> None:
    """결과 페이지를 제한된 횟수만큼 스크롤한다."""
    for scroll_count in range(max_scrolls):
        before_count = len(
            driver.find_elements(
                By.CSS_SELECTOR,
                'h2.Card__Section__Title',
            )
        )

        driver.execute_script(
            'window.scrollTo(0, document.body.scrollHeight);'
        )

        wait.until(
            lambda current_driver: len(
                current_driver.find_elements(
                    By.CSS_SELECTOR,
                    'h2.Card__Section__Title',
                )
            ) > before_count
        )

        after_count = len(
            driver.find_elements(
                By.CSS_SELECTOR,
                'h2.Card__Section__Title',
            )
        )

        print(
            f'스크롤 {scroll_count + 1}회 후 '
            f'카테고리 개수: {after_count}'
        )


# ===========================================================
# 4. 카테고리별 음식점 후보 수집
# ===========================================================

def collect_restaurant_list(
    driver: webdriver.Chrome,
) -> list[dict]:
    """
    카테고리별 상위 음식점 후보를 수집한다.

    중복 제거 전 목록을 반환하여
    이후 categories 통합에도 사용한다.
    """
    category_sections = driver.find_elements(
        By.CSS_SELECTOR,
        'section.Card__Section',
    )

    restaurant_list: list[dict] = []

    for category_section in category_sections:
        category_name = category_section.find_element(
            By.CSS_SELECTOR,
            'h2.Card__Section__Title',
        ).text.splitlines()[-1]

        restaurant_items = category_section.find_elements(
            By.CSS_SELECTOR,
            'li.Slide__Card__Item',
        )

        restaurant_items = (
            restaurant_items[:MAX_RESTAURANTS_PER_CATEGORY]
        )

        for restaurant_item in restaurant_items:
            if len(restaurant_list) >= MAX_TOTAL_RESTAURANTS:
                return restaurant_list

            restaurant_name = restaurant_item.find_element(
                By.CSS_SELECTOR,
                'p.Card__Rest__Name',
            ).text.strip()

            link_element = restaurant_item.find_element(
                By.TAG_NAME,
                'a',
            )
            source_url = link_element.get_attribute('href')

            image_element = link_element.find_element(
                By.TAG_NAME,
                'img',
            )
            image_url = image_element.get_attribute('src')

            restaurant_list.append(
                {
                    'category': category_name,
                    'restaurant_name': restaurant_name,
                    'source_url': source_url,
                    'image_url': image_url,
                }
            )

    return restaurant_list


def remove_duplicate_restaurants(
    restaurant_list: list[dict],
) -> list[dict]:
    """source_url 기준으로 음식점 후보 중복을 제거한다."""
    unique_restaurant_list: list[dict] = []
    seen_urls: list[str] = []

    for restaurant in restaurant_list:
        source_url = restaurant['source_url']

        if source_url not in seen_urls:
            seen_urls.append(source_url)
            unique_restaurant_list.append(restaurant)

    print('중복 제거 전:', len(restaurant_list))
    print('중복 제거 후:', len(unique_restaurant_list))

    return unique_restaurant_list


# ===========================================================
# 5. 상세페이지 수집
# ===========================================================

def get_optional_text(
    parent_element,
    by: str,
    selector: str,
) -> str | None:
    """요소가 있으면 텍스트를 반환하고 없으면 None을 반환한다."""
    try:
        return parent_element.find_element(
            by,
            selector,
        ).text.strip()
    except NoSuchElementException:
        return None


def collect_top_menus(
    restaurant_detail_element,
) -> list[dict]:
    """상세페이지 최초 노출 메뉴 중 상위 3개를 수집한다."""
    menu_items = restaurant_detail_element.find_elements(
        By.CSS_SELECTOR,
        'div.menu-info ul.Restaurant-MenuList li',
    )

    menu_items = menu_items[:TOP_MENU_COUNT]
    menu_list: list[dict] = []

    for menu_item in menu_items:
        menu_name = get_optional_text(
            menu_item,
            By.CSS_SELECTOR,
            'span.restaurant-menu',
        )

        menu_price = get_optional_text(
            menu_item,
            By.CSS_SELECTOR,
            'p.restaurant-price',
        )

        menu_list.append(
            {
                'menu_name': menu_name,
                'menu_price': menu_price,
            }
        )

    return menu_list


def collect_restaurant_detail(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    restaurant: dict,
) -> dict:
    """음식점 1개의 상세정보를 수집한다."""
    driver.get(restaurant['source_url'])

    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'div#subleft-cont')
        )
    )

    detail_element = driver.find_element(
        By.CSS_SELECTOR,
        'div#subleft-cont',
    )

    restaurant_name = detail_element.find_element(
        By.CSS_SELECTOR,
        'h1.tit',
    ).text.strip()

    address = detail_element.find_element(
        By.CSS_SELECTOR,
        'div.basic-info li.locat',
    ).text.strip().splitlines()[0]

    address = address.replace(' 지번', '')

    phone = get_optional_text(
        detail_element,
        By.CSS_SELECTOR,
        'div.basic-info li.tel',
    )

    open_hours = get_optional_text(
        detail_element,
        By.CSS_SELECTOR,
        '#today-main-hours',
    )

    tag = get_optional_text(
        detail_element,
        By.CSS_SELECTOR,
        'div.basic-info li.tag',
    )

    char = get_optional_text(
        detail_element,
        By.CSS_SELECTOR,
        '.basic-info li.char',
    )

    menu_list = collect_top_menus(detail_element)

    return {
        'category': restaurant['category'],
        'restaurant_name': restaurant_name,
        'address': address,
        'phone': phone,
        'open_hours': open_hours,
        'tag': tag,
        'char': char,
        'image_url': restaurant['image_url'],
        'source_url': restaurant['source_url'],
        'menu_list': menu_list,
    }


def collect_restaurant_details(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    unique_restaurant_list: list[dict],
) -> list[dict]:
    """중복 제거된 음식점 전체 상세정보를 수집한다."""
    restaurant_result_list: list[dict] = []

    for index, restaurant in enumerate(unique_restaurant_list):
        print(
            f'{index + 1}/{len(unique_restaurant_list)} '
            f'{restaurant["restaurant_name"]} 수집 중'
        )

        detail = collect_restaurant_detail(
            driver,
            wait,
            restaurant,
        )

        restaurant_result_list.append(detail)

    print(
        '전체 상세정보 수집 건수:',
        len(restaurant_result_list),
    )

    return restaurant_result_list


def save_restaurant_detail_htmls(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    unique_restaurant_list: list[dict],
    batch_dir: Path,
) -> list[Path]:
    """중복 제거된 음식점의 상세 HTML을 모두 저장한다."""
    detail_files: list[Path] = []

    for index, restaurant in enumerate(
        unique_restaurant_list,
        start=1,
    ):
        print(
            f'{index}/{len(unique_restaurant_list)} '
            f'{restaurant["restaurant_name"]} HTML 저장 중'
        )

        driver.get(restaurant['source_url'])

        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'div#subleft-cont')
            )
        )

        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'h1.tit')
            )
        )

        rid = get_restaurant_rid(
            restaurant['source_url']
        )

        detail_file = save_raw_html(
            html=driver.page_source,
            batch_dir=batch_dir,
            file_name=f'restaurant_detail_{rid}.html',
        )

        detail_files.append(detail_file)

    if len(detail_files) != len(unique_restaurant_list):
        raise ValueError(
            '상세 HTML 저장 건수와 음식점 수가 다릅니다.'
        )

    print(
        '상세 HTML 저장 완료:',
        len(detail_files),
    )

    return detail_files


# ===========================================================
# 6. Raw CSV 저장
# ===========================================================

def save_raw_csv(
    restaurant_result_list: list[dict],
) -> Path:
    """수집 직후 데이터를 Raw CSV로 저장하고 경로를 반환한다."""
    raw_df = pd.DataFrame(restaurant_result_list)

    ensure_directory(RAW_DATA_DIR)

    saved_at = datetime.now().strftime('%Y%m%d_%H%M%S')

    raw_file_path = (
        RAW_DATA_DIR
        / f'diningcode_restaurants_raw_{saved_at}.csv'
    )

    raw_df.to_csv(
        raw_file_path,
        index=False,
        encoding='utf-8-sig',
    )

    raw_load_df = pd.read_csv(
        raw_file_path,
        encoding='utf-8-sig',
    )

    if raw_df.shape != raw_load_df.shape:
        raise ValueError(
            'Raw CSV 저장 전후 데이터 크기가 다릅니다.'
        )

    print(f'Raw CSV 저장 완료: {raw_file_path}')
    print('Raw CSV 저장 건수:', len(raw_df))

    return raw_file_path


# ===========================================================
# 7. 대표 실행 함수
# ===========================================================

def run_crawling() -> Path:
    """DiningCode 목록 및 상세페이지 Raw HTML을 수집한다."""
    return run_full_raw_html_crawling()


def run_raw_html_poc() -> Path:
    """
    DiningCode Raw HTML 저장 가능 여부를 검증한다.

    목록 페이지 HTML과 음식점 상세페이지 1건의 HTML만 저장한다.
    기존 전체 크롤링 파이프라인에는 영향을 주지 않는다.
    """
    driver = None

    try:
        driver, wait = create_driver()

        batch_dir = create_html_batch_directory()

        # 1. DiningCode 접속 및 강남역 선택
        open_site(driver, wait)
        select_region(driver, wait)
        scroll_results(driver, wait)

        # 2. 동적 로딩이 완료된 목록 페이지 HTML 저장
        list_html_file = save_raw_html(
            html=driver.page_source,
            batch_dir=batch_dir,
            file_name='restaurant_list.html',
        )

        # 3. 음식점 후보 수집 및 중복 제거
        restaurant_list = collect_restaurant_list(driver)

        unique_restaurant_list = remove_duplicate_restaurants(
            restaurant_list
        )

        if not unique_restaurant_list:
            raise ValueError(
                'Raw HTML POC에 사용할 음식점 후보가 없습니다.'
            )

        # 4. 첫 번째 음식점 1건만 상세페이지 접근
        first_restaurant = unique_restaurant_list[0]

        detail = collect_restaurant_detail(
            driver,
            wait,
            first_restaurant,
        )

        # 5. 상세페이지 렌더링 HTML 저장
        detail_html_file = save_raw_html(
            html=driver.page_source,
            batch_dir=batch_dir,
            file_name='restaurant_detail_001.html',
        )

        print()
        print('=' * 60)
        print('Raw HTML POC 완료')
        print('=' * 60)
        print(f'배치 폴더: {batch_dir}')
        print(f'목록 HTML: {list_html_file}')
        print(f'상세 HTML: {detail_html_file}')
        print(f'POC 음식점: {detail["restaurant_name"]}')
        print(f'후보 수: {len(restaurant_list)}')
        print(f'중복 제거 후 후보 수: {len(unique_restaurant_list)}')

        return batch_dir

    finally:
        if driver is not None:
            driver.quit()
            print('Chrome WebDriver 종료')


def run_full_raw_html_crawling() -> Path:
    """
    DiningCode 목록 및 상세페이지 전체 Raw HTML을 저장한다.

    기존 Raw CSV 파이프라인을 변경하기 전
    전체 HTML 수집 가능 여부를 검증하기 위한 실행 함수이다.
    """
    driver = None

    try:
        driver, wait = create_driver()

        batch_dir = create_html_batch_directory()

        # 1. 사이트 접속 및 지역 선택
        open_site(driver, wait)
        select_region(driver, wait)
        scroll_results(driver, wait)

        # 2. 목록 페이지 Raw HTML 저장
        list_html_file = save_raw_html(
            html=driver.page_source,
            batch_dir=batch_dir,
            file_name='restaurant_list.html',
        )

        # 3. 음식점 후보 확인
        restaurant_list = collect_restaurant_list(driver)

        unique_restaurant_list = remove_duplicate_restaurants(
            restaurant_list
        )

        if not unique_restaurant_list:
            raise ValueError('수집할 음식점 후보가 없습니다.')

        # 4. 상세페이지 Raw HTML 저장
        detail_files = save_restaurant_detail_htmls(
            driver,
            wait,
            unique_restaurant_list,
            batch_dir,
        )

        print()
        print('=' * 60)
        print('전체 Raw HTML 수집 완료')
        print('=' * 60)
        print(f'배치 폴더: {batch_dir}')
        print(f'목록 HTML: {list_html_file}')
        print(f'후보 수: {len(restaurant_list)}')
        print('중복 제거 후 음식점 수:', len(unique_restaurant_list))
        print('상세 HTML 저장 수:', len(detail_files))

        return batch_dir

    finally:
        if driver is not None:
            driver.quit()
            print('Chrome WebDriver 종료')


if __name__ == '__main__':
    run_crawling()
