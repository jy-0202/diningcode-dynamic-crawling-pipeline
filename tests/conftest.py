from datetime import datetime

import pandas as pd
import pytest

from src.diningcode_pipeline.load import DB_COLUMNS


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'category': '한식',
                'restaurant_name': '식당A',
                'address': '서울 강남구 A로 1',
                'phone': '02-111-1111',
                'open_hours': '10:00-22:00',
                'tag': '데이트',
                'char': '조용한',
                'image_url': 'https://example.com/a.jpg',
                'source_url': 'https://www.diningcode.com/profile.php?rid=1001',
                'menu_list': "[{'menu_name': '메뉴A', 'menu_price': '10,000원'}]",
            },
            {
                'category': '일식',
                'restaurant_name': '식당B',
                'address': '서울 강남구 B로 2',
                'phone': None,
                'open_hours': None,
                'tag': None,
                'char': '깔끔한',
                'image_url': None,
                'source_url': 'https://www.diningcode.com/profile.php?rid=1002',
                'menu_list': (
                    "[{'menu_name': '메뉴B1', 'menu_price': '12,000원'}, "
                    "{'menu_name': '메뉴B2', 'menu_price': '15,000원'}]"
                ),
            },
        ]
    )


@pytest.fixture
def sample_restaurant_list() -> list[dict]:
    return [
        {
            'category': '한식',
            'restaurant_name': '식당A',
            'source_url': 'https://www.diningcode.com/profile.php?rid=1001',
            'image_url': 'https://example.com/a.jpg',
        },
        {
            'category': '데이트',
            'restaurant_name': '식당A',
            'source_url': 'https://www.diningcode.com/profile.php?rid=1001',
            'image_url': 'https://example.com/a.jpg',
        },
        {
            'category': '일식',
            'restaurant_name': '식당B',
            'source_url': 'https://www.diningcode.com/profile.php?rid=1002',
            'image_url': None,
        },
    ]


@pytest.fixture
def valid_processed_df() -> pd.DataFrame:
    row = {
        'restaurant_id': '1001',
        'restaurant_name': '식당A',
        'categories': '한식, 데이트',
        'address': '서울 강남구 A로 1',
        'phone': '02-111-1111',
        'open_hours': '10:00-22:00',
        'feature': '데이트, 조용한',
        'image_url': 'https://example.com/a.jpg',
        'menu_1_name': '메뉴A',
        'menu_1_price': '10,000원',
        'menu_2_name': None,
        'menu_2_price': None,
        'menu_3_name': None,
        'menu_3_price': None,
        'source_url': 'https://www.diningcode.com/profile.php?rid=1001',
        'collected_at': datetime(2026, 9, 1, 12, 0, 0),
    }
    return pd.DataFrame([row], columns=DB_COLUMNS)
