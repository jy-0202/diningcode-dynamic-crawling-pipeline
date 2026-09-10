# DiningCode Dynamic Crawling Pipeline

Selenium을 활용해 DiningCode의 동적 페이지에서 음식점 정보를 제한적으로 수집하고,

**Raw HTML 저장 → 데이터 추출 → Interim CSV → 전처리 및 검증 → Processed CSV → MySQL UPSERT**

까지 수행하는 개인 데이터 수집 파이프라인 프로젝트입니다.

로컬 실행뿐 아니라 pytest, Ruff, GitHub Actions CI와 Windows Self-hosted Runner 기반 전체 배치 실행 환경도 구성했습니다.

---

## 1. 프로젝트 목적

JavaScript 기반 동적 웹페이지에서 필요한 데이터를 수집하고, 원본부터 최종 적재 데이터까지 단계별로 관리하는 데이터 파이프라인을 구현하는 것을 목표로 합니다.

주요 목표는 다음과 같습니다.

- Selenium을 이용한 동적 웹페이지 수집
- Raw / Interim / Processed 데이터 계층 분리
- BeautifulSoup을 이용한 Raw HTML 데이터 추출
- pandas를 이용한 데이터 전처리 및 품질 검증
- MySQL 데이터 저장
- PK / UNIQUE 제약 기반 UPSERT
- pytest 기반 단위 테스트
- Ruff 기반 정적 코드 검사
- GitHub Actions 기반 CI 자동화
- Self-hosted Runner 기반 전체 데이터 파이프라인 실행
- 실행 결과 Artifact 보관

---

## 2. 수집 대상 및 범위

- 대상 사이트: DiningCode
- 대상 지역: 서울 > 강남역
- 최대 스크롤 횟수: 2회
- 카테고리별 최대 음식점 후보: 5개
- 전체 음식점 후보 최대 수: 100개
- 음식점별 메뉴: 상위 3개
- 영업시간: 수집 시점을 기준으로 오늘 포함 7일 정보

무분별한 수집을 피하기 위해 지역, 스크롤 횟수, 카테고리별 후보 수, 전체 후보 수를 제한하여 실행합니다.

사이트 데이터와 노출 순서는 시점에 따라 변경될 수 있으므로 실제 수집 건수는 실행마다 달라질 수 있습니다.

---

## 3. 전체 파이프라인

```text
DiningCode
    ↓
Selenium 동적 크롤링
    ↓
Raw HTML
data/raw/html/{batch_id}/
    ↓
BeautifulSoup 데이터 추출
    ↓
Interim CSV
data/interim/{batch_id}/
    ↓
pandas 전처리 및 데이터 검증
    ↓
Processed CSV
data/processed/{batch_id}/
    ↓
MySQL UPSERT
    ↓
현재 배치 DB 반영 검증
```

프로그램의 실행 함수 흐름은 다음과 같습니다.

```text
run_crawling()
    ↓
run_extract()
    ↓
run_preprocess()
    ↓
run_load()
```

`main.py`가 전체 파이프라인의 실행 진입점 역할을 합니다.

---

## 4. Raw HTML 기반 구조

초기에는 Selenium에서 수집한 결과를 바로 Raw CSV로 저장하는 구조를 사용했습니다.

현재는 Crawling과 데이터 추출의 책임을 분리하기 위해 Raw HTML 기반 구조로 변경했습니다.

```text
기존

Selenium
→ Raw CSV
→ Preprocess
→ Processed CSV
→ MySQL
```

```text
현재

Selenium
→ Raw HTML
→ Extract
→ Interim CSV
→ Preprocess
→ Processed CSV
→ MySQL
```

Raw HTML을 별도로 보관하면 다음과 같은 장점이 있습니다.

- 수집 당시 렌더링 결과를 원본 데이터로 보존
- 사이트에 다시 접속하지 않고 Extract 로직 재실행 가능
- HTML 파싱 오류 발생 시 원본 데이터 기준으로 디버깅 가능
- Crawling과 Extract 단계의 책임 분리
- Raw / Interim / Processed 데이터 계층 구분
- 이후 클라우드 스토리지 기반 파이프라인으로 확장하기 쉬운 구조

Raw HTML 저장은 최초 사이트 접근 횟수를 줄이는 기능은 아니지만, 이후 데이터 추출 및 전처리 개발 과정에서 불필요한 재크롤링을 줄일 수 있습니다.

---

