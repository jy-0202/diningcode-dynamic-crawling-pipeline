
import main as app_main


def test_main_runs_crawling_preprocess_and_load_in_order(monkeypatch, tmp_path):
    raw_path = tmp_path / 'raw.csv'
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
        return raw_path, restaurants

    def fake_preprocess(path, restaurant_list):
        calls.append(('preprocess', path, restaurant_list))
        return processed_path

    def fake_load(path):
        calls.append(('load', path))
        return summary

    monkeypatch.setattr(app_main, 'run_crawling', fake_crawling)
    monkeypatch.setattr(app_main, 'run_preprocess', fake_preprocess)
    monkeypatch.setattr(app_main, 'run_load', fake_load)

    result = app_main.main()

    assert result == (raw_path, processed_path, summary)
    assert calls == [
        'crawling',
        ('preprocess', raw_path, restaurants),
        ('load', processed_path),
    ]
