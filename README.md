# DiningCode Dynamic Crawling Pipeline

Selenium을 활용해 DiningCode의 동적 페이지에서 음식점 정보를 제한적으로 수집하고,

**Raw HTML 저장 → 데이터 추출 → Interim CSV → 전처리 및 검증 → Processed CSV → MySQL UPSERT**

까지 수행하는 개인 데이터 수집 파이프라인 프로젝트입니다.

로컬 실행뿐 아니라 pytest, Ruff, GitHub Actions CI, Windows Self-hosted Runner 기반 전체 Pipeline 실행, Google Compute Engine(GCE) 실행 환경, CI 성공 후 자동 CD, GCE 기반 전체 Batch 자동 실행까지 구성했습니다.

GCE Batch 실행 시에는 VM을 자동으로 시작하고 신규 데이터를 크롤링한 뒤 MySQL 적재 및 검증까지 수행하고, 작업 종료 후 VM을 다시 중지합니다.

---

## Demo

GitHub Actions에서 GCE VM을 자동으로 시작한 뒤 신규 데이터를 크롤링하고,
Raw HTML → Interim CSV → Processed CSV → MySQL UPSERT까지 전체 Batch Pipeline을 실행한 후
VM을 다시 자동 중지하는 과정을 확인할 수 있습니다.

