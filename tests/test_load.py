from datetime import datetime

import pandas as pd
import pytest

from src.diningcode_pipeline import load


def test_load_processed_csv_raises_file_not_found_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load.load_processed_csv(tmp_path / 'missing.csv')


def test_load_processed_csv_loads_string_columns_and_datetime(tmp_path, valid_processed_df):
    file_path = tmp_path / 'processed.csv'
    valid_processed_df.to_csv(file_path, index=False, encoding='utf-8-sig')

    result = load.load_processed_csv(file_path)

    assert str(result['restaurant_id'].dtype) == 'string'
    assert pd.api.types.is_datetime64_any_dtype(result['collected_at'])
    assert result.loc[0, 'restaurant_id'] == '1001'


def test_prepare_database_dataframe_raises_for_missing_column(valid_processed_df):
    invalid_df = valid_processed_df.drop(columns=['restaurant_name'])

    with pytest.raises(ValueError, match='DB 저장에 필요한 컬럼'):
        load.prepare_database_dataframe(invalid_df)


def test_prepare_database_dataframe_strips_strings_and_converts_blank_to_na(valid_processed_df):
    source_df = valid_processed_df.copy()
    source_df.loc[0, 'restaurant_name'] = '  식당A  '
    source_df.loc[0, 'phone'] = '   '

    result = load.prepare_database_dataframe(source_df)

    assert result.loc[0, 'restaurant_name'] == '식당A'
    assert pd.isna(result.loc[0, 'phone'])


def test_prepare_database_dataframe_raises_for_required_blank(valid_processed_df):
    invalid_df = valid_processed_df.copy()
    invalid_df.loc[0, 'address'] = '   '

    with pytest.raises(ValueError, match='DB 필수 컬럼에 결측값'):
        load.prepare_database_dataframe(invalid_df)


def test_prepare_database_dataframe_raises_for_invalid_collected_at(valid_processed_df):
    invalid_df = valid_processed_df.copy()
    invalid_df['collected_at'] = invalid_df['collected_at'].astype('object')
    invalid_df.loc[0, 'collected_at'] = 'invalid-date'

    with pytest.raises(ValueError, match='DB 필수 컬럼에 결측값'):
        load.prepare_database_dataframe(invalid_df)


def test_prepare_database_dataframe_raises_for_duplicate_restaurant_id(valid_processed_df):
    duplicate = valid_processed_df.copy()
    duplicate.loc[0, 'source_url'] = 'url-2'
    invalid_df = pd.concat([valid_processed_df, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match='restaurant_id'):
        load.prepare_database_dataframe(invalid_df)


def test_prepare_database_dataframe_raises_for_duplicate_source_url(valid_processed_df):
    duplicate = valid_processed_df.copy()
    duplicate.loc[0, 'restaurant_id'] = '2002'
    invalid_df = pd.concat([valid_processed_df, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match='source_url'):
        load.prepare_database_dataframe(invalid_df)


def test_dataframe_to_database_records_converts_values(valid_processed_df):
    prepared_df = load.prepare_database_dataframe(valid_processed_df)

    result = load.dataframe_to_database_records(prepared_df)

    assert len(result) == 1
    assert result[0]['restaurant_id'] == '1001'
    assert result[0]['menu_2_name'] is None
    assert isinstance(result[0]['collected_at'], datetime)


def test_upsert_restaurants_returns_zero_for_empty_records():
    assert load.upsert_restaurants(object(), []) == 0


def test_upsert_restaurants_executes_records_and_returns_rowcount():
    received = {}

    class FakeResult:
        rowcount = 2

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement, records):
            received['statement'] = statement
            received['records'] = records
            return FakeResult()

    class FakeEngine:
        def begin(self):
            return FakeConnection()

    records = [{'restaurant_id': '1001'}]

    result = load.upsert_restaurants(FakeEngine(), records)

    assert result == 2
    assert received['records'] == records
    assert 'ON DUPLICATE KEY UPDATE' in str(received['statement'])


def test_create_table_executes_create_table_sql():
    executed = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement):
            executed.append(str(statement))

    class FakeEngine:
        def begin(self):
            return FakeConnection()

    load.create_table(FakeEngine())

    assert len(executed) == 1
    assert 'CREATE TABLE IF NOT EXISTS diningcode_restaurant' in executed[0]


