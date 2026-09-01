"""
DiningCode Raw CSV 전처리 모듈

Raw CSV를 읽어 다음 작업을 수행한다.

1. tag + char → feature 통합
2. 상위 3개 메뉴 컬럼 분리
3. 음식점별 categories 통합
4. 임시 컬럼 제거
5. restaurant_id / collected_at 생성
6. 결측값 정리
7. 데이터 검증
8. Processed CSV 저장
"""

from datetime import datetime
from pathlib import Path
import ast

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = PROJECT_DIR / "data" / "processed"

FINAL_COLUMNS = [
    "restaurant_id",
    "restaurant_name",
    "categories",
    "address",
    "phone",
    "open_hours",
    "feature",
    "image_url",
    "menu_1_name",
    "menu_1_price",
    "menu_2_name",
    "menu_2_price",
    "menu_3_name",
    "menu_3_price",
    "source_url",
    "collected_at",
]


def ensure_directory(directory: Path) -> Path:
    """지정한 폴더가 없으면 생성하고 경로를 반환한다."""
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_raw_csv(file_path: Path) -> pd.DataFrame:
    """Raw CSV를 DataFrame으로 읽는다."""
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Raw CSV 파일이 없습니다. {file_path}"
        )

    return pd.read_csv(file_path, encoding='utf-8-sig')


def parse_menu_list(value: object) -> list[dict]:
    """CSV 문자열로 저장된 menu_list를 Python list로 복원한다."""
    if pd.isna(value):
        return []

    if isinstance(value, list):
        return value

    return ast.literal_eval(str(value))


def build_restaurant_categories(
    restaurant_list: list[dict],
) -> dict[str, str]:
    """중복 제거 전 후보 목록으로 음식점별 복수 categories를 통합한다."""
    restaurant_categories = {}

    for restaurant in restaurant_list:
        source_url = restaurant['source_url']
        category = restaurant['category']

        if source_url not in restaurant_categories:
            restaurant_categories[source_url] = []

        if category not in restaurant_categories[source_url]:
            restaurant_categories[source_url].append(category)

    for source_url in restaurant_categories:
        restaurant_categories[source_url] = ', '.join(restaurant_categories[source_url])

    return restaurant_categories


def preprocess_restaurants(
    raw_df: pd.DataFrame,
    restaurant_list: list[dict],
) -> pd.DataFrame:
    """Raw DataFrame을 최종 DB 적재 구조로 전처리한다."""
    restaurant_df = raw_df.copy()

    restaurant_df['menu_list'] = restaurant_df['menu_list'].map(parse_menu_list)

    feature_list: list[str | None] = []

    for index in restaurant_df.index:
        tag = restaurant_df.loc[index, "tag"]
        char = restaurant_df.loc[index, "char"]

        tag = None if pd.isna(tag) else str(tag).strip()
        char = None if pd.isna(char) else str(char).strip()

        if tag and char:
            feature = tag + ", " + char
        elif tag:
            feature = tag
        elif char:
            feature = char
        else:
            feature = None

        feature_list.append(feature)

    restaurant_df["feature"] = feature_list

    for menu_number in range(1, 4):
        restaurant_df[f"menu_{menu_number}_name"] = None
        restaurant_df[f"menu_{menu_number}_price"] = None

    for index in restaurant_df.index:
        menu_list = restaurant_df.loc[index, 'menu_list']

        if len(menu_list) >= 1:
            restaurant_df.loc[index, 'menu_1_name'] = menu_list[0]['menu_name']
            restaurant_df.loc[index, 'menu_1_price'] = menu_list[0]['menu_price']

        if len(menu_list) >= 2:
            restaurant_df.loc[index, 'menu_2_name'] = menu_list[1]['menu_name']
            restaurant_df.loc[index, 'menu_2_price'] = menu_list[1]['menu_price']

        if len(menu_list) >= 3:
            restaurant_df.loc[index, 'menu_3_name'] = menu_list[2]['menu_name']
            restaurant_df.loc[index, 'menu_3_price'] = menu_list[2]['menu_price']

    restaurant_categories = build_restaurant_categories(restaurant_list)

    restaurant_df['categories'] = restaurant_df['source_url'].map(restaurant_categories)

    restaurant_df = restaurant_df.drop(columns=['category', 'tag', 'char', 'menu_list'])

    restaurant_df["restaurant_id"] = (
        restaurant_df["source_url"]
        .str.split("rid=")
        .str[-1]
    )

    restaurant_df['collected_at'] = datetime.now()

    restaurant_df = restaurant_df.replace('', pd.NA)

    return restaurant_df[FINAL_COLUMNS]


