#!/usr/bin/env bash

set -euo pipefail

export TZ=Asia/Seoul

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "============================================================"
echo "DiningCode 전체 데이터 파이프라인 시작"
echo "시작 시각: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

if [ ! -x ".venv/bin/python" ]; then
  echo "Python 가상환경을 찾을 수 없습니다."
  exit 1
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "xvfb-run을 찾을 수 없습니다."
  exit 1
fi

if ! command -v google-chrome >/dev/null 2>&1; then
  echo "Google Chrome을 찾을 수 없습니다."
  exit 1
fi

xvfb-run -a env HEADLESS=false \
  .venv/bin/python -c "from main import main; main()"

echo "============================================================"
echo "DiningCode 전체 데이터 파이프라인 완료"
echo "종료 시각: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"