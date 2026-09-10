import pandas as pd
import pytest
from bs4 import BeautifulSoup

from src.diningcode_pipeline import extract


def test_load_html_returns_content(tmp_path):
    file_path = tmp_path / 'sample.html'
    file_path.write_text('<html><body>test</body></html>', encoding='utf-8')

    result = extract.load_html(file_path)

    assert result == '<html><body>test</body></html>'


def test_load_html_raises_file_not_found_error(tmp_path):
    file_path = tmp_path / 'missing.html'

    with pytest.raises(FileNotFoundError):
        extract.load_html(file_path)


def test_parse_restaurant_list_extracts_restaurant():
    html = """
    <section class="Card__Section">
        <h2 class="Card__Section__Title">1. 이자카야</h2>

        <li class="Slide__Card__Item">
            <a href="/profile.php?rid=test1">
                <img src="https://example.com/image.webp">
                <p class="Card__Rest__Name">테스트식당</p>
            </a>
        </li>
    </section>
    """

    result = extract.parse_restaurant_list(html)

    assert len(result) == 1
    assert result[0]['category'] == '이자카야'
    assert result[0]['restaurant_name'] == '테스트식당'
    assert result[0]['source_url'] == 'https://www.diningcode.com/profile.php?rid=test1'
    assert result[0]['image_url'] == 'https://example.com/image.webp'


def test_remove_duplicate_restaurants_removes_same_source_url():
    restaurants = [
        {'restaurant_name': '식당A', 'source_url': 'url-1'},
        {'restaurant_name': '식당A', 'source_url': 'url-1'},
        {'restaurant_name': '식당B', 'source_url': 'url-2'},
    ]

    result = extract.remove_duplicate_restaurants(restaurants)

    assert len(result) == 2
    assert result[0]['source_url'] == 'url-1'
    assert result[1]['source_url'] == 'url-2'


def test_parse_restaurant_detail_extracts_detail_data():
    html = """
    <html>
        <body>
            <h1 class="tit">테스트식당</h1>

            <div class="basic-info">
                <li class="locat">서울특별시 강남구 테스트로 1</li>
                <li class="tel">02-1234-5678</li>
                <li class="tag">데이트, 술모임</li>
                <li class="char">조용한, 저녁식사</li>
            </div>

            <div id="today-main-hours">영업시간: 11:00 - 22:00</div>

            <div class="menu-info">
                <ul class="Restaurant-MenuList">
                    <li>
                        <span class="restaurant-menu">메뉴1</span>
                        <p class="restaurant-price">10,000원</p>
                    </li>
                    <li>
                        <span class="restaurant-menu">메뉴2</span>
                        <p class="restaurant-price">20,000원</p>
                    </li>
                    <li>
                        <span class="restaurant-menu">메뉴3</span>
                        <p class="restaurant-price">30,000원</p>
                    </li>
                </ul>
            </div>
        </body>
    </html>
    """

    restaurant = {
        'category': '한식',
        'restaurant_name': '테스트식당',
        'image_url': 'https://example.com/image.webp',
        'source_url': 'https://www.diningcode.com/profile.php?rid=test1',
    }

    result = extract.parse_restaurant_detail(html, restaurant)

    assert result['restaurant_name'] == '테스트식당'
    assert result['category'] == '한식'
    assert result['address'] == '서울특별시 강남구 테스트로 1'
    assert result['phone'] == '02-1234-5678'
    assert result['open_hours'] == '영업시간: 11:00 - 22:00'
    assert len(result['menu_list']) == 3
    assert result['menu_list'][0]['menu_name'] == '메뉴1'
    assert result['menu_list'][0]['menu_price'] == '10,000원'


def test_get_detail_source_url_returns_canonical_url():
    html = """
    <html>
        <head>
            <link rel="canonical" href="https://www.diningcode.com/profile.php?rid=test1">
        </head>
    </html>
    """

    result = extract.get_detail_source_url(html)

    assert result == 'https://www.diningcode.com/profile.php?rid=test1'


