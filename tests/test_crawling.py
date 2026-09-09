
import pandas as pd
import pytest
from selenium.common.exceptions import NoSuchElementException

from src.diningcode_pipeline import crawling


class TextElement:
    def __init__(self, text: str):
        self.text = text


class OptionalTextParent:
    def __init__(self, text: str | None):
        self.text = text

    def find_element(self, by, selector):
        if self.text is None:
            raise NoSuchElementException()
        return TextElement(self.text)


class MenuItem:
    def __init__(self, name: str | None, price: str | None):
        self.name = name
        self.price = price

    def find_element(self, by, selector):
        if selector == 'span.restaurant-menu':
            if self.name is None:
                raise NoSuchElementException()
            return TextElement(self.name)

        if selector == 'p.restaurant-price':
            if self.price is None:
                raise NoSuchElementException()
            return TextElement(self.price)

        raise NoSuchElementException()


class MenuDetail:
    def __init__(self, items: list[MenuItem]):
        self.items = items

    def find_elements(self, by, selector):
        return self.items


def test_ensure_directory_creates_directory(tmp_path):
    directory = tmp_path / 'raw'

    result = crawling.ensure_directory(directory)

    assert result == directory
    assert directory.is_dir()


def test_remove_duplicate_restaurants_keeps_first_item():
    restaurants = [
        {'restaurant_name': 'A', 'source_url': 'url-1'},
        {'restaurant_name': 'A duplicate', 'source_url': 'url-1'},
        {'restaurant_name': 'B', 'source_url': 'url-2'},
    ]

    result = crawling.remove_duplicate_restaurants(restaurants)

    assert result == [restaurants[0], restaurants[2]]


def test_remove_duplicate_restaurants_returns_empty_list_for_empty_input():
    assert crawling.remove_duplicate_restaurants([]) == []


def test_get_optional_text_returns_stripped_text():
    parent = OptionalTextParent('  강남역 맛집  ')

    result = crawling.get_optional_text(parent, 'css selector', '.name')

    assert result == '강남역 맛집'


def test_get_optional_text_returns_none_when_element_is_missing():
    parent = OptionalTextParent(None)

    result = crawling.get_optional_text(parent, 'css selector', '.name')

    assert result is None


def test_collect_top_menus_collects_only_top_three():
    detail = MenuDetail(
        [
            MenuItem('메뉴1', '10,000원'),
            MenuItem('메뉴2', '20,000원'),
            MenuItem('메뉴3', '30,000원'),
            MenuItem('메뉴4', '40,000원'),
        ]
    )

    result = crawling.collect_top_menus(detail)

    assert result == [
        {'menu_name': '메뉴1', 'menu_price': '10,000원'},
        {'menu_name': '메뉴2', 'menu_price': '20,000원'},
        {'menu_name': '메뉴3', 'menu_price': '30,000원'},
    ]


def test_collect_top_menus_allows_missing_price():
    detail = MenuDetail([MenuItem('메뉴1', None)])

    result = crawling.collect_top_menus(detail)

    assert result == [{'menu_name': '메뉴1', 'menu_price': None}]


def test_save_raw_csv_writes_and_reads_same_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(crawling, 'RAW_DATA_DIR', tmp_path)
    restaurants = [
        {
            'category': '한식',
            'restaurant_name': '식당A',
            'address': '서울',
            'phone': None,
            'open_hours': None,
            'tag': None,
            'char': None,
            'image_url': None,
            'source_url': 'url-1',
            'menu_list': [],
        }
    ]

    result = crawling.save_raw_csv(restaurants)

    assert result.parent == tmp_path
    assert result.name.startswith('diningcode_restaurants_raw_')
    saved_df = pd.read_csv(result, encoding='utf-8-sig')
    assert saved_df.shape == (1, 10)


def test_run_crawling_returns_raw_batch_dir(monkeypatch, tmp_path):
    batch_dir = tmp_path / '20260908_174901'

    monkeypatch.setattr(
        crawling,
        'run_full_raw_html_crawling',
        lambda: batch_dir,
    )

    result = crawling.run_crawling()

    assert result == batch_dir


def test_run_crawling_propagates_error(monkeypatch):
    def raise_error():
        raise ValueError('수집 실패')

    monkeypatch.setattr(
        crawling,
        'run_full_raw_html_crawling',
        raise_error,
    )

    with pytest.raises(ValueError, match='수집 실패'):
        crawling.run_crawling()