@pytest.mark.parametrize(
    ('restaurant_ids', 'db_count', 'loaded_count', 'expected_status'),
    [
        (['id1', 'id2', 'id3'], 3, 3, '일치'),
        (['id1', 'id2', 'id3'], 4, 3, '일치'),
        (['id1', 'id2', 'id3'], 4, 2, '불일치'),
    ],
)
def test_validate_database_returns_count_status(
    monkeypatch, restaurant_ids, db_count, loaded_count, expected_status
):
    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, statement, params=None):
            sql = str(statement)

            if 'WHERE restaurant_id IN' in sql:
                return FakeResult(loaded_count)

            return FakeResult(db_count)

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr(
        load.pd,
        'read_sql',
        lambda *args, **kwargs: load.pd.DataFrame(),
    )

    result = load.validate_database(FakeEngine(), restaurant_ids)

    assert result == {
        'processed_count': 3,
        'loaded_count': loaded_count,
        'db_count': db_count,
        'count_status': expected_status,
    }


def test_run_load_runs_pipeline_and_disposes_engine(monkeypatch, tmp_path):
    processed_path = tmp_path / 'processed.csv'
    processed_df = pd.DataFrame([{'raw': 1}])
    database_df = pd.DataFrame([{'restaurant_id': '1001'}])
    records = [{'restaurant_id': '1001'}]
    config = {'database': 'diningcode'}
    calls = []

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def dispose(self):
            self.disposed = True

    engine = FakeEngine()

    monkeypatch.setattr(load, 'load_processed_csv', lambda path: processed_df)
    monkeypatch.setattr(load, 'prepare_database_dataframe', lambda df: database_df)
    monkeypatch.setattr(load, 'dataframe_to_database_records', lambda df: records)
    monkeypatch.setattr(load, 'load_database_config', lambda: config)
    monkeypatch.setattr(
        load,
        'create_database_if_not_exists',
        lambda cfg: calls.append(('create_database', cfg)),
    )
    monkeypatch.setattr(load, 'create_mysql_engine', lambda cfg: engine)
    monkeypatch.setattr(load, 'test_mysql_connection', lambda eng: calls.append(('test', eng)))
    monkeypatch.setattr(load, 'create_table', lambda eng: calls.append(('table', eng)))
    monkeypatch.setattr(
        load,
        'upsert_restaurants',
        lambda eng, rows: calls.append(('upsert', eng, rows)) or 1,
    )
    monkeypatch.setattr(
        load,
        'validate_database',
        lambda eng, processed_count: {
            'processed_count': processed_count,
            'db_count': 1,
            'count_status': '일치',
        },
    )

    result = load.run_load(processed_path)

    assert result['count_status'] == '일치'
    assert ('create_database', config) in calls
    assert ('upsert', engine, records) in calls
    assert engine.disposed is True


def test_run_load_disposes_engine_when_database_validation_fails(monkeypatch, tmp_path):
    processed_path = tmp_path / 'processed.csv'
    processed_df = pd.DataFrame([{'raw': 1}])
    database_df = pd.DataFrame([{'restaurant_id': '1001'}])
    records = [{'restaurant_id': '1001'}]

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def dispose(self):
            self.disposed = True

    engine = FakeEngine()

    monkeypatch.setattr(load, 'load_processed_csv', lambda path: processed_df)
    monkeypatch.setattr(load, 'prepare_database_dataframe', lambda df: database_df)
    monkeypatch.setattr(load, 'dataframe_to_database_records', lambda df: records)
    monkeypatch.setattr(load, 'load_database_config', lambda: {'database': 'diningcode'})
    monkeypatch.setattr(load, 'create_database_if_not_exists', lambda config: None)
    monkeypatch.setattr(load, 'create_mysql_engine', lambda config: engine)
    monkeypatch.setattr(load, 'test_mysql_connection', lambda eng: None)
    monkeypatch.setattr(load, 'create_table', lambda eng: None)
    monkeypatch.setattr(load, 'upsert_restaurants', lambda eng, rows: 1)

    def raise_validation_error(engine, processed_count):
        raise ValueError('DB 검증 실패')

    monkeypatch.setattr(load, 'validate_database', raise_validation_error)

    with pytest.raises(ValueError, match='DB 검증 실패'):
        load.run_load(processed_path)

    assert engine.disposed is True