def test_save_interim_csv_writes_batch_file(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, 'INTERIM_DATA_DIR', tmp_path)

    restaurants = [{
        'category': '한식',
        'restaurant_name': '테스트식당',
        'address': '서울특별시 강남구 테스트로 1',
        'phone': '02-1234-5678',
        'open_hours': '11:00 - 22:00',
        'tag': '데이트',
        'char': '조용한',
        'image_url': 'https://example.com/image.webp',
        'source_url': 'https://www.diningcode.com/profile.php?rid=test1',
        'menu_list': [{'menu_name': '메뉴1', 'menu_price': '10,000원'}],
    }]

    result = extract.save_interim_csv(restaurants, '20260908_174901')

    expected_path = tmp_path / '20260908_174901' / 'diningcode_restaurants_parsed.csv'

    assert result == expected_path
    assert result.is_file()

    loaded_df = pd.read_csv(result, encoding='utf-8-sig')
    assert loaded_df.shape == (1, 10)


def test_run_extract_reads_raw_html_and_saves_interim(tmp_path, monkeypatch):
    raw_batch_dir = tmp_path / 'raw' / '20260908_174901'
    raw_batch_dir.mkdir(parents=True)

    list_html = """
    <section class="Card__Section">
        <h2 class="Card__Section__Title">1. 한식</h2>
        <li class="Slide__Card__Item">
            <a href="/profile.php?rid=test1">
                <img src="https://example.com/image.webp">
                <p class="Card__Rest__Name">테스트식당</p>
            </a>
        </li>
    </section>
    """

    detail_html = """
    <html>
        <head>
            <link rel="canonical" href="https://www.diningcode.com/profile.php?rid=test1">
        </head>
        <body>
            <h1 class="tit">테스트식당</h1>
            <div class="basic-info">
                <li class="locat">서울특별시 강남구 테스트로 1</li>
                <li class="tel">02-1234-5678</li>
            </div>
        </body>
    </html>
    """

    (raw_batch_dir / 'restaurant_list.html').write_text(list_html, encoding='utf-8')
    (raw_batch_dir / 'restaurant_detail_test1.html').write_text(detail_html, encoding='utf-8')

    interim_dir = tmp_path / 'interim'
    monkeypatch.setattr(extract, 'INTERIM_DATA_DIR', interim_dir)

    interim_file, restaurant_list = extract.run_extract(raw_batch_dir)

    assert interim_file == interim_dir / '20260908_174901' / 'diningcode_restaurants_parsed.csv'
    assert interim_file.is_file()
    assert len(restaurant_list) == 1
    assert restaurant_list[0]['restaurant_name'] == '테스트식당'

    interim_df = pd.read_csv(interim_file, encoding='utf-8-sig')
    assert interim_df.shape == (1, 10)


def test_parse_open_hours_extracts_seven_day_schedule():
    html = """
    <div class="hour-main-grid">
        <span class="open-desc">오늘(목)</span>
        <span id="today-main-hours">휴무일</span>

        <div class="hour-dates-column">
            <span class="hour_date">9월 11일(금)</span>
            <span class="hour_date">9월 12일(토)</span>
        </div>

        <div class="hour-times-column">
            <div class="hour_time_item">
                <span class="hour_time">영업시간: 11:30 - 22:00</span>
                <span class="hour_time">라스트오더: 21:00</span>
            </div>
            <div class="hour_time_item">
                <span class="hour_time closed">휴무일</span>
            </div>
        </div>
    </div>
    """

    soup = BeautifulSoup(html, 'html.parser')

    result = extract.parse_open_hours(soup)

    assert result == (
        '오늘(목): 휴무일 | '
        '9월 11일(금): 영업시간: 11:30 - 22:00 / 라스트오더: 21:00 | '
        '9월 12일(토): 휴무일'
    )