def validate_restaurant_df(
    restaurant_df: pd.DataFrame,
) -> dict[str, int]:
    """전처리 결과의 필수 컬럼, 중복, 결측값을 검증한다."""
    if restaurant_df.empty:
        raise ValueError(
            "전처리 결과 DataFrame이 비어 있습니다."
        )

    missing_columns = (
        set(FINAL_COLUMNS)
        - set(restaurant_df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"필수 컬럼이 누락되었습니다. "
            f"{sorted(missing_columns)}"
        )

    required_columns = [
        "restaurant_id",
        "restaurant_name",
        "categories",
        "address",
        "source_url",
        "collected_at",
    ]

    null_counts = (
        restaurant_df[required_columns]
        .isna()
        .sum()
    )
    invalid_nulls = null_counts[
        null_counts > 0
    ]

    if not invalid_nulls.empty:
        raise ValueError(
            "필수 데이터에 결측값이 있습니다.\n"
            + invalid_nulls.to_string()
        )

    restaurant_id_duplicates = int(
        restaurant_df["restaurant_id"]
        .duplicated()
        .sum()
    )
    source_url_duplicates = int(
        restaurant_df["source_url"]
        .duplicated()
        .sum()
    )

    if restaurant_id_duplicates:
        raise ValueError(
            "중복된 restaurant_id가 존재합니다."
        )

    if source_url_duplicates:
        raise ValueError(
            "중복된 source_url이 존재합니다."
        )

    return {
        "row_count": len(restaurant_df),
        "column_count": len(restaurant_df.columns),
        "restaurant_id_duplicates": restaurant_id_duplicates,
        "source_url_duplicates": source_url_duplicates,
    }


def save_processed_csv(
    restaurant_df: pd.DataFrame,
) -> Path:
    """전처리 결과를 Processed CSV로 저장하고 경로를 반환한다."""
    ensure_directory(PROCESSED_DATA_DIR)

    saved_at = datetime.now().strftime('%Y%m%d_%H%M%S')

    processed_file_path = (
        PROCESSED_DATA_DIR
        / (
            "diningcode_restaurants_processed_"
            f"{saved_at}.csv"
        )
    )

    restaurant_df.to_csv(
        processed_file_path,
        index=False,
        encoding="utf-8-sig",
    )

    processed_load_df = pd.read_csv(processed_file_path, encoding='utf-8-sig')

    if restaurant_df.shape != processed_load_df.shape:
        raise ValueError(
            "Processed CSV 저장 전후 데이터 크기가 다릅니다."
        )

    print(f'Processed CSV 저장 완료: {processed_file_path}')

    return processed_file_path


def run_preprocess(
    raw_csv_file: Path,
    restaurant_list: list[dict],
) -> Path:
    """
    Raw CSV를 읽어 전처리, 검증, Processed CSV 저장을 수행한다.

    Returns:
        저장된 Processed CSV 파일 경로
    """
    raw_df = load_raw_csv(raw_csv_file)

    restaurant_df = preprocess_restaurants(
        raw_df,
        restaurant_list,
    )

    summary = validate_restaurant_df(restaurant_df)

    print('전처리 검증 결과:', summary)

    return save_processed_csv(restaurant_df)


if __name__ == "__main__":
    print('preprocess.py는 main.py에서 run_preprocess()로 실행합니다.')