## 5. 주요 모듈 및 기능

### Config

`src/diningcode_pipeline/config.py`

공통 설정을 관리합니다.

- 프로젝트 및 데이터 저장 경로
- DiningCode 기본 URL
- 수집 대상 지역
- 최대 스크롤 횟수
- 카테고리별 수집 제한
- 전체 음식점 후보 제한
- 메뉴 수집 개수
- Selenium 대기시간

### Crawling

`src/diningcode_pipeline/crawling.py`

Selenium을 이용한 동적 페이지 탐색과 Raw HTML 저장을 담당합니다.

- Chrome WebDriver 생성
- Headed / Headless 실행 설정
- DiningCode 접속
- 서울 > 강남역 지역 선택
- WebDriverWait을 이용한 동적 요소 로딩 대기
- 최대 2회 결과 페이지 스크롤
- 카테고리별 상위 음식점 후보 수집
- `source_url` 기준 후보 중복 제거
- 음식점 목록 페이지 Raw HTML 저장
- 음식점별 상세페이지 Raw HTML 저장
- 실행 종료 시 WebDriver 자원 해제

### Extract

`src/diningcode_pipeline/extract.py`

저장된 Raw HTML을 읽어 구조화된 음식점 정보를 추출합니다.

- Raw HTML 파일 로드
- 음식점 후보 목록 파싱
- `source_url` 기준 중복 제거
- 음식점 상세정보 파싱
- 주소 및 전화번호 추출
- 오늘 포함 7일 영업시간 추출
- 태그 및 특징 데이터 추출
- 대표 이미지 URL 추출
- 상위 3개 메뉴 및 가격 추출
- 상세 HTML의 canonical URL 확인
- batch_id별 Interim CSV 저장
- Interim CSV 저장 전후 데이터 크기 검증

요일별 영업시간은 실행 당일의 영업 여부만 저장하지 않고, Raw HTML에 포함된 오늘부터 이후 6일까지의 정보를 함께 저장합니다.

예:

```text
오늘(목): 휴무일 |
9월 11일(금): 휴무일 |
9월 12일(토): 휴무일 |
9월 13일(일): 휴무일 |
9월 14일(월): 영업시간: 11:30 - 22:00 / 라스트오더: 21:00 |
...
```

특정 날짜의 임시 휴무 가능성을 고려해 단순히 "매주 목요일 휴무"처럼 재해석하지 않고 사이트에서 제공하는 날짜 정보를 그대로 보존합니다.

### Preprocess

`src/diningcode_pipeline/preprocess.py`

Interim CSV를 최종 적재 구조로 전처리하고 데이터 품질을 검증합니다.

- Interim CSV 로드
- `tag`, `char` 데이터를 `feature`로 통합
- 메뉴 데이터를 `menu_1 ~ menu_3` 컬럼으로 분리
- 음식점별 복수 카테고리 통합
- `restaurant_id` 생성
- `collected_at` 생성
- 빈 문자열 및 결측값 정리
- 필수 컬럼 존재 여부 검증
- 필수 데이터 결측 여부 검증
- `restaurant_id` 중복 검증
- `source_url` 중복 검증
- Processed CSV 저장
- 저장 전후 데이터 크기 검증

### Database

`src/diningcode_pipeline/database.py`

DB 연결 책임을 Load 단계에서 분리하여 관리합니다.

- 로컬 `.env` 파일 지원
- 배포 및 자동화 환경의 환경변수 지원
- 필수 DB 환경변수 검증
- `DB_PORT` 자료형 검증
- MySQL Database가 없으면 생성
- SQLAlchemy Engine 생성
- MySQL 연결 상태 확인

로컬에서는 `.env`를 사용할 수 있고, GitHub Actions에서는 GitHub Secrets를 환경변수로 전달합니다.

### Load

`src/diningcode_pipeline/load.py`

Processed 데이터를 MySQL에 저장하고 현재 배치의 반영 여부를 검증합니다.

- Processed CSV 로드
- DB 저장용 컬럼 및 자료형 정리
- 필수값 및 중복 데이터 재검증
- `diningcode_restaurant` 테이블 생성
- 음식점 데이터 UPSERT
- 현재 배치의 `restaurant_id`가 DB에 모두 존재하는지 검증
- 전체 DB 누적 건수 확인
- DB 샘플 데이터 출력
- SQLAlchemy Engine 자원 해제

---

## 6. 수집 데이터

