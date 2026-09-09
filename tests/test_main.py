
import main as app_main


def test_main_runs_pipeline_in_order(monkeypatch, tmp_path):
    raw_batch_dir = tmp_path / 'raw' / '20260908_174901'
    interim_path = tmp_path / 'interim.csv'
    processed_path = tmp_path / 'processed.csv'

    restaurants = [{'source_url': 'url-1'}]

    summary = {
        'processed_count': 1,
        'db_count': 1,
        'count_status': '일치',
    }

    calls = []

    def fake_crawling():
        calls.append('crawling')
        return raw_batch_dir

    def fake_extract(path):
        calls.append(('extract', path))
        return interim_path, restaurants

    def fake_preprocess(path, restaurant_list):
        calls.append(('preprocess', path, restaurant_list))
        return processed_path

    def fake_load(path):
        calls.append(('load', path))
        return summary

    monkeypatch.setattr(app_main, 'run_crawling', fake_crawling)
    monkeypatch.setattr(app_main, 'run_extract', fake_extract)
    monkeypatch.setattr(app_main, 'run_preprocess', fake_preprocess)
    monkeypatch.setattr(app_main, 'run_load', fake_load)

    result = app_main.main()

    assert calls == [
        'crawling',
        ('extract', raw_batch_dir),
        ('preprocess', interim_path, restaurants),
        ('load', processed_path),
    ]

    assert result == (
        raw_batch_dir,
        interim_path,
        processed_path,
        summary,
    )