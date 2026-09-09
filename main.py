"""
DiningCode 동적 크롤링 데이터 파이프라인 실행 파일

이 파일은 프로젝트의 실행 진입점(entry point)으로,
동적 크롤링, 데이터 추출, 전처리, MySQL 저장 작업을 순서대로 실행한다.

[사용 모듈]
1. crawling.py
    - Selenium으로 서울 > 강남역을 선택한다.
    - 카테고리별 음식점 목록과 상세페이지를 탐색한다.
    - 렌더링된 원본 HTML을 Raw 데이터로 저장한다.

2. extract.py
    - Raw HTML을 읽어 음식점 데이터를 추출한다.
    - 추출 데이터를 Interim CSV로 저장한다.

3. preprocess.py
    - Interim CSV를 읽어 전처리한다.
    - feature, menu_1~3, categories 등을 정리한다.
    - 검증 완료 데이터를 Processed CSV로 저장한다.

4. load.py
    - Processed CSV를 읽는다.
    - MySQL DB와 테이블을 생성한다.
    - 음식점 데이터를 UPSERT 방식으로 저장한다.
    - CSV와 DB 저장 건수를 검증한다.

[실행 흐름]
run_crawling()
→ Raw HTML 배치 폴더 경로 반환

run_extract(raw_batch_dir)
→ Interim CSV 파일 경로 + 중복 제거 전 음식점 후보 목록 반환

run_preprocess(interim_csv_file, restaurant_list)
→ Processed CSV 파일 경로 반환

run_load(processed_csv_file)
→ MySQL 저장 결과 요약 반환
"""

from pathlib import Path

from selenium.common.exceptions import WebDriverException
from sqlalchemy.exc import SQLAlchemyError

from src.diningcode_pipeline import run_crawling, run_extract, run_load, run_preprocess


def main() -> tuple[Path, Path, Path, dict[str, int | str]]:
    """DiningCode 동적 크롤링부터 MySQL 저장까지 전체 파이프라인을 실행한다."""
    print('=' * 60)
    print('DiningCode 동적 크롤링 데이터 파이프라인 시작')
    print('=' * 60)

    # 1. Crawling
    raw_batch_dir = run_crawling()

    # 2. Extract
    interim_csv_file, restaurant_list = run_extract(raw_batch_dir)

    # 3. Preprocess
    processed_csv_file = run_preprocess(interim_csv_file, restaurant_list)

    # 4. Load
    load_summary = run_load(processed_csv_file)

    print()
    print('>' * 60)
    print('DiningCode 동적 크롤링 데이터 파이프라인 완료')
    print('>' * 60)
    print()
    print(f'Raw HTML 배치 폴더 : {raw_batch_dir}')
    print(f'Interim CSV 파일 : {interim_csv_file}')
    print(f'Processed CSV 파일 : {processed_csv_file}')
    print(f'MySQL 저장 결과 : {load_summary}')

    return raw_batch_dir, interim_csv_file, processed_csv_file, load_summary


if __name__ == '__main__':
    try:
        main()

    except WebDriverException as error:
        print()
        print('Selenium 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

    except SQLAlchemyError as error:
        print()
        print('MySQL 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

    except (OSError, ValueError) as error:
        print()
        print('파일 처리 또는 데이터 변환 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')