- 실행 영상: [YouTube Demo](https://youtu.be/vJRltBh7z7k)

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
- Windows Self-hosted Runner 기반 전체 데이터 파이프라인 실행
- Google Compute Engine 기반 Linux 실행 환경 구성
- GitHub Actions CI 성공 후 GCE 자동 배포
- GCE VM 자동 Start / Stop
- GCE 기반 Crawling → MySQL 전체 Batch 자동 실행
- Workload Identity Federation, IAP, OS Login 기반 인증
- 실행 시각 및 batch_id의 Asia/Seoul 시간대 적용
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

## 3. 전체 데이터 파이프라인

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

GCE에서는 `scripts/run_pipeline.sh`가 전체 Pipeline 실행을 담당합니다.

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
- 이후 Object Storage 기반 파이프라인으로 확장하기 쉬운 구조

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
- `page_load_strategy='eager'` 적용
- 상세페이지 로딩 제한시간 설정
- 상세페이지 로딩 실패 시 최대 3회 재시도
- 단일 상세페이지 실패 시 실패 내역 기록 후 다음 음식점 수집 계속
- 실행 종료 시 WebDriver 자원 해제

외부 사이트의 일시적인 응답 지연으로 전체 Batch가 중단되는 것을 줄이기 위해 상세페이지 단위의 Timeout 및 재시도 처리를 적용했습니다.

전체 상세페이지를 한 건도 저장하지 못한 경우에는 정상적인 수집 결과로 볼 수 없으므로 Pipeline을 실패 처리합니다.

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
- 자동화 및 배포 환경의 환경변수 지원
- 필수 DB 환경변수 검증
- `DB_PORT` 자료형 검증
- MySQL Database가 없으면 생성
- SQLAlchemy Engine 생성
- MySQL 연결 상태 확인

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
20260913_205533
```

GCE Batch에서는 `Asia/Seoul` 시간대를 명시하여 실행 로그와 `batch_id`를 한국시간 기준으로 생성합니다.

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

---

## 9. 프로젝트 구조

```text
.
├── .github/
│   └── workflows/
│       ├── batch.yml
│       ├── cd.yml
│       ├── ci.yml
│       └── pipeline.yml
│
├── scripts/
│   └── run_pipeline.sh
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

### 로컬 / Windows Self-hosted Runner

- Python 3.13
- Google Chrome
- MySQL
- Windows

### Google Compute Engine

- Ubuntu 24.04 LTS
- E2 기반 VM
- Google Chrome
- Xvfb
- Python 3.12
- MySQL
- Asia/Seoul 실행 시간대

### 주요 Python 라이브러리

- Selenium
- BeautifulSoup4
- pandas
- SQLAlchemy
- PyMySQL
- python-dotenv

### 개발 및 자동화 도구

- pytest
- Ruff
- GitHub Actions
- Google Cloud CLI
- Workload Identity Federation
- IAP
- OS Login

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

로컬 또는 GCE에서 실행할 때 `.env.example`을 참고하여 프로젝트 루트에 `.env` 파일을 생성할 수 있습니다.

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

자동화 환경
→ 환경변수
```

Windows Self-hosted Runner 기반 전체 Pipeline에서는 Repository Secrets에 다음 값을 등록하여 환경변수로 전달합니다.

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

GCE Batch에서는 DB 이름과 사용자를 Repository Variables로, 비밀번호는 Repository Secret으로 관리합니다.

```text
Variables
GCE_DB_NAME
GCE_DB_USER

Secret
GCE_DB_PASSWORD
```

GCE 내부 MySQL을 사용하므로 Batch 실행 시 다음 값은 Workflow에서 지정합니다.

```text
DB_HOST=localhost
DB_PORT=3306
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

## 14. GCE 실행

GCE에서는 Headless Chrome 대신 Xvfb 가상 디스플레이에서 일반 Chrome을 실행합니다.

전체 Pipeline 실행은 다음 스크립트로 표준화했습니다.

```bash
bash scripts/run_pipeline.sh
```

스크립트 내부에서는 다음 형태로 Pipeline을 실행합니다.

```bash
xvfb-run -a env HEADLESS=false \
  .venv/bin/python -c "from main import main; main()"
```

`main()`에서 발생한 예외가 프로세스의 실패 상태로 전달되도록 직접 호출하며, GitHub Actions가 Pipeline의 성공 또는 실패를 정확하게 판단할 수 있도록 합니다.

실행 스크립트에서는 다음 시간대를 명시합니다.

```bash
export TZ=Asia/Seoul
```

따라서 실행 시작·종료 로그와 Python의 `datetime.now()`를 이용한 `batch_id`가 한국시간 기준으로 생성됩니다.

GCE VM 내부 MySQL은 `127.0.0.1:3306`에만 바인딩하여 외부에 DB 포트를 공개하지 않습니다.

---

## 15. 데이터 품질 검증

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

## 16. 테스트 및 Ruff

실제 외부 사이트나 MySQL에 의존하지 않도록 단위 테스트에서는 pytest의 `monkeypatch`, 임시 경로 및 Fake 객체를 활용합니다.

주요 테스트 대상:

- Crawling 보조 함수
- Raw HTML 저장
- WebDriver 종료 처리
- `source_url` 중복 제거
- Raw HTML 파일 로드
- 음식점 목록 및 상세정보 파싱
- 7일 영업시간 파싱
- 상위 메뉴 추출
- canonical URL 추출
- Interim / Processed CSV 저장
- 메뉴 데이터 변환
- 복수 카테고리 통합
- 데이터 품질 검증
- `.env` 및 환경변수 기반 DB 설정
- SQLAlchemy Engine 생성
- DB 생성 및 연결 확인
- DB 저장용 DataFrame 및 레코드 변환
- CREATE TABLE / UPSERT 호출
- 현재 배치 DB 반영 검증
- `main.py` 전체 단계 호출 순서

테스트 실행:

```bash
python -m pytest -q
```

현재 기준:

```text
56 passed
```

Ruff 코드 검사:

```bash
python -m ruff check .
```

현재 기준:

```text
All checks passed!
```

---

## 17. GitHub Actions CI

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

외부 사이트에 대한 데이터 수집과 코드 품질 검사를 분리하여 일반적인 코드 변경마다 실제 크롤링이 반복되지 않도록 구성했습니다.

---

## 18. Windows Self-hosted Runner 전체 Pipeline

`.github/workflows/pipeline.yml`

Windows Self-hosted Runner에서도 실제 크롤링부터 MySQL 적재까지 전체 Pipeline을 실행할 수 있도록 별도의 Workflow를 구성했습니다.

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

Pipeline 실행 시 Chrome을 일반 브라우저 모드로 실행하도록 `HEADLESS=false`를 사용합니다.

DB 접속 정보는 GitHub Repository Secrets를 통해 환경변수로 전달합니다.

### Artifact

Pipeline 실행 후 다음 데이터를 GitHub Actions Artifact로 저장합니다.

```text
data/raw/html/
data/interim/
data/processed/
```

Artifact 보관 기간은 7일입니다.

---

## 19. Google Compute Engine 실행 환경

클라우드 VM에서도 실제 Pipeline이 동작하는지 검증하기 위해 Google Compute Engine에 Ubuntu 기반 실행 환경을 구성했습니다.

```text
Google Compute Engine
    ↓
Ubuntu 24.04 LTS
    ↓
Google Chrome + Xvfb
    ↓
Python Virtual Environment
    ↓
DiningCode Pipeline
    ↓
MySQL
```

GCE에서 실제로 다음 전체 단계를 검증했습니다.

```text
Crawling
→ Raw HTML
→ Extract
→ Interim CSV
→ Preprocess
→ Processed CSV
→ MySQL UPSERT
→ 현재 배치 DB 반영 검증
```

MySQL은 동일 VM 내부에서 실행하며 외부 DB 포트를 열지 않고 `localhost` 연결을 사용합니다.

---

## 20. 실행 환경에 따른 크롤링 차이

동일한 Selenium 코드라도 실행 환경과 브라우저 실행 방식에 따라 대상 사이트의 응답이 달라질 수 있음을 확인했습니다.

GCE 검증 결과:

```text
curl
→ 403 Forbidden

Headless Chrome
→ 403 Forbidden

Xvfb + 일반 Chrome
→ 정상 페이지 응답
→ 실제 Crawling 성공
```

따라서 GCE에서는 별도의 프록시나 User-Agent 변경 없이 Xvfb 가상 디스플레이에서 일반 Chrome을 실행하는 방식을 사용합니다.

이 결과는 특정 차단 원인을 단정하기 위한 것이 아니라 실제 실행 환경에서 관찰된 응답 차이를 기준으로 실행 방식을 결정한 것입니다.

---

## 21. GitHub Actions CD

`.github/workflows/cd.yml`

CI를 통과한 코드를 Google Compute Engine에 자동 배포하는 CD Workflow를 구성했습니다.

현재는 VM이 중지되어 있어도 CD가 자동으로 VM을 시작한 뒤 배포를 수행하고, 배포가 끝나면 다시 VM을 중지합니다.

```text
main push
    ↓
GitHub Actions CI
    ↓
Ruff + pytest
    ↓
CI 성공
    ↓
GitHub Actions CD
    ↓
GitHub OIDC
    ↓
Workload Identity Federation
    ↓
GCP Service Account
    ↓
GCE 자동 Start
    ↓
IAP Tunnel + OS Login
    ↓
CI가 검증한 동일 Commit 배포
    ↓
GCE 자동 Stop
```

### CI와 CD 연결

CD는 `workflow_run`을 이용하여 CI 완료 이벤트를 확인합니다.

```text
CI 성공
→ CD 실행

CI 실패
→ CD 배포하지 않음
```

수동 검증이 필요한 경우에는 `workflow_dispatch`를 이용해 CD를 직접 실행할 수도 있습니다.

### CI 검증 Commit 배포

CD는 단순히 실행 시점의 최신 `main`을 배포하지 않고 CI가 성공한 `head_sha`를 배포 대상으로 사용합니다.

검증 사례:

```text
CI 검증 Commit
97227d9d0490415ae1c7787de4be900f4f689f4f

GCE 배포 Commit
97227d9
```

이를 통해 CI가 검증한 코드와 실제 GCE에 배포된 코드를 일치시킵니다.

### Workload Identity Federation

GitHub Actions에 장기 Service Account JSON Key를 저장하지 않고 GitHub OIDC와 Google Cloud Workload Identity Federation을 사용합니다.

```text
GitHub OIDC Token
    ↓
Workload Identity Provider
    ↓
GCP Service Account
```

Workload Identity Provider 조건에서 허용 Repository와 `main` 브랜치를 제한합니다.

### IAP + OS Login

GCE SSH 접속에는 IAP Tunnel과 OS Login을 사용합니다.

CD용 Service Account에 필요한 IAM 권한을 별도로 부여하고 IAP를 통해 SSH 연결을 수행합니다.

### 임시 SSH Key

GitHub-hosted Runner는 매 실행마다 임시 SSH Key를 생성하여 OS Login에 등록합니다.

장기 SSH Private Key를 GitHub Secrets에 저장하지 않습니다.

### CD와 Batch 실행 분리

CD의 목적은 **검증된 최신 코드를 GCE에 배포하는 것**입니다.

따라서 CD Workflow에서는 실제 DiningCode 크롤링을 실행하지 않습니다.

```text
코드 변경
→ CI
→ CD
→ GCE 코드 배포

실제 데이터 수집
→ 별도 Batch Workflow
```

README나 테스트 코드 변경만으로 외부 사이트 크롤링이 반복 실행되는 구조를 방지하기 위해 배포와 Batch 실행을 분리했습니다.

---

## 22. GCE 전체 Batch 자동 실행

`.github/workflows/batch.yml`

GCE 환경에서 실제 신규 데이터 수집부터 MySQL 저장까지 전체 Pipeline을 자동 실행하는 Workflow를 구성했습니다.

현재는 `workflow_dispatch`를 사용하여 필요한 시점에 GitHub Actions 화면에서 실행합니다.

```text
GitHub Actions
    ↓
GCP 인증
    ↓
임시 OS Login SSH Key 생성
    ↓
GCE 자동 Start
    ↓
SSH 연결 준비 확인
    ↓
scripts/run_pipeline.sh
    ↓
Xvfb + 일반 Chrome
    ↓
DiningCode 신규 Crawling
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
GCE 자동 Stop
```

Pipeline의 중간 단계가 실패하더라도 마지막 VM 중지 단계는 실행되도록 구성하여 오류 발생 시 VM이 불필요하게 계속 실행되는 상황을 줄였습니다.

### 주기 실행 구성

GitHub Actions의 `schedule`을 이용한 주기 실행 구조도 구성했습니다.

예를 들어 다음 설정은 매주 일요일 오전 9시 KST에 실행됩니다.

```yaml
schedule:
  - cron: '0 0 * * 0'
```

GitHub Actions의 cron은 UTC를 기준으로 하므로 `00:00 UTC`는 `09:00 KST`에 해당합니다.

주기 실행 기능을 구성한 뒤 실제 Pipeline은 동일한 Batch Job을 사용하도록 설계했습니다.

다만 이 프로젝트는 상시 운영 서비스가 아닌 포트폴리오 목적의 제한적 데이터 수집 프로젝트이므로, 불필요한 GCE 비용과 대상 사이트에 대한 반복 요청을 방지하기 위해 **최종 저장소에서는 자동 schedule을 비활성화하고 `workflow_dispatch`만 유지합니다.**

필요한 경우 schedule 설정을 다시 활성화하여 정기 Batch로 운영할 수 있습니다.

---

## 23. 기준 실행 결과

### Windows Self-hosted Runner

2026-09-10 전체 Pipeline 실행 기준:

```text
음식점 후보              : 75
source_url 중복 제거 후  : 72
상세 Raw HTML            : 72
Interim CSV              : 72
Processed CSV            : 72
Processed 컬럼           : 16
restaurant_id 중복       : 0
source_url 중복          : 0
MySQL 배치 반영          : 72 / 72
count_status             : 일치
```

### Google Compute Engine 수동 실행

2026-09-11 GCE 실행 기준:

```text
음식점 후보              : 75
source_url 중복 제거 후  : 72
상세 Raw HTML            : 72
Interim CSV              : 72
Processed CSV            : 72
Processed 컬럼           : 16
restaurant_id 중복       : 0
source_url 중복          : 0
MySQL processed_count    : 72
MySQL loaded_count       : 72
MySQL db_count           : 72
count_status             : 일치
```

### GitHub Actions GCE Batch

2026-09-13 전체 자동 Batch 실행 기준:

```text
음식점 후보              : 75
source_url 중복 제거 후  : 72

상세 Raw HTML 저장       : 72
상세 HTML 저장 실패      : 0

Interim CSV              : 72

Processed CSV            : 72
Processed 컬럼           : 16
restaurant_id 중복       : 0
source_url 중복          : 0

MySQL processed_count    : 72
MySQL loaded_count       : 72
MySQL db_count           : 72
count_status             : 일치
```

전체 자동 Batch에서는 다음 과정이 하나의 Workflow에서 정상 완료되었습니다.

```text
GCE 자동 Start
→ 신규 DiningCode 크롤링
→ Raw HTML 저장
→ Extract
→ Interim CSV
→ Preprocess
→ Processed CSV
→ MySQL UPSERT
→ 배치 반영 검증
→ GCE 자동 Stop
```

수집 대상 사이트의 데이터와 노출 순서는 변경될 수 있으므로 위 수치는 고정 요구사항이 아니라 기준 실행 결과입니다.

---

## 24. CI / CD / Batch 역할 분리

```text
CI
GitHub-hosted Runner
→ Ruff
→ pytest
→ 코드 품질 검증


CD
GitHub-hosted Runner
→ WIF 인증
→ GCE Start
→ IAP + OS Login
→ CI 검증 Commit 배포
→ GCE Stop


Batch
GitHub-hosted Runner
→ WIF 인증
→ GCE Start
→ IAP + OS Login
→ Xvfb + Chrome
→ 신규 Selenium Crawling
→ Extract
→ Preprocess
→ MySQL Load
→ DB 반영 검증
→ GCE Stop
```

코드 품질 검증, 배포, 실제 외부 데이터 수집의 책임을 분리했습니다.

특히 CI/CD가 실행될 때마다 외부 사이트 크롤링이 발생하지 않도록 CD와 데이터 Batch를 독립적인 Workflow로 구성했습니다.

---

## 25. 보안 및 운영 고려사항

- `.env`는 Git에 포함하지 않음
- DB 비밀번호는 GitHub Repository Secret으로 관리
- 일반 설정값은 Repository Variables로 분리
- GCE CD 인증에 장기 Service Account JSON Key를 사용하지 않음
- GitHub OIDC + Workload Identity Federation 사용
- Workload Identity Provider의 Repository / Branch 조건 제한
- CD 및 Batch용 Service Account에 필요한 IAM 권한을 부여
- GCE SSH는 IAP + OS Login 사용
- GitHub-hosted Runner에서 임시 SSH Key 생성
- 장기 SSH Private Key를 Repository Secrets에 저장하지 않음
- GCE MySQL은 `127.0.0.1:3306`에만 바인딩
- MySQL 3306 포트를 외부 공개하지 않음
- 실제 크롤링 실행과 코드 배포를 분리하여 불필요한 외부 사이트 호출 방지
- GCE Batch 완료 또는 실패 후 VM 중지 단계 실행
- 상시 VM 운영 대신 필요할 때 VM을 시작하고 작업 후 중지하여 컴퓨팅 비용 절감
- 포트폴리오 운영 상태에서는 자동 주기 크롤링을 비활성화하여 불필요한 반복 요청 방지

---

## 26. 향후 개선

현재까지 다음 범위를 구현하고 실제 실행으로 검증했습니다.

```text
로컬 Pipeline
→ Windows Self-hosted Runner Pipeline
→ GitHub Actions CI
→ Google Compute Engine 실행 환경
→ CI 성공 후 GCE 자동 CD
→ GCE 자동 Start / Stop
→ GCE 신규 크롤링부터 MySQL까지 전체 Batch 자동 실행
```

향후에는 다음 내용을 검토할 예정입니다.

- Raw / Interim / Processed 데이터의 Object Storage 저장
- Cloud SQL 또는 RDS 등 관리형 MySQL 연동
- 실행 로그 및 실패 상태 모니터링과 알림 기능
- CD 배포 실패 시 Rollback 전략
- Dependency 설치 및 배포 시간 최적화
- AWS EC2 / SSM / Step Functions / EventBridge Scheduler 기반 오케스트레이션 검토
- 필요 시 주기 Batch schedule 재활성화

외부 사이트의 접근 정책과 실행 환경의 제약을 고려하여 실제 동작을 검증한 방식만 최종 실행 구조에 반영합니다.
