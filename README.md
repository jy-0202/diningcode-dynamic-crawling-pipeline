# DiningCode Dynamic Crawling Pipeline

Selenium을 활용하여 동적 웹페이지의 음식점 데이터를 제한적으로
수집하고,\
**Raw HTML → Interim → Processed → MySQL** 단계로 처리하는 데이터 수집
파이프라인 프로젝트입니다.

데이터 수집뿐 아니라 전처리·품질 검증·멱등 적재를 구현하고, GitHub
Actions와 Google Compute Engine을 활용하여 **CI/CD 및 전체 Batch 실행
자동화**까지 구성했습니다.

> 외부 사이트에 불필요한 요청을 발생시키지 않도록 수집 범위와 실행
> 횟수를 제한하여 진행한 개인 프로젝트입니다.

-   **개발 기간**: 2026.08.14 \~ 2026.09.13
-   **개발 형태**: 개인 프로젝트
-   **Demo**: [YouTube 실행 영상](https://youtu.be/vJRltBh7z7k)

------------------------------------------------------------------------

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=flat-square&logo=selenium&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup-59666C?style=flat-square)
![pandas](https://img.shields.io/badge/pandas-150458?style=flat-square&logo=pandas&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=flat-square&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-D7FF64?style=flat-square&logo=ruff&logoColor=black)
![GitHub
Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)
![Google
Cloud](https://img.shields.io/badge/Google_Cloud-4285F4?style=flat-square&logo=googlecloud&logoColor=white)

------------------------------------------------------------------------

## 1. Pipeline

``` text
DiningCode
    ↓
Selenium Crawling
    ↓
Raw HTML
    ↓
BeautifulSoup Extract
    ↓
Interim CSV
    ↓
pandas Preprocessing & Validation
    ↓
Processed CSV
    ↓
MySQL UPSERT
    ↓
DB 반영 검증
```

수집·추출·전처리·적재의 책임을 분리하고, 동일한 `batch_id`를 사용하여 각
단계의 데이터를 하나의 실행 단위로 관리했습니다.

  단계        역할
  ----------- -------------------------------------------
  Raw         Selenium으로 수집한 원본 HTML 보존
  Interim     Raw HTML에서 추출한 구조화 데이터
  Processed   정제·검증을 완료한 최종 적재 데이터
  MySQL       PK / UNIQUE 기반 UPSERT 및 배치 반영 검증

Raw HTML을 별도로 저장하여 데이터 추출이나 전처리 로직을 수정할 때 외부
사이트를 다시 요청하지 않고 기존 원본을 이용할 수 있도록 구성했습니다.

------------------------------------------------------------------------

## 2. Key Features

### 제한적 동적 데이터 수집

-   서울 강남역 지역으로 수집 범위 제한
-   최대 스크롤 횟수 및 카테고리별 후보 수 제한
-   `source_url` 기준 음식점 후보 중복 제거
-   음식점 상세 페이지의 메뉴·영업시간·주소 등 수집
-   상세 페이지별 Timeout 및 최대 3회 재시도
-   개별 상세 페이지 실패가 전체 Batch 중단으로 이어지지 않도록 예외
    범위 분리

### 데이터 전처리 및 품질 검증

-   음식점별 복수 카테고리 통합
-   태그·특징 데이터 정리
-   메뉴 데이터를 고정 컬럼 구조로 변환
-   필수 컬럼 및 결측값 검증
-   `restaurant_id`, `source_url` 중복 검증
-   저장 전후 데이터 건수 검증

### MySQL 멱등 적재

`restaurant_id`와 `source_url`을 식별 기준으로 사용하고 PK / UNIQUE 제약
기반 UPSERT를 적용했습니다.

반복 실행 시 동일 데이터를 단순 추가하지 않고 기존 데이터를 갱신하며,
적재 후에는 현재 Batch의 `restaurant_id`가 DB에 모두 존재하는지
확인합니다.

------------------------------------------------------------------------

## 3. Result

**2026.09.13 GitHub Actions GCE Batch 기준**

  항목                          결과
  ---------------------- -----------
  음식점 후보                     75
  URL 중복 제거 후                72
  상세 Raw HTML                   72
  상세 HTML 저장 실패              0
  Interim CSV                     72
  Processed CSV                   72
  Processed 컬럼                  16
  `restaurant_id` 중복             0
  `source_url` 중복                0
  MySQL 배치 반영            72 / 72
  pytest                   56 passed

수집 대상 사이트의 데이터와 노출 순서는 변경될 수 있으므로 위 수치는
고정 요구사항이 아닌 **기준 실행 결과**입니다.

------------------------------------------------------------------------

## 4. CI / CD / Batch

코드 품질 검증, 배포, 실제 데이터 수집의 책임을 각각 분리했습니다.

``` text
CI
GitHub Actions
→ Ruff
→ pytest

CD
CI 성공
→ GCP 인증
→ GCE Start
→ 검증된 Commit 배포
→ GCE Stop

Batch
GitHub Actions
→ GCE Start
→ Selenium Crawling
→ Extract
→ Preprocess
→ MySQL UPSERT
→ DB 반영 검증
→ GCE Stop
```

### CI

-   GitHub-hosted Runner에서 Ruff 정적 검사와 pytest 단위 테스트 수행
-   CI 실패 시 CD 미실행

### CD

-   CI에서 검증된 `head_sha`를 기준으로 GCE에 배포
-   GitHub OIDC + Workload Identity Federation 사용
-   IAP + OS Login을 통한 GCE 접근
-   장기 Service Account JSON Key 및 SSH Private Key를 저장하지 않는
    구조

### Batch

-   실제 데이터 수집은 CD와 분리된 Workflow에서 실행
-   GCE VM 자동 Start → 전체 Pipeline → DB 검증 → Stop
-   중간 단계 실패 시에도 VM 중지 단계 실행
-   포트폴리오 운영 상태에서는 불필요한 요청과 비용을 줄이기 위해 자동
    Schedule 비활성화

------------------------------------------------------------------------

## 5. Troubleshooting

### Selenium Timeout으로 인한 전체 Batch 중단

**문제**\
GCE에서 Selenium으로 상세 페이지를 순차 수집하는 과정에서 일부 페이지의
응답 지연으로 Timeout이 발생하면 전체 Batch가 중단될 수 있었습니다.

**원인**\
상세 페이지 하나의 로딩 실패가 전체 Crawling 단계의 실패로 이어지는
구조였으며, 실행 환경에 따라 페이지 응답 시간에도 차이가 있었습니다.

**해결**
- `page_load_strategy='eager'` 적용
- 상세 페이지 로딩 제한시간 설정
- 상세 페이지별 최대 3회 재시도
- 개별 페이지 실패 후 다음 데이터 수집 계속

**결과**\
2026.09.13 기준 전체 Batch에서 **상세 HTML 72건 저장 / 최종 수집 실패
0건**을 확인했습니다.

이 과정을 통해 외부 서비스에 의존하는 작업에서는 개별 실패를 전체 작업과
분리하고 재시도 범위를 명확하게 설계하는 것이 Batch 안정성에 중요하다는
점을 확인했습니다.

------------------------------------------------------------------------

## 6. Project Structure

``` text
diningcode-dynamic-crawling-pipeline/
├── .github/
│   └── workflows/
│       ├── batch.yml
│       ├── cd.yml
│       ├── ci.yml
│       └── pipeline.yml
├── scripts/
│   └── run_pipeline.sh
├── src/
│   └── diningcode_pipeline/
│       ├── config.py
│       ├── crawling.py
│       ├── database.py
│       ├── extract.py
│       ├── load.py
│       └── preprocess.py
├── tests/
├── main.py
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

`main.py`가 전체 Pipeline의 실행 진입점이며 각 단계는 별도의 모듈로
분리했습니다.

``` text
run_crawling()
    ↓
run_extract()
    ↓
run_preprocess()
    ↓
run_load()
```

------------------------------------------------------------------------

## 7. What I Learned

이 프로젝트를 통해 단순한 데이터 수집을 넘어 다음 과정을 직접 구성하고
검증했습니다.

-   원본과 가공 데이터의 계층 분리
-   데이터 품질 및 정합성 검증
-   반복 실행을 고려한 멱등 적재
-   외부 서비스 장애를 고려한 예외 처리
-   테스트와 CI를 통한 코드 품질 관리
-   배포와 데이터 Batch의 책임 분리
-   클라우드 실행 환경의 인증 및 자동화

특히 기능이 한 번 실행되는 것보다 **반복 실행해도 데이터 정합성을
유지하고, 일부 실패가 전체 작업으로 확산되지 않도록 설계하는 과정**의
중요성을 경험했습니다.

------------------------------------------------------------------------

## Demo

전체 Batch 실행 과정은 아래 영상에서 확인할 수 있습니다.

▶ [YouTube Demo](https://youtu.be/vJRltBh7z7k)
