"""
DiningCode Raw HTML 데이터 추출 모듈

Selenium으로 저장한 Raw HTML을 읽어
음식점 후보 목록과 상세정보를 추출한다.
"""

import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from .config import (
    BASE_URL,
    INTERIM_DATA_DIR,
    MAX_RESTAURANTS_PER_CATEGORY,
    MAX_TOTAL_RESTAURANTS,
    TOP_MENU_COUNT,
)

INTERIM_COLUMNS = [
    'category',
    'restaurant_name',
    'address',
    'phone',
    'open_hours',
    'tag',
    'char',
    'image_url',
    'source_url',
    'menu_list',
]


def load_html(file_path: Path) -> str:
    """HTML 파일을 UTF-8 문자열로 읽는다."""
    if not file_path.is_file():
        raise FileNotFoundError(f'HTML 파일이 없습니다. {file_path}')

    return file_path.read_text(encoding='utf-8')


def get_optional_text(parent, selector: str) -> str | None:
    """선택한 요소가 있으면 텍스트를 반환하고 없으면 None을 반환한다."""
    element = parent.select_one(selector)

    if element is None:
        return None

    return element.get_text(' ', strip=True)


def parse_restaurant_list(html: str) -> list[dict]:
    """목록 HTML에서 카테고리별 음식점 후보를 추출한다."""
    soup = BeautifulSoup(html, 'html.parser')
    restaurant_list: list[dict] = []
    category_sections = soup.select('section.Card__Section')

    for category_section in category_sections:
        category_element = category_section.select_one('h2.Card__Section__Title')

        if category_element is None:
            continue

        category_name = category_element.get_text(' ', strip=True)
        category_name = re.sub(r'^\d+\.\s*', '', category_name)

        restaurant_items = category_section.select('li.Slide__Card__Item')
        restaurant_items = restaurant_items[:MAX_RESTAURANTS_PER_CATEGORY]

        for restaurant_item in restaurant_items:
            if len(restaurant_list) >= MAX_TOTAL_RESTAURANTS:
                return restaurant_list

            restaurant_name_element = restaurant_item.select_one('p.Card__Rest__Name')
            link_element = restaurant_item.select_one('a[href*="/profile.php?rid="]')

            if restaurant_name_element is None or link_element is None:
                continue

            image_element = link_element.select_one('img')
            source_url = urljoin(BASE_URL, link_element.get('href', ''))
            image_url = image_element.get('src') if image_element is not None else None

            restaurant_list.append(
                {
                    'category': category_name,
                    'restaurant_name': restaurant_name_element.get_text(' ', strip=True),
                    'source_url': source_url,
                    'image_url': image_url,
                }
            )

    return restaurant_list


def remove_duplicate_restaurants(restaurant_list: list[dict]) -> list[dict]:
    """source_url 기준으로 음식점 후보 중복을 제거한다."""
    unique_restaurant_list: list[dict] = []
    seen_urls: list[str] = []

    for restaurant in restaurant_list:
        source_url = restaurant['source_url']

        if source_url not in seen_urls:
            seen_urls.append(source_url)
            unique_restaurant_list.append(restaurant)

    return unique_restaurant_list


def parse_address(soup: BeautifulSoup) -> str | None:
    """상세 HTML에서 도로명 주소를 추출한다."""
    address_element = soup.select_one('div.basic-info li.locat')

    if address_element is None:
        return None

    address_parts: list[str] = []

    for child in address_element.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
        elif isinstance(child, Tag):
            if child.name in {'button', 'div'}:
                break
            text = child.get_text(' ', strip=True)
        else:
            text = ''

        if text:
            address_parts.append(text)

    if not address_parts:
        return None

    return ' '.join(address_parts)


def parse_open_hours(soup: BeautifulSoup) -> str | None:
    """상세 HTML에서 오늘부터 7일간의 영업시간을 추출한다."""
    today_label = get_optional_text(soup, '.hour-main-grid .open-desc')
    today_hours = get_optional_text(soup, '#today-main-hours')

    if today_hours is None:
        return None

    open_hours = [f'{today_label}: {today_hours}' if today_label else today_hours]
    date_elements = soup.select('.hour-dates-column .hour_date')
    time_elements = soup.select('.hour-times-column .hour_time_item')

    for date_element, time_element in zip(date_elements, time_elements, strict=False):
        date_text = date_element.get_text(' ', strip=True)
        time_text = time_element.get_text(' / ', strip=True)

        if date_text and time_text:
            open_hours.append(f'{date_text}: {time_text}')

    return ' | '.join(open_hours)


