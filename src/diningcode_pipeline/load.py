"""
DiningCode Processed CSV MySQL 저장 모듈

1. Processed CSV 로드
2. DB 접속 정보 로드
3. DB가 없으면 생성
4. diningcode_restaurant 테이블 생성
5. UPSERT
6. 저장 건수 및 샘플 데이터 검증
"""

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .database import (
    create_database_if_not_exists,
    create_mysql_engine,
    load_database_config,
    test_mysql_connection,
)

TABLE_NAME = "diningcode_restaurant"

DB_COLUMNS = [
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

REQUIRED_DB_COLUMNS = [
    "restaurant_id",
    "restaurant_name",
    "categories",
    "address",
    "source_url",
    "collected_at",
]

CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS diningcode_restaurant (
        restaurant_id VARCHAR(20) PRIMARY KEY,
        restaurant_name VARCHAR(100) NOT NULL,
        categories VARCHAR(100) NOT NULL,
        address VARCHAR(255) NOT NULL,
        phone VARCHAR(30) NULL,
        open_hours TEXT NULL,
        feature TEXT NULL,
        image_url VARCHAR(500) NULL,

        menu_1_name VARCHAR(100) NULL,
        menu_1_price VARCHAR(30) NULL,
        menu_2_name VARCHAR(100) NULL,
        menu_2_price VARCHAR(30) NULL,
        menu_3_name VARCHAR(100) NULL,
        menu_3_price VARCHAR(30) NULL,

        source_url VARCHAR(255) NOT NULL UNIQUE,
        collected_at DATETIME NOT NULL
    )
    ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    """
)

UPSERT_SQL = text(
    """
    INSERT INTO diningcode_restaurant (
        restaurant_id,
        restaurant_name,
        categories,
        address,
        phone,
        open_hours,
        feature,
        image_url,
        menu_1_name,
        menu_1_price,
        menu_2_name,
        menu_2_price,
        menu_3_name,
        menu_3_price,
        source_url,
        collected_at
    )
    VALUES (
        :restaurant_id,
        :restaurant_name,
        :categories,
        :address,
        :phone,
        :open_hours,
        :feature,
        :image_url,
        :menu_1_name,
        :menu_1_price,
        :menu_2_name,
        :menu_2_price,
        :menu_3_name,
        :menu_3_price,
        :source_url,
        :collected_at
    )
    ON DUPLICATE KEY UPDATE
        restaurant_name = VALUES(restaurant_name),
        categories = VALUES(categories),
        address = VALUES(address),
        phone = VALUES(phone),
        open_hours = VALUES(open_hours),
        feature = VALUES(feature),
        image_url = VALUES(image_url),
        menu_1_name = VALUES(menu_1_name),
        menu_1_price = VALUES(menu_1_price),
        menu_2_name = VALUES(menu_2_name),
        menu_2_price = VALUES(menu_2_price),
        menu_3_name = VALUES(menu_3_name),
        menu_3_price = VALUES(menu_3_price),
        source_url = VALUES(source_url),
        collected_at = VALUES(collected_at)
    """
)


def load_processed_csv(
    file_path: Path,
) -> pd.DataFrame:
    """Processed CSV를 DataFrame으로 읽는다."""
    if not file_path.is_file():
        raise FileNotFoundError(
            f'Processed CSV 파일이 없습니다. '
            f'{file_path}'
        )

    return pd.read_csv(
        file_path,
        encoding='utf-8-sig',
        dtype={
            "restaurant_id": "string",
            "restaurant_name": "string",
            "categories": "string",
            "address": "string",
            "phone": "string",
            "open_hours": "string",
            "feature": "string",
            "image_url": "string",
            "menu_1_name": "string",
            "menu_1_price": "string",
            "menu_2_name": "string",
            "menu_2_price": "string",
            "menu_3_name": "string",
            "menu_3_price": "string",
            "source_url": "string",
        },
        parse_dates=['collected_at'],
    )


def prepare_database_dataframe(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """DB 저장용 컬럼과 자료형을 정리하고 검증한다."""
    missing_columns = (
        set(DB_COLUMNS)
        - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f'DB 저장에 필요한 컬럼이 누락되었습니다. '
            f'{sorted(missing_columns)}'
        )

    database_df = df[DB_COLUMNS].copy()

    string_columns = [column for column in DB_COLUMNS if column != 'collected_at']

    for column in string_columns:
        database_df[column] = (
            database_df[column]
            .astype('string')
            .str.strip()
            .replace('', pd.NA)
        )

    database_df['collected_at'] = pd.to_datetime(
        database_df['collected_at'],
        errors='coerce',
    )

    null_counts = (
        database_df[REQUIRED_DB_COLUMNS]
        .isna()
        .sum()
    )
    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(
            'DB 필수 컬럼에 결측값이 있습니다.\n'
            + invalid_nulls.to_string()
        )

    if database_df['restaurant_id'].duplicated().any():
        raise ValueError(
            '중복된 restaurant_id가 존재합니다.'
        )

    if database_df['source_url'].duplicated().any():
        raise ValueError(
            '중복된 source_url이 존재합니다.'
        )

    return database_df


def dataframe_to_database_records(
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """DB 저장용 DataFrame을 Python 기본 자료형 레코드 목록으로 변환한다."""
    records: list[dict[str, Any]] = []

    for row in df.to_dict(orient='records'):
        record: dict[str, Any] = {}

        for column in DB_COLUMNS:
            value = row[column]

            if pd.isna(value):
                record[column] = None

            elif column == 'collected_at':
                record[column] = (
                    pd.Timestamp(value)
                    .to_pydatetime()
                )

            else:
                record[column] = str(value)

        records.append(record)

    return records


def create_table(
    engine: Engine,
) -> None:
    """diningcode_restaurant 테이블이 없으면 생성한다."""
    with engine.begin() as connection:
        connection.execute(CREATE_TABLE_SQL)


def upsert_restaurants(
    engine: Engine,
    records: list[dict[str, Any]],
) -> int:
    """음식점 데이터를 MySQL에 UPSERT한다."""
    if not records:
        return 0

    with engine.begin() as connection:
        result = connection.execute(
            UPSERT_SQL,
            records,
        )

    return int(result.rowcount)


def validate_database(
    engine: Engine,
    restaurant_ids: list[str],
) -> dict[str, int | str]:
    """이번 배치 데이터의 DB 반영 여부와 전체 DB 건수를 확인한다."""
    processed_count = len(restaurant_ids)

    with engine.connect() as connection:
        db_count = connection.execute(
            text('SELECT COUNT(*) FROM diningcode_restaurant')
        ).scalar_one()

        if restaurant_ids:
            params = {f'id_{index}': restaurant_id for index, restaurant_id in enumerate(restaurant_ids)}
            placeholders = ', '.join(f':id_{index}' for index in range(processed_count))

            loaded_count = connection.execute(
                text(
                    'SELECT COUNT(*) '
                    'FROM diningcode_restaurant '
                    f'WHERE restaurant_id IN ({placeholders})'
                ),
                params,
            ).scalar_one()
        else:
            loaded_count = 0

    status = '일치' if processed_count == loaded_count else '불일치'

    sample_df = pd.read_sql(
        text(
            """
            SELECT
                restaurant_id,
                restaurant_name,
                categories,
                address,
                phone,
                menu_1_name,
                menu_1_price
            FROM diningcode_restaurant
            LIMIT 5
            """
        ),
        engine,
    )

    print('DB 샘플 데이터')
    print(sample_df)

    return {
        'processed_count': processed_count,
        'loaded_count': loaded_count,
        'db_count': db_count,
        'count_status': status,
    }


def run_load(
    processed_csv_file: Path,
) -> dict[str, int | str]:
    """
    Processed CSV를 MySQL에 UPSERT하고 저장 결과를 검증한다.

    Returns:
        이번 배치 건수, DB 반영 건수, 전체 DB 건수, 건수 비교 결과
    """
    processed_df = load_processed_csv(processed_csv_file)

    database_df = prepare_database_dataframe(processed_df)

    records = dataframe_to_database_records(database_df)

    config = load_database_config()

    create_database_if_not_exists(config)

    engine = create_mysql_engine(config)

    try:
        test_mysql_connection(engine)

        create_table(engine)

        upsert_restaurants(engine, records)

        restaurant_ids = database_df['restaurant_id'].astype(str).tolist()
        summary = validate_database(engine, restaurant_ids)

        print(f'MySQL 저장 결과: {summary}')

        return summary

    finally:
        engine.dispose()
        print('SQLAlchemy Engine 종료')


if __name__ == '__main__':
    print(
        'load.py는 main.py에서 '
        'run_load()로 실행합니다.'
    )
