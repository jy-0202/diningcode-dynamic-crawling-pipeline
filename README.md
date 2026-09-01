# DiningCode Dynamic Crawling Pipeline

Selenium을 활용해 DiningCode의 동적 페이지에서 음식점 정보를 제한적으로 수집하고,  
Raw CSV 저장 → 전처리 및 검증 → Processed CSV 저장 → MySQL UPSERT까지 수행하는  
개인 데이터 수집 파이프라인 프로젝트입니다.

## 1. 프로젝트 목적

동적 웹페이지를 대상으로 다음 과정을 하나의 로컬 데이터 파이프라인으로 구성하는 것을 목표로 합니다.

- Selenium을 이용한 동적 크롤링
- 원본 수집 데이터와 전처리 데이터 분리
- 데이터 정제 및 품질 검증
- MySQL 저장
- PK / UNIQUE 제약을 이용한 UPSERT

## 2. 수집 대상 및 범위

- 대상 사이트: DiningCode
- 대상 지역: 서울 > 강남역
- 최대 스크롤 횟수: 2회
- 카테고리별 최대 수집 후보: 5개
- 전체 음식점 후보 최대 수: 100개
- 상세페이지 메뉴 수집: 상위 3개

무분별한 수집을 피하기 위해 수집 범위를 제한하여 실행합니다.

## 3. 전체 파이프라인

```text
DiningCode
    ↓
Selenium 동적 크롤링
    ↓
data/raw/
    ↓
전처리 및 데이터 검증
    ↓
data/processed/
    ↓
MySQL UPSERT
```

프로그램 실행 순서는 다음과 같습니다.

```text
run_crawling()
    ↓
run_preprocess()
    ↓
run_load()
```

## 4. 주요 모듈 및 기능

### Config

`src/diningcode_pipeline/config.py`

- 프로젝트 루트 및 데이터 저장 경로 관리
- DiningCode 기본 URL 관리
- 수집 대상 지역 설정
- 최대 스크롤 횟수 및 수집 건수 제한 설정
- 메뉴 수집 개수 및 Selenium 대기시간 설정

### Crawling

`src/diningcode_pipeline/crawling.py`

- Chrome WebDriver 생성
- DiningCode 접속
- 서울 > 강남역 지역 선택
- 제한된 횟수만큼 결과 페이지 스크롤
- 카테고리별 상위 음식점 후보 수집
- `source_url` 기준 중복 제거
- 음식점 상세정보 수집
- 상위 3개 메뉴 수집
- Raw CSV 저장

### Preprocess

`src/diningcode_pipeline/preprocess.py`

- Raw CSV 로드
- `tag`, `char` 데이터를 `feature`로 통합
- 메뉴 데이터를 `menu_1 ~ menu_3` 컬럼으로 분리
- 음식점별 복수 카테고리 통합
- `restaurant_id` 생성
- `collected_at` 생성
- 결측값 정리
- 필수 컬럼 검증
- `restaurant_id`, `source_url` 중복 검증
- Processed CSV 저장

### Database

`src/diningcode_pipeline/database.py`

- `.env`에서 MySQL 접속 정보 로드
- 필수 DB 환경변수 검증
- 데이터베이스가 없으면 생성
- SQLAlchemy Engine 생성
- MySQL 연결 상태 확인

### Load

`src/diningcode_pipeline/load.py`

- Processed CSV 로드
- DB 저장용 컬럼 및 자료형 정리
- 필수값 및 중복 데이터 검증
- `diningcode_restaurant` 테이블 생성
- 음식점 데이터 UPSERT
- Processed CSV 건수와 DB 저장 건수 검증

## 5. 수집 데이터

최종 Processed 데이터는 다음 16개 컬럼으로 구성됩니다.

| 컬럼 | 설명 |
|---|---|
| `restaurant_id` | 음식점 식별자 |
| `restaurant_name` | 음식점명 |
| `categories` | 음식점 카테고리 |
| `address` | 주소 |
| `phone` | 전화번호 |
| `open_hours` | 영업시간 |
| `feature` | 태그 및 특징 |
| `image_url` | 대표 이미지 URL |
| `menu_1_name` | 메뉴 1 |
| `menu_1_price` | 메뉴 1 가격 |
| `menu_2_name` | 메뉴 2 |
| `menu_2_price` | 메뉴 2 가격 |
| `menu_3_name` | 메뉴 3 |
| `menu_3_price` | 메뉴 3 가격 |
| `source_url` | 원본 상세페이지 URL |
| `collected_at` | 수집 시각 |

## 6. 프로젝트 구조

```text
.
├── src/
│   └── diningcode_pipeline/
│       ├── __init__.py
│       ├── config.py
│       ├── crawling.py
│       ├── database.py
│       ├── preprocess.py
│       └── load.py
├── data/                         # 파이프라인 실행 시 생성
│   ├── raw/
│   └── processed/
├── .env.example
├── .gitignore
├── main.py
├── README.md
└── requirements.txt
```

`data/raw`, `data/processed` 디렉터리는 파이프라인 실행 시 자동으로 생성되며,  
생성된 CSV 파일과 실제 DB 접속 정보가 들어 있는 `.env` 파일은 Git에 포함하지 않습니다.

## 7. 실행 환경

- Python 3.10+
- Google Chrome
- MySQL

주요 Python 라이브러리:

- pandas
- Selenium
- SQLAlchemy
- PyMySQL
- python-dotenv

## 8. 설치

저장소를 내려받은 뒤 가상환경을 생성하고 필요한 패키지를 설치합니다.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

패키지 설치:

```bash
pip install -r requirements.txt
```

## 9. 환경변수 설정

`.env.example`을 참고하여 프로젝트 루트에 `.env` 파일을 생성합니다.

```env
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=
```

실제 DB 계정과 비밀번호가 들어 있는 `.env` 파일은 Git에 업로드하지 않습니다.

## 10. 실행

프로젝트 루트에서 다음 명령으로 전체 파이프라인을 실행합니다.

```bash
python main.py
```

실행하면 다음 순서로 처리됩니다.

```text
1. Selenium 동적 크롤링
2. Raw CSV 저장
3. 전처리 및 검증
4. Processed CSV 저장
5. MySQL UPSERT
6. CSV / DB 저장 건수 검증
```

## 11. 데이터 저장 구조

### Raw

```text
data/raw/
└── diningcode_restaurants_raw_YYYYMMDD_HHMMSS.csv
```

크롤링 직후 데이터를 저장합니다.

### Processed

```text
data/processed/
└── diningcode_restaurants_processed_YYYYMMDD_HHMMSS.csv
```

전처리 및 검증이 완료된 최종 데이터를 저장합니다.

## 12. 데이터 품질 검증

전처리 및 DB 적재 단계에서 다음 내용을 검증합니다.

- 필수 컬럼 존재 여부
- 필수값 결측 여부
- `restaurant_id` 중복 여부
- `source_url` 중복 여부
- CSV 저장 전후 데이터 크기
- Processed CSV와 MySQL 저장 건수 비교

## 13. MySQL 적재 방식

`restaurant_id`를 Primary Key로 사용하고,  
`source_url`에는 UNIQUE 제약을 적용합니다.

동일 음식점이 다시 수집되더라도 `ON DUPLICATE KEY UPDATE` 방식으로 갱신하여  
반복 실행 시 중복 레코드가 계속 추가되는 것을 방지합니다.

## 14. 향후 개선

현재 버전은 로컬 환경에서 실행되는 데이터 수집 파이프라인입니다.

향후 AWS Lambda, S3, RDS를 활용한 배치형 데이터 파이프라인으로 확장할 예정입니다.