최종 Processed 데이터는 16개 컬럼으로 구성됩니다.

| 컬럼 | 설명 |
|---|---|
| `restaurant_id` | DiningCode 상세 URL의 `rid` 기반 음식점 식별자 |
| `restaurant_name` | 음식점명 |
| `categories` | 음식점이 노출된 카테고리 |
| `address` | 주소 |
| `phone` | 전화번호 |
| `open_hours` | 수집일 기준 오늘 포함 7일 영업시간 |
| `feature` | 태그 및 음식점 특징 |
| `image_url` | 대표 이미지 URL |
| `menu_1_name` | 메뉴 1 |
| `menu_1_price` | 메뉴 1 가격 |
| `menu_2_name` | 메뉴 2 |
| `menu_2_price` | 메뉴 2 가격 |
| `menu_3_name` | 메뉴 3 |
| `menu_3_price` | 메뉴 3 가격 |
| `source_url` | 원본 상세페이지 URL |
| `collected_at` | 수집 시각 |

요일별 영업시간은 데이터 길이가 길어질 수 있으므로 MySQL의 `open_hours` 컬럼은 `TEXT` 타입을 사용합니다.

---

## 7. 데이터 저장 구조

Raw, Interim, Processed 데이터는 동일한 `batch_id`를 사용하여 하나의 실행 단위로 관리합니다.

예:

```text
20260910_234951
```

### Raw

```text
data/raw/html/{batch_id}/
├── restaurant_list.html
├── restaurant_detail_{rid}.html
├── restaurant_detail_{rid}.html
└── ...
```

Selenium으로 렌더링된 목록 및 상세페이지 HTML을 원본 데이터로 저장합니다.

### Interim

```text
data/interim/{batch_id}/
└── diningcode_restaurants_parsed.csv
```

Raw HTML에서 구조화된 음식점 데이터를 추출한 결과입니다.

### Processed

```text
data/processed/{batch_id}/
└── diningcode_restaurants_processed.csv
```

전처리 및 데이터 품질 검증을 완료한 최종 데이터입니다.

생성된 Raw HTML 및 CSV 데이터는 Git에 포함하지 않습니다.

---

## 8. MySQL 적재 방식

MySQL의 `diningcode_restaurant` 테이블에 최종 데이터를 저장합니다.

주요 제약조건은 다음과 같습니다.

```text
restaurant_id → PRIMARY KEY
source_url    → UNIQUE
```

동일 음식점이 다시 수집되면 새로운 행을 계속 추가하지 않고 `ON DUPLICATE KEY UPDATE` 방식으로 기존 데이터를 갱신합니다.

따라서 반복 실행 시에도 동일 음식점에 대한 중복 레코드가 누적되는 것을 방지합니다.

### 배치 적재 검증

MySQL은 이전 실행 데이터가 유지되는 누적 구조이므로 다음과 같이 단순 비교하지 않습니다.

```text
Processed CSV 건수 == DB 전체 건수
```

예를 들어 기존 DB에 77건이 있고 이번 배치가 72건이라면 UPSERT 후에도 기존 데이터가 삭제되지 않아 DB 전체는 77건일 수 있습니다.

현재는 다음 방식으로 검증합니다.

```text
이번 Processed CSV의 restaurant_id
            ↓
DB에서 해당 restaurant_id 조회
            ↓
이번 배치 건수와 실제 DB 반영 건수 비교
```

검증 결과 예:

```text
processed_count : 72
loaded_count    : 72
db_count        : 77
count_status    : 일치
```

- `processed_count`: 이번 Processed CSV 건수
- `loaded_count`: 이번 배치 ID 중 DB에 존재하는 건수
- `db_count`: DB 전체 누적 건수
- `count_status`: `processed_count`와 `loaded_count` 비교 결과

---

## 9. 프로젝트 구조

```text
.
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── pipeline.yml
│
├── src/
│   └── diningcode_pipeline/
│       ├── __init__.py
│       ├── config.py
│       ├── crawling.py
│       ├── database.py
│       ├── extract.py
│       ├── load.py
│       └── preprocess.py
│
├── tests/
│   ├── conftest.py
│   ├── test_crawling.py
│   ├── test_database.py
│   ├── test_extract.py
│   ├── test_load.py
│   ├── test_main.py
│   └── test_preprocess.py
│
├── data/
│   ├── raw/
│   │   └── html/
│   ├── interim/
│   └── processed/
│
├── .env.example
├── .gitignore
├── main.py
├── pyproject.toml
├── README.md
├── requirements-dev.txt
└── requirements.txt
```

