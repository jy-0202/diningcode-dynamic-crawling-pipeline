import pandas as pd
import pytest

from src.diningcode_pipeline import preprocess


def test_load_interim_csv_raises_file_not_found_error(tmp_path):
    file_path = tmp_path / 'missing.csv'

    with pytest.raises(FileNotFoundError):
        preprocess.load_interim_csv(file_path)


def test_load_interim_csv_returns_dataframe(tmp_path):
    file_path = tmp_path / 'interim.csv'

    pd.DataFrame([{'name': '식당A'}]).to_csv(
        file_path,
        index=False,
        encoding='utf-8-sig',
    )

    result = preprocess.load_interim_csv(file_path)

    assert len(result) == 1
    assert result.iloc[0]['name'] == '식당A'


def test_parse_menu_list_returns_existing_list():
    value = [{'menu_name': '메뉴A', 'menu_price': '10,000원'}]

    result = preprocess.parse_menu_list(value)

    assert result is value


def test_parse_menu_list_parses_string_value():
    value = "[{'menu_name': '메뉴A', 'menu_price': '10,000원'}]"

    result = preprocess.parse_menu_list(value)

    assert result == [{'menu_name': '메뉴A', 'menu_price': '10,000원'}]


def test_parse_menu_list_returns_empty_list_for_missing_value():
    assert preprocess.parse_menu_list(pd.NA) == []


def test_parse_menu_list_raises_for_invalid_literal():
    with pytest.raises((ValueError, SyntaxError)):
        preprocess.parse_menu_list('[invalid')


def test_build_restaurant_categories_merges_and_deduplicates_categories():
    restaurants = [
        {'source_url': 'url-1', 'category': '한식'},
        {'source_url': 'url-1', 'category': '데이트'},
        {'source_url': 'url-1', 'category': '한식'},
        {'source_url': 'url-2', 'category': '일식'},
    ]

    result = preprocess.build_restaurant_categories(restaurants)

    assert result == {
        'url-1': '한식, 데이트',
        'url-2': '일식',
    }


def test_build_restaurant_categories_returns_empty_dict_for_empty_input():
    assert preprocess.build_restaurant_categories([]) == {}


def test_preprocess_restaurants_builds_final_columns_and_values(
    sample_raw_df,
    sample_restaurant_list,
):
    result = preprocess.preprocess_restaurants(
        sample_raw_df,
        sample_restaurant_list,
    )

    assert result.columns.tolist() == preprocess.FINAL_COLUMNS
    assert result['restaurant_id'].tolist() == ['1001', '1002']
    assert result['categories'].tolist() == ['한식, 데이트', '일식']
    assert result.loc[0, 'feature'] == '데이트, 조용한'
    assert result.loc[1, 'feature'] == '깔끔한'
    assert result.loc[0, 'menu_1_name'] == '메뉴A'
    assert result.loc[1, 'menu_1_name'] == '메뉴B1'
    assert result.loc[1, 'menu_2_name'] == '메뉴B2'
    assert pd.isna(result.loc[1, 'menu_3_name'])
    assert result['collected_at'].notna().all()


def test_validate_restaurant_df_raises_for_empty_dataframe():
    with pytest.raises(ValueError, match='비어 있습니다'):
        preprocess.validate_restaurant_df(pd.DataFrame())


def test_validate_restaurant_df_raises_for_missing_column(valid_processed_df):
    invalid_df = valid_processed_df.drop(columns=['address'])

    with pytest.raises(ValueError, match='필수 컬럼이 누락'):
        preprocess.validate_restaurant_df(invalid_df)


def test_validate_restaurant_df_raises_for_required_null(valid_processed_df):
    invalid_df = valid_processed_df.copy()
    invalid_df.loc[0, 'address'] = pd.NA

    with pytest.raises(ValueError, match='필수 데이터에 결측값'):
        preprocess.validate_restaurant_df(invalid_df)


def test_validate_restaurant_df_raises_for_duplicate_restaurant_id(valid_processed_df):
    duplicate = valid_processed_df.copy()
    duplicate.loc[0, 'source_url'] = 'url-2'
    invalid_df = pd.concat([valid_processed_df, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match='restaurant_id'):
        preprocess.validate_restaurant_df(invalid_df)


def test_validate_restaurant_df_raises_for_duplicate_source_url(valid_processed_df):
    duplicate = valid_processed_df.copy()
    duplicate.loc[0, 'restaurant_id'] = '2002'
    invalid_df = pd.concat([valid_processed_df, duplicate], ignore_index=True)

    with pytest.raises(ValueError, match='source_url'):
        preprocess.validate_restaurant_df(invalid_df)


def test_validate_restaurant_df_returns_summary(valid_processed_df):
    result = preprocess.validate_restaurant_df(valid_processed_df)

    assert result == {
        'row_count': 1,
        'column_count': 16,
        'restaurant_id_duplicates': 0,
        'source_url_duplicates': 0,
    }


def test_save_processed_csv_writes_file(tmp_path, monkeypatch, valid_processed_df):
    monkeypatch.setattr(preprocess, 'PROCESSED_DATA_DIR', tmp_path)

    batch_id = '20260908_174901'
    result = preprocess.save_processed_csv(valid_processed_df, batch_id)

    expected_path = tmp_path / batch_id / 'diningcode_restaurants_processed.csv'

    assert result == expected_path
    assert result.is_file()

    loaded_df = pd.read_csv(result, encoding='utf-8-sig')
    assert loaded_df.shape == valid_processed_df.shape


def test_run_preprocess_runs_load_transform_validate_and_save(monkeypatch, tmp_path):
    batch_dir = tmp_path / '20260908_174901'
    batch_dir.mkdir()

    interim_path = batch_dir / 'diningcode_restaurants_parsed.csv'
    processed_path = tmp_path / 'processed.csv'

    interim_df = pd.DataFrame([{'interim': 1}])
    transformed_df = pd.DataFrame([{'processed': 1}])
    restaurant_list = [{'source_url': 'url-1', 'category': '한식'}]
    calls = []

    monkeypatch.setattr(preprocess, 'load_interim_csv', lambda path: interim_df)

    def fake_preprocess_restaurants(df, restaurants):
        calls.append(('preprocess', df, restaurants))
        return transformed_df

    def fake_validate(df):
        calls.append(('validate', df))
        return {'row_count': 1}

    def fake_save(df, batch_id):
        calls.append(('save', df, batch_id))
        return processed_path

    monkeypatch.setattr(preprocess, 'preprocess_restaurants', fake_preprocess_restaurants)
    monkeypatch.setattr(preprocess, 'validate_restaurant_df', fake_validate)
    monkeypatch.setattr(preprocess, 'save_processed_csv', fake_save)

    result = preprocess.run_preprocess(interim_path, restaurant_list)

    assert result == processed_path
    assert calls == [
        ('preprocess', interim_df, restaurant_list),
        ('validate', transformed_df),
        ('save', transformed_df, '20260908_174901'),
    ]