def parse_top_menus(soup: BeautifulSoup) -> list[dict]:
    """상세 HTML의 상위 3개 메뉴를 추출한다."""
    menu_items = soup.select('div.menu-info ul.Restaurant-MenuList li')[:TOP_MENU_COUNT]
    menu_list: list[dict] = []

    for menu_item in menu_items:
        menu_name = get_optional_text(menu_item, 'span.restaurant-menu')
        price_element = menu_item.select_one('p.restaurant-price')
        menu_price = price_element.get_text('', strip=True) if price_element is not None else None

        menu_list.append(
            {
                'menu_name': menu_name,
                'menu_price': menu_price,
            }
        )

    return menu_list


def parse_restaurant_detail(html: str, restaurant: dict) -> dict:
    """상세 HTML에서 음식점 정보를 추출한다."""
    soup = BeautifulSoup(html, 'html.parser')

    return {
        'category': restaurant['category'],
        'restaurant_name': get_optional_text(soup, 'h1.tit'),
        'address': parse_address(soup),
        'phone': get_optional_text(soup, 'div.basic-info li.tel'),
        'open_hours': parse_open_hours(soup),
        'tag': get_optional_text(soup, 'div.basic-info li.tag'),
        'char': get_optional_text(soup, '.basic-info li.char'),
        'image_url': restaurant['image_url'],
        'source_url': restaurant['source_url'],
        'menu_list': parse_top_menus(soup),
    }


def get_detail_source_url(html: str) -> str:
    """상세 HTML의 canonical 태그에서 음식점 URL을 추출한다."""
    soup = BeautifulSoup(html, 'html.parser')
    canonical = soup.select_one('link[rel="canonical"]')

    if canonical is None:
        raise ValueError('상세 HTML에서 canonical URL을 찾지 못했습니다.')

    source_url = canonical.get('href')

    if not source_url:
        raise ValueError('상세 HTML의 canonical URL이 비어 있습니다.')

    return str(source_url)


def save_interim_csv(restaurant_result_list: list[dict], batch_id: str) -> Path:
    """Extract 결과를 batch_id별 Interim CSV로 저장한다."""
    interim_df = pd.DataFrame(restaurant_result_list, columns=INTERIM_COLUMNS)

    batch_dir = INTERIM_DATA_DIR / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    interim_file_path = batch_dir / 'diningcode_restaurants_parsed.csv'
    interim_df.to_csv(interim_file_path, index=False, encoding='utf-8-sig')

    loaded_df = pd.read_csv(interim_file_path, encoding='utf-8-sig')

    if interim_df.shape != loaded_df.shape:
        raise ValueError('Interim CSV 저장 전후 데이터 크기가 다릅니다.')

    print(f'Interim CSV 저장 완료: {interim_file_path}')
    print(f'Interim CSV 저장 건수: {len(interim_df)}')

    return interim_file_path


def run_extract(raw_batch_dir: Path) -> tuple[Path, list[dict]]:
    """
    Raw HTML 배치를 읽어 음식점 정보를 추출하고 Interim CSV로 저장한다.

    Returns:
        1. 저장된 Interim CSV 파일 경로
        2. 중복 제거 전 음식점 후보 목록
           (Preprocess categories 통합용)
    """
    list_html_file = raw_batch_dir / 'restaurant_list.html'

    restaurant_list = parse_restaurant_list(load_html(list_html_file))
    unique_restaurant_list = remove_duplicate_restaurants(restaurant_list)

    restaurant_lookup = {
        restaurant['source_url']: restaurant
        for restaurant in unique_restaurant_list
    }

    detail_files = sorted(raw_batch_dir.glob('restaurant_detail_*.html'))

    if not detail_files:
        raise ValueError('파싱할 상세 HTML 파일이 없습니다.')

    restaurant_result_list: list[dict] = []

    for detail_file in detail_files:
        html = load_html(detail_file)
        source_url = get_detail_source_url(html)
        restaurant = restaurant_lookup.get(source_url)

        if restaurant is None:
            raise ValueError(f'목록 HTML에서 상세 음식점을 찾지 못했습니다. {source_url}')

        detail = parse_restaurant_detail(html, restaurant)
        restaurant_result_list.append(detail)

    print('상세 HTML 파싱 건수:', len(restaurant_result_list))

    return (
        save_interim_csv(restaurant_result_list, raw_batch_dir.name),
        restaurant_list,
    )