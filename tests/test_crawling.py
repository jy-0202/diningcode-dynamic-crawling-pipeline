import pytest

from src.diningcode_pipeline import crawling


def test_ensure_directory_creates_directory(tmp_path):
    directory = tmp_path / 'raw'

    result = crawling.ensure_directory(directory)

    assert result == directory
    assert directory.is_dir()


def test_remove_duplicate_restaurants_keeps_first_item():
    restaurants = [
        {'restaurant_name': 'A', 'source_url': 'url-1'},
        {'restaurant_name': 'A duplicate', 'source_url': 'url-1'},
        {'restaurant_name': 'B', 'source_url': 'url-2'},
    ]

    result = crawling.remove_duplicate_restaurants(restaurants)

    assert result == [restaurants[0], restaurants[2]]


def test_remove_duplicate_restaurants_returns_empty_list_for_empty_input():
    assert crawling.remove_duplicate_restaurants([]) == []


def test_run_crawling_calls_pipeline_and_quits_driver(monkeypatch, tmp_path):
    class FakeDriver:
        def __init__(self):
            self.page_source = '<html></html>'
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    driver = FakeDriver()
    wait = object()
    batch_dir = tmp_path / '20260908_174901'
    list_html_file = batch_dir / 'restaurant_list.html'

    restaurants = [{'restaurant_name': 'A', 'source_url': 'url-1'}]
    detail_files = [batch_dir / 'restaurant_detail_test1.html']

    monkeypatch.setattr(crawling, 'create_driver', lambda: (driver, wait))
    monkeypatch.setattr(crawling, 'create_html_batch_directory', lambda: batch_dir)
    monkeypatch.setattr(crawling, 'open_site', lambda d, w: None)
    monkeypatch.setattr(crawling, 'select_region', lambda d, w: None)
    monkeypatch.setattr(crawling, 'scroll_results', lambda d, w: None)
    monkeypatch.setattr(crawling, 'save_raw_html', lambda html, batch_dir, file_name: list_html_file)
    monkeypatch.setattr(crawling, 'collect_restaurant_list', lambda d: restaurants)
    monkeypatch.setattr(crawling, 'remove_duplicate_restaurants', lambda items: items)
    monkeypatch.setattr(crawling, 'save_restaurant_detail_htmls', lambda d, w, items, path: detail_files)

    result = crawling.run_crawling()

    assert result == batch_dir
    assert driver.quit_called is True


def test_run_crawling_quits_driver_when_collection_fails(monkeypatch, tmp_path):
    class FakeDriver:
        def __init__(self):
            self.page_source = '<html></html>'
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    driver = FakeDriver()
    wait = object()
    batch_dir = tmp_path / '20260908_174901'

    monkeypatch.setattr(crawling, 'create_driver', lambda: (driver, wait))
    monkeypatch.setattr(crawling, 'create_html_batch_directory', lambda: batch_dir)
    monkeypatch.setattr(crawling, 'open_site', lambda d, w: None)
    monkeypatch.setattr(crawling, 'select_region', lambda d, w: None)
    monkeypatch.setattr(crawling, 'scroll_results', lambda d, w: None)
    monkeypatch.setattr(crawling, 'save_raw_html', lambda html, batch_dir, file_name: batch_dir / file_name)

    def raise_error(driver):
        raise ValueError('수집 실패')

    monkeypatch.setattr(crawling, 'collect_restaurant_list', raise_error)

    with pytest.raises(ValueError, match='수집 실패'):
        crawling.run_crawling()

    assert driver.quit_called is True
