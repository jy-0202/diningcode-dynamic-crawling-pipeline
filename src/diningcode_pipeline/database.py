"""
MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당하는 모듈입니다.

로컬 환경에서는 .env 파일에서 데이터베이스 접속 정보를 읽습니다.
DB 연결 책임을 load.py에서 분리하여 적재 로직과 연결 설정을 구분합니다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from .config import ENV_FILE


# ===========================================================
# 1. 데이터베이스 환경변수 설정
# ===========================================================

REQUIRED_ENV_NAMES = {
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
}


# ===========================================================
# 2. 데이터베이스 연결 설정
# ===========================================================

def load_database_config(
    env_file: Path = ENV_FILE,
) -> dict[str, str | int]:
    """.env 파일에서 MySQL 연결 정보를 읽고 검증한다."""
    if not env_file.is_file():
        raise FileNotFoundError(
            f'.env 파일이 없습니다. {env_file}'
        )

    load_dotenv(dotenv_path=env_file)

    missing_names = [
        name
        for name in REQUIRED_ENV_NAMES
        if not os.environ.get(name)
    ]

    if missing_names:
        raise ValueError(
            f'필수 환경 변수가 없습니다. '
            f'{sorted(missing_names)}'
        )

    try:
        port = int(os.environ['DB_PORT'])
    except ValueError as error:
        raise ValueError(
            'DB_PORT는 정수여야 합니다.'
        ) from error

    return {
        'host': os.environ['DB_HOST'],
        'port': port,
        'database': os.environ['DB_NAME'],
        'user': os.environ['DB_USER'],
        'password': os.environ['DB_PASSWORD'],
    }


def create_database_if_not_exists(
    config: dict[str, str | int],
) -> None:
    """MySQL 서버에 크롤링 전용 DB가 없으면 생성한다."""
    server_url = URL.create(
        drivername='mysql+pymysql',
        username=str(config['user']),
        password=str(config['password']),
        host=str(config['host']),
        port=int(config['port']),
        query={'charset': 'utf8mb4'},
    )

    server_engine = create_engine(server_url)

    try:
        with server_engine.connect() as connection:
            connection.execute(
                text(
                    f"""
                    CREATE DATABASE IF NOT EXISTS
                    `{config['database']}`
                    CHARACTER SET utf8mb4
                    COLLATE utf8mb4_unicode_ci
                    """
                )
            )
    finally:
        server_engine.dispose()


def create_mysql_engine(
    config: dict[str, str | int],
) -> Engine:
    """크롤링 전용 DB용 SQLAlchemy Engine을 생성한다."""
    database_url = URL.create(
        drivername='mysql+pymysql',
        username=str(config['user']),
        password=str(config['password']),
        host=str(config['host']),
        port=int(config['port']),
        database=str(config['database']),
        query={'charset': 'utf8mb4'},
    )

    return create_engine(database_url)


def test_mysql_connection(
    engine: Engine,
) -> None:
    """MySQL 연결을 확인한다."""
    with engine.connect() as connection:
        result = connection.execute(
            text('SELECT 1')
        )

        print(
            'MySQL 연결 확인:',
            result.scalar(),
        )
