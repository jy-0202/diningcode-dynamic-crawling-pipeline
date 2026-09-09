"""
DiningCode 동적 크롤링 데이터 파이프라인의 공통 설정 모듈입니다.

프로젝트 경로와 Selenium 수집 설정을 한곳에서 관리합니다.
각 단계 모듈은 필요한 설정값만 import하여 사용합니다.
"""

from pathlib import Path

# ===========================================================
# 1. 프로젝트 경로
# ===========================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_DIR / 'data'

RAW_DATA_DIR = DATA_DIR / 'raw'
RAW_HTML_DIR = RAW_DATA_DIR / 'html'
INTERIM_DATA_DIR = DATA_DIR / 'interim'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'

ENV_FILE = PROJECT_DIR / '.env'


# ===========================================================
# 2. 웹 수집 설정
# ===========================================================

BASE_URL = 'https://www.diningcode.com/'

TARGET_CITY = '서울'
TARGET_REGION = '강남역'

MAX_SCROLLS = 2
MAX_RESTAURANTS_PER_CATEGORY = 5
MAX_TOTAL_RESTAURANTS = 100
TOP_MENU_COUNT = 3

WAIT_TIMEOUT = 10