실제 DB 접속 정보가 들어 있는 `.env`, 생성된 데이터 파일, 테스트 캐시 및 가상환경 등은 Git에서 제외합니다.

---

## 10. 실행 환경

- Python 3.10+
- Google Chrome
- MySQL

주요 Python 라이브러리:

- Selenium
- BeautifulSoup4
- pandas
- SQLAlchemy
- PyMySQL
- python-dotenv

개발 및 자동화 도구:

- pytest
- Ruff
- GitHub Actions

CI에서는 Python 3.13 환경을 사용합니다.

---

## 11. 설치

저장소를 내려받은 뒤 프로젝트 루트에서 가상환경을 생성합니다.

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

프로젝트 실행에 필요한 패키지를 설치합니다.

```bash
python -m pip install -r requirements.txt
```

테스트 및 코드 검사까지 수행하려면 개발용 패키지를 설치합니다.

```bash
python -m pip install -r requirements-dev.txt
```

---

## 12. DB 환경변수 설정

로컬 실행 시 `.env.example`을 참고하여 프로젝트 루트에 `.env` 파일을 생성합니다.

```env
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=
```

실제 DB 계정과 비밀번호가 들어 있는 `.env` 파일은 Git에 업로드하지 않습니다.

`database.py`는 다음 두 방식을 지원합니다.

```text
로컬
→ .env

자동화 / 배포 환경
→ 환경변수
```

GitHub Actions 전체 Pipeline에서는 Repository Secrets에 다음 값을 등록하여 사용합니다.

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

---

## 13. 로컬 실행

프로젝트 루트에서 다음 명령으로 전체 파이프라인을 실행합니다.

```bash
python main.py
```

실행 순서는 다음과 같습니다.

```text
1. Selenium 동적 크롤링
2. Raw HTML 저장
3. Raw HTML 데이터 추출
4. Interim CSV 저장
5. 전처리 및 데이터 검증
6. Processed CSV 저장
7. MySQL 연결 및 UPSERT
8. 현재 배치 DB 반영 검증
```

---

## 14. 데이터 품질 검증

각 파이프라인 단계에서 다음 내용을 검증합니다.

### Extract

- Raw HTML 파일 존재 여부
- 목록 및 상세정보 파싱
- canonical URL 확인
- Interim CSV 저장 전후 데이터 크기

### Preprocess

- 필수 컬럼 존재 여부
- 필수값 결측 여부
- `restaurant_id` 중복 여부
- `source_url` 중복 여부
- Processed CSV 저장 전후 데이터 크기

### Load

- DB 저장용 필수 컬럼 존재 여부
- DB 필수값 결측 여부
- `restaurant_id` 중복 여부
- `source_url` 중복 여부
- MySQL 연결 여부
- 이번 배치의 DB 반영 건수
- 전체 DB 누적 건수

---

## 15. 테스트 및 Ruff

실제 외부 사이트나 MySQL에 의존하지 않도록 단위 테스트에서는 pytest의 `monkeypatch`, 임시 경로 및 Fake 객체를 활용합니다.

테스트 대상은 다음과 같습니다.

- Crawling 보조 함수
- Raw HTML 저장
- WebDriver 종료 처리
- `source_url` 중복 제거
- Raw HTML 파일 로드
- 음식점 목록 파싱
- 상세정보 파싱
- 7일 영업시간 파싱
- 상위 메뉴 추출
- canonical URL 추출
- Interim CSV 저장
- 메뉴 데이터 변환
- 복수 카테고리 통합
- Processed 데이터 전처리
- 데이터 품질 검증
- Processed CSV 저장
- `.env` 및 환경변수 기반 DB 설정
- SQLAlchemy Engine 생성
- DB 생성 및 연결 확인
- DB 저장용 DataFrame 및 레코드 변환
- CREATE TABLE / UPSERT 호출
- 현재 배치의 DB 반영 검증
- `main.py` 전체 단계 호출 순서

테스트 실행:

```bash
python -m pytest -q
```

현재 기준 로컬 테스트 결과:

```text
56 passed
```

Ruff 코드 검사:

```bash
python -m ruff check .
```

---

## 16. GitHub Actions CI

`.github/workflows/ci.yml`

`main` 브랜치에 push하거나 pull request가 생성되면 GitHub-hosted Ubuntu Runner에서 자동으로 실행됩니다.

