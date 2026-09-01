import pytest

from src.diningcode_pipeline import database

ENV_NAMES = [
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
]


def set_db_environment(monkeypatch, **overrides):
    values = {
        'DB_HOST': 'localhost',
        'DB_PORT': '3306',
        'DB_NAME': 'diningcode',
        'DB_USER': 'root',
        'DB_PASSWORD': 'password',
    }
    values.update(overrides)

    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    for name, value in values.items():
        if value is not None:
            monkeypatch.setenv(name, value)


def test_load_database_config_raises_when_env_file_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        database.load_database_config(tmp_path / '.env')


def test_load_database_config_returns_valid_config(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('', encoding='utf-8')
    set_db_environment(monkeypatch)

    result = database.load_database_config(env_file)

    assert result == {
        'host': 'localhost',
        'port': 3306,
        'database': 'diningcode',
        'user': 'root',
        'password': 'password',
    }


def test_load_database_config_raises_when_required_value_is_missing(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('', encoding='utf-8')
    set_db_environment(monkeypatch, DB_PASSWORD=None)

    with pytest.raises(ValueError, match='DB_PASSWORD'):
        database.load_database_config(env_file)


def test_load_database_config_raises_when_port_is_not_integer(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('', encoding='utf-8')
    set_db_environment(monkeypatch, DB_PORT='not-number')

    with pytest.raises(ValueError, match='DB_PORT는 정수'):
        database.load_database_config(env_file)


def test_create_mysql_engine_builds_expected_url(monkeypatch):
    captured = {}
    fake_engine = object()

    def fake_create_engine(url):
        captured['url'] = url
        return fake_engine

    monkeypatch.setattr(database, 'create_engine', fake_create_engine)
    config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'diningcode',
        'user': 'root',
        'password': 'password',
    }

    result = database.create_mysql_engine(config)

    assert result is fake_engine
    url = captured['url']
    assert url.drivername == 'mysql+pymysql'
    assert url.host == 'localhost'
    assert url.port == 3306
    assert url.database == 'diningcode'
    assert url.username == 'root'
    assert url.query['charset'] == 'utf8mb4'


def test_create_database_if_not_exists_executes_sql_and_disposes(monkeypatch):
    executed = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement):
            executed.append(str(statement))

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def connect(self):
            return FakeConnection()

        def dispose(self):
            self.disposed = True

    engine = FakeEngine()
    monkeypatch.setattr(database, 'create_engine', lambda url: engine)
    config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'diningcode',
        'user': 'root',
        'password': 'password',
    }

    database.create_database_if_not_exists(config)

    assert any('CREATE DATABASE IF NOT EXISTS' in sql for sql in executed)
    assert any('`diningcode`' in sql for sql in executed)
    assert engine.disposed is True


def test_test_mysql_connection_executes_select_one(capsys):
    class FakeResult:
        def scalar(self):
            return 1

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement):
            assert str(statement) == 'SELECT 1'
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    database.test_mysql_connection(FakeEngine())

    captured = capsys.readouterr()
    assert 'MySQL 연결 확인: 1' in captured.out