```text
Checkout
    ↓
Python 3.13 설정
    ↓
Dependency 설치
    ↓
Ruff
    ↓
pytest
```

CI는 실제 DiningCode 크롤링이나 실제 MySQL 연결을 수행하지 않고 단위 테스트와 정적 코드 검사를 수행합니다.

---

## 17. GitHub Actions 전체 Pipeline

`.github/workflows/pipeline.yml`

실제 크롤링부터 MySQL 적재까지 실행하는 Workflow도 별도로 구성했습니다.

전체 Pipeline은 `workflow_dispatch`를 사용하여 GitHub Actions 화면에서 수동으로 실행합니다.

```text
GitHub Actions
    ↓
Windows Self-hosted Runner
    ↓
Python / 가상환경 구성
    ↓
MySQL 연결 확인
    ↓
Selenium Crawling
    ↓
Raw HTML
    ↓
Extract
    ↓
Interim CSV
    ↓
Preprocess
    ↓
Processed CSV
    ↓
MySQL UPSERT
    ↓
현재 배치 DB 반영 검증
    ↓
Artifact 업로드
```

실제 브라우저 기반 수집이 필요한 Workflow이므로 검증된 Windows Self-hosted Runner에서 실행하며, Pipeline 실행 시 Chrome을 일반 브라우저 모드로 실행하도록 `HEADLESS=false`를 사용합니다.

DB 접속 정보는 GitHub Repository Secrets를 통해 환경변수로 전달합니다.

### Artifact

Pipeline 실행 후 다음 데이터를 GitHub Actions Artifact로 저장합니다.

```text
data/raw/html/
data/interim/
data/processed/
```

Artifact 보관 기간은 7일입니다.

이를 통해 GitHub Actions 실행 결과와 각 데이터 계층의 산출물을 함께 확인할 수 있습니다.

---

## 18. 기준 실행 결과

2026-09-10 전체 Pipeline 실행 기준 결과입니다.

```text
음식점 후보              : 75
source_url 중복 제거 후   : 72
상세 Raw HTML             : 72
Interim CSV               : 72
Processed CSV             : 72
Processed 컬럼             : 16
restaurant_id 중복         : 0
source_url 중복            : 0
MySQL 배치 반영            : 72 / 72
count_status               : 일치
```

또한 목록 HTML 1개와 상세 HTML 72개가 동일한 batch_id의 Raw 데이터로 저장되고, 같은 batch_id로 Interim / Processed 데이터가 생성되는 것을 확인했습니다.

수집 대상 사이트의 데이터와 노출 순서는 변경될 수 있으므로 위 수치는 고정 요구사항이 아니라 **기준 실행 결과**입니다.

---

## 19. 실행 환경에 따른 크롤링 차이

동일한 Selenium 코드라도 실행 환경에 따라 대상 사이트의 응답이 달라질 수 있습니다.

GitHub-hosted 환경과 Headless 실행 환경에서는 대상 사이트 접근 과정에서 정상 페이지가 반환되지 않는 사례를 확인했으며, 현재 실제 전체 Pipeline은 정상 동작을 확인한 Windows Self-hosted Runner에서 실행합니다.

CI와 실제 데이터 수집 Workflow를 분리하여 다음처럼 운영합니다.

```text
CI
→ GitHub-hosted Runner
→ Ruff + pytest

실제 Pipeline
→ Self-hosted Runner
→ Selenium + MySQL
```

이를 통해 코드 품질 검증과 외부 사이트에 의존하는 실제 데이터 수집 작업의 실행 환경을 분리했습니다.

---

## 20. 향후 개선

현재까지 로컬 및 Windows Self-hosted Runner 기반 데이터 파이프라인 실행을 완료했습니다.

향후에는 다음 내용을 단계적으로 검토할 예정입니다.

- 클라우드 VM 기반 실행 환경 구성
- 클라우드 환경에서 Selenium 실행 가능 여부 검증
- Raw / Interim / Processed 데이터의 Object Storage 저장
- 관리형 MySQL 연동
- 배치 실행 스케줄링
- 실행 로그 및 실패 상태 모니터링
- AWS Lambda / S3 / RDS / Step Functions / EventBridge 기반 서버리스 구조 검토

외부 사이트의 접근 정책과 실행 환경의 제약을 고려하여 실제 동작을 검증한 방식만 최종 배포 구조에 반영할 예정입